#!/usr/bin/env python3
"""Capture and evaluate the frozen training-only GFS MOS precipitation model."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import os
import threading
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP, getcontext
from pathlib import Path
from zoneinfo import ZoneInfo


getcontext().prec = 40
ROOT = Path(__file__).resolve().parents[1]
IDENTITY = "gfs_mos_local_day_precipitation_jeffreys_wilson95_development_v1"
SCHEMA = "gfs_mos_precipitation_development_v1"
DEVELOPMENT_SHA256 = "d912e490731b3dcafeec824837709c4241c3a0ef1a958543c543a8b25c3de436"
STATIONS_SHA256 = "297e7cdf081c38212c3a1298d09921dfcb79fff9f3fa3bae6ccafc3b8ed09d12"
IEM_URL = "https://mesonet.agron.iastate.edu/cgi-bin/request/mos.py"
ISD_URL = "https://www.ncei.noaa.gov/pub/data/noaa/isd-history.csv"
NCEI_URL = "https://www.ncei.noaa.gov/access/services/data/v1"
HISTORY_START = dt.date(2024, 1, 1)
HISTORY_END = dt.date(2024, 12, 31)
DEVELOPMENT_START = dt.date(2025, 1, 1)
DEVELOPMENT_END = dt.date(2025, 11, 23)
RESERVED_START = dt.date(2025, 11, 24)
RESERVED_END = dt.date(2026, 7, 31)
EXPECTED_HISTORY_DATES = 366
EXPECTED_DEVELOPMENT_DATES = 327
EXPECTED_RESERVED_DATES = 250
EXPECTED_STATIONS = 20
EXPECTED_REQUESTS = 23
REQUIRED_MOS_FIELDS = {"runtime", "ftime", "model", "p06", "station"}
SOURCE_MODEL = "GFS"
FORECAST_MODEL = "noaa_gfs_station_mos_p06_local_day_v1"
Z95 = Decimal("1.6448536269514722")
PRICE = Decimal("0.70")
MIN_EDGE = Decimal("0.015")
MIN_HISTORY = 30
BOOTSTRAP_SAMPLES = 10_000
SCORE_BANDS = (
    (Decimal("0.00"), Decimal("0.50"), "0.00-0.50"),
    (Decimal("0.50"), Decimal("0.70"), "0.50-0.70"),
    (Decimal("0.70"), Decimal("0.80"), "0.70-0.80"),
    (Decimal("0.80"), Decimal("0.90"), "0.80-0.90"),
    (Decimal("0.90"), Decimal("0.95"), "0.90-0.95"),
    (Decimal("0.95"), Decimal("1.0001"), "0.95-1.00"),
)
RELIABILITY_BANDS = SCORE_BANDS[2:]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--max-requests", type=int, required=True)
    return parser.parse_args()


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes())


def atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def create_once(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError(f"Create-once source changed: {path.name}.")
        return
    path.write_bytes(payload)


def date_range(start: dt.date, end: dt.date) -> list[dt.date]:
    output = []
    current = start
    while current <= end:
        output.append(current)
        current += dt.timedelta(days=1)
    return output


def assert_frozen_dates() -> tuple[list[dt.date], list[dt.date]]:
    history = date_range(HISTORY_START, HISTORY_END)
    development = date_range(DEVELOPMENT_START, DEVELOPMENT_END)
    reserved = date_range(RESERVED_START, RESERVED_END)
    if (
        len(history) != EXPECTED_HISTORY_DATES
        or len(development) != EXPECTED_DEVELOPMENT_DATES
        or len(reserved) != EXPECTED_RESERVED_DATES
        or history[-1] >= development[0]
        or development[-1] >= reserved[0]
    ):
        raise ValueError("Frozen date identity is invalid.")
    return history, development


def assert_not_production_host() -> None:
    try:
        with urllib.request.urlopen("http://127.0.0.1:8787/api/status", timeout=1) as response:
            payload = json.load(response)
    except (OSError, ValueError, urllib.error.URLError):
        return
    if not isinstance(payload, dict) or not isinstance(payload.get("environment"), str):
        raise ValueError("Local Mimir runtime identity is malformed.")
    if payload["environment"] == "production":
        raise ValueError("Precipitation evidence acquisition is forbidden on a production Mimir host.")


class RequestBudget:
    def __init__(self, maximum: int):
        if maximum != EXPECTED_REQUESTS:
            raise ValueError(f"The frozen request budget is exactly {EXPECTED_REQUESTS}.")
        self.maximum = maximum
        self.used = 0
        self.lock = threading.Lock()

    def consume(self) -> None:
        with self.lock:
            if self.used >= self.maximum:
                raise ValueError("Frozen request budget exhausted.")
            self.used += 1


def fetch(url: str, budget: RequestBudget) -> tuple[bytes, dict[str, str]]:
    budget.consume()
    request = urllib.request.Request(url, headers={"User-Agent": "mimir-public-gfs-mos-precipitation/1"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.read(), {key.lower(): value for key, value in response.headers.items()}
    except urllib.error.HTTPError as error:
        if error.code == 429:
            raise ValueError("Frozen acquisition stopped on HTTP 429 without retry.") from error
        raise


def mos_url(station_id: str) -> str:
    first_runtime = HISTORY_START - dt.timedelta(days=1)
    last_runtime = DEVELOPMENT_END - dt.timedelta(days=1)
    if last_runtime >= RESERVED_START:
        raise ValueError("MOS URL would access a reserved date.")
    query = urllib.parse.urlencode({
        "station": station_id,
        "model": SOURCE_MODEL,
        "year1": first_runtime.year,
        "month1": first_runtime.month,
        "day1": first_runtime.day,
        "hour1": 12,
        "year2": last_runtime.year,
        "month2": last_runtime.month,
        "day2": last_runtime.day,
        "hour2": 12,
    })
    return f"{IEM_URL}?{query}"


def local_day_interval_ends(market_date: dt.date, time_zone: str) -> list[dt.datetime]:
    zone = ZoneInfo(time_zone)
    local_start = dt.datetime.combine(market_date, dt.time(), tzinfo=zone).astimezone(dt.timezone.utc)
    local_end = dt.datetime.combine(market_date + dt.timedelta(days=1), dt.time(), tzinfo=zone).astimezone(dt.timezone.utc)
    cursor = (local_start - dt.timedelta(hours=12)).replace(minute=0, second=0, microsecond=0)
    cursor -= dt.timedelta(hours=cursor.hour % 6)
    output = []
    while cursor <= local_end + dt.timedelta(hours=12):
        interval_start = cursor - dt.timedelta(hours=6)
        if interval_start < local_end and cursor > local_start:
            output.append(cursor)
        cursor += dt.timedelta(hours=6)
    if len(output) not in (4, 5) or len(output) != len(set(output)):
        raise ValueError(f"Local-day interval identity is invalid for {market_date}|{time_zone}.")
    return output


def proxy_band(value: Decimal) -> str:
    for low, high, label in SCORE_BANDS:
        if low <= value < high:
            return label
    raise ValueError("Raw no-rain proxy is outside frozen bands.")


def parse_mos(
    payload: bytes,
    station: dict[str, object],
    desired_dates: list[dt.date],
) -> tuple[list[dict[str, object]], tuple[str, ...], int]:
    station_id = str(station["station_id"])
    reader = csv.DictReader(io.StringIO(payload.decode("utf-8")))
    fieldnames = tuple(reader.fieldnames or ())
    if len(fieldnames) != len(set(fieldnames)) or not REQUIRED_MOS_FIELDS.issubset(fieldnames):
        raise ValueError(f"IEM MOS schema drifted for {station_id}.")
    desired = set(desired_dates)
    selected: dict[tuple[dt.date, dt.datetime], Decimal] = {}
    duplicates = 0
    for row in reader:
        if row.get("station") != station_id or row.get("model") != SOURCE_MODEL:
            raise ValueError(f"IEM MOS identity drifted for {station_id}.")
        try:
            runtime = dt.datetime.strptime(row["runtime"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=dt.timezone.utc)
            forecast_time = dt.datetime.strptime(row["ftime"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=dt.timezone.utc)
        except (KeyError, ValueError) as error:
            raise ValueError(f"IEM MOS clock is malformed for {station_id}.") from error
        if runtime.hour != 12 or runtime.minute != 0 or runtime.second != 0:
            continue
        market_date = runtime.date() + dt.timedelta(days=1)
        if market_date not in desired:
            continue
        expected = set(local_day_interval_ends(market_date, str(station["time_zone"])))
        if forecast_time not in expected:
            continue
        if row.get("p06") in (None, ""):
            raise ValueError(f"IEM MOS p06 is missing for {station_id}|{market_date}|{forecast_time.isoformat()}.")
        try:
            p06 = Decimal(str(row["p06"]))
        except Exception as error:
            raise ValueError(f"IEM MOS p06 is malformed for {station_id}|{market_date}.") from error
        if not p06.is_finite() or not Decimal(0) <= p06 <= Decimal(100):
            raise ValueError(f"IEM MOS p06 is outside bounds for {station_id}|{market_date}.")
        key = (market_date, forecast_time)
        if key in selected:
            if selected[key] != p06:
                raise ValueError(f"IEM MOS p06 has a conflicting duplicate for {station_id}|{market_date}.")
            duplicates += 1
        else:
            selected[key] = p06
    output = []
    for market_date in desired_dates:
        endpoints = local_day_interval_ends(market_date, str(station["time_zone"]))
        missing = [endpoint for endpoint in endpoints if (market_date, endpoint) not in selected]
        if missing:
            raise ValueError(f"IEM MOS local-day coverage is incomplete for {station_id}|{market_date}: {missing[:2]}.")
        probabilities = [selected[(market_date, endpoint)] for endpoint in endpoints]
        raw_no = Decimal(1)
        for probability in probabilities:
            raw_no *= Decimal(1) - probability / Decimal(100)
        raw_no = raw_no.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
        initialized = market_date - dt.timedelta(days=1)
        output.append({
            "station_id": station_id,
            "market_date": market_date.isoformat(),
            "time_zone": station["time_zone"],
            "forecast_model": FORECAST_MODEL,
            "forecast_initialized_at": f"{initialized.isoformat()}T12:00:00Z",
            "forecast_available_by": f"{initialized.isoformat()}T20:00:00Z",
            "selected_interval_ends_utc": [value.isoformat().replace("+00:00", "Z") for value in endpoints],
            "selected_p06_percent": [str(value) for value in probabilities],
            "raw_no_rain_proxy": str(raw_no),
            "proxy_band": proxy_band(raw_no),
        })
    return output, fieldnames, duplicates


def parse_isd(payload: bytes, stations: list[dict[str, object]]) -> list[dict[str, object]]:
    reader = csv.DictReader(io.StringIO(payload.decode("utf-8")))
    expected = ["USAF", "WBAN", "STATION NAME", "CTRY", "STATE", "ICAO", "LAT", "LON", "ELEV(M)", "BEGIN", "END"]
    if reader.fieldnames != expected:
        raise ValueError("NOAA ISD station-history header is unsupported.")
    rows = list(reader)
    identities = []
    for station in stations:
        station_id = str(station["station_id"])
        matches = sorted(
            [row for row in rows if row["ICAO"] == station_id and len(row["WBAN"]) == 5 and row["WBAN"] != "99999"],
            key=lambda row: row["END"], reverse=True,
        )
        if not matches:
            raise ValueError(f"NOAA ISD has no exact identity for {station_id}.")
        selected = matches[0]
        if selected["BEGIN"] > HISTORY_START.strftime("%Y%m%d") or selected["END"] < DEVELOPMENT_END.strftime("%Y%m%d"):
            raise ValueError(f"NOAA ISD identity does not cover the frozen window for {station_id}.")
        if (
            abs(float(selected["LAT"]) - float(station["latitude"])) > 0.2
            or abs(float(selected["LON"]) - float(station["longitude"])) > 0.2
        ):
            raise ValueError(f"NOAA ISD coordinates conflict for {station_id}.")
        identities.append({
            "station_id": station_id,
            "ghcn_station_id": f"USW000{selected['WBAN']}",
            "usaf": selected["USAF"],
            "wban": selected["WBAN"],
            "station_name": selected["STATION NAME"],
            "latitude": float(selected["LAT"]),
            "longitude": float(selected["LON"]),
            "history_begin": selected["BEGIN"],
            "history_end": selected["END"],
        })
    if len(identities) != EXPECTED_STATIONS or len({row["ghcn_station_id"] for row in identities}) != EXPECTED_STATIONS:
        raise ValueError("NOAA station mapping is not one-to-one.")
    return identities


def outcome_url(identities: list[dict[str, object]], start: dt.date, end: dt.date) -> str:
    if end >= RESERVED_START:
        raise ValueError("Outcome URL would access a reserved date.")
    query = urllib.parse.urlencode({
        "dataset": "daily-summaries",
        "stations": ",".join(str(identity["ghcn_station_id"]) for identity in identities),
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "dataTypes": "PRCP",
        "format": "json",
        "units": "standard",
        "includeAttributes": "true",
        "includeStationName": "true",
        "includeStationLocation": "true",
    })
    return f"{NCEI_URL}?{query}"


def parse_attributes(value: object, identity: str) -> tuple[str, str, str, str]:
    if not isinstance(value, str):
        raise ValueError(f"NOAA NCEI PRCP attributes are missing for {identity}.")
    fields = value.split(",")
    if len(fields) == 3:
        fields.append("")
    if len(fields) != 4:
        raise ValueError(f"NOAA NCEI PRCP attributes are malformed for {identity}.")
    measurement, quality, source, observation_time = fields
    if measurement not in ("", "T", "B", "D") or quality != "" or not source or observation_time not in ("", "2400"):
        raise ValueError(f"NOAA NCEI PRCP attributes are unsafe for {identity}: {value}.")
    return measurement, quality, source, observation_time


def parse_outcomes(
    payload: bytes,
    identities: list[dict[str, object]],
    dates: list[dt.date],
) -> dict[tuple[str, str], dict[str, object]]:
    rows = json.loads(payload)
    if not isinstance(rows, list):
        raise ValueError("NOAA NCEI daily summaries response is malformed.")
    by_ghcn = {str(identity["ghcn_station_id"]): identity for identity in identities}
    desired = {value.isoformat() for value in dates}
    outcomes: dict[tuple[str, str], dict[str, object]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("NOAA NCEI outcome row is malformed.")
        identity = by_ghcn.get(str(row.get("STATION", "")))
        market_date = str(row.get("DATE", ""))
        if identity is None or market_date not in desired:
            raise ValueError("NOAA NCEI returned an unexpected station/date.")
        key = (str(identity["station_id"]), market_date)
        if key in outcomes:
            raise ValueError(f"NOAA NCEI PRCP is duplicated for {key[0]}|{key[1]}.")
        try:
            precipitation = Decimal(str(row["PRCP"]))
        except Exception as error:
            raise ValueError(f"NOAA NCEI PRCP is malformed for {key[0]}|{key[1]}.") from error
        if not precipitation.is_finite() or not Decimal(0) <= precipitation <= Decimal(100):
            raise ValueError(f"NOAA NCEI PRCP is outside bounds for {key[0]}|{key[1]}.")
        measurement, quality, source, observation_time = parse_attributes(row.get("PRCP_ATTRIBUTES"), f"{key[0]}|{key[1]}")
        if measurement == "T" and precipitation != 0:
            raise ValueError(f"NOAA NCEI trace PRCP is nonzero for {key[0]}|{key[1]}.")
        outcome_no = int(precipitation == 0 and measurement != "T")
        outcomes[key] = {
            "observed_prcp_inches": str(precipitation),
            "outcome_no": outcome_no,
            "measurement_flag": measurement,
            "quality_flag": quality,
            "source_flag": source,
            "observation_time": observation_time,
            "observation_attributes": str(row["PRCP_ATTRIBUTES"]),
            "observation_source": "noaa_ncei_daily_summaries_prcp",
            "observation_station_name": str(row.get("NAME") or identity["station_name"]),
        }
    expected = {(str(identity["station_id"]), value.isoformat()) for identity in identities for value in dates}
    missing = sorted(expected - set(outcomes))
    if missing:
        raise ValueError(f"NOAA NCEI PRCP coverage is incomplete: {missing[:5]}.")
    if set(outcomes) != expected:
        raise ValueError("NOAA NCEI PRCP identity is not exact.")
    return outcomes


def wilson_lower(successes: int, trials: int) -> Decimal:
    if trials <= 0 or successes < 0 or successes > trials:
        raise ValueError("Wilson inputs are invalid.")
    n = Decimal(trials)
    proportion = Decimal(successes) / n
    z2 = Z95 * Z95
    center = proportion + z2 / (Decimal(2) * n)
    radius = Z95 * ((proportion * (Decimal(1) - proportion) + z2 / (Decimal(4) * n)) / n).sqrt()
    return max(Decimal(0), (center - radius) / (Decimal(1) + z2 / n))


def exact_fee(price: Decimal) -> Decimal:
    return (Decimal("0.07") * price * (Decimal(1) - price)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def brier(rows: list[dict[str, object]], probability_key: str) -> Decimal:
    if not rows:
        raise ValueError("Brier input is empty.")
    return sum(
        (Decimal(str(row[probability_key])) - Decimal(int(row["outcome_no"]))) ** 2
        for row in rows
    ) / Decimal(len(rows))


def clustered_lower(rows: list[dict[str, object]], value_key: str, seed: int) -> Decimal | None:
    clusters: dict[str, list[Decimal]] = defaultdict(list)
    for row in rows:
        clusters[str(row["market_date"])].append(Decimal(str(row[value_key])))
    ordered = [clusters[key] for key in sorted(clusters)]
    if not ordered:
        return None
    state = seed & 0xFFFF_FFFF
    samples = []
    for _ in range(BOOTSTRAP_SAMPLES):
        total = Decimal(0)
        count = 0
        for _ in ordered:
            state ^= (state << 13) & 0xFFFF_FFFF
            state ^= state >> 17
            state ^= (state << 5) & 0xFFFF_FFFF
            state &= 0xFFFF_FFFF
            cluster = ordered[(state * len(ordered)) // 0x1_0000_0000]
            total += sum(cluster, Decimal(0))
            count += len(cluster)
        samples.append(total / Decimal(count))
    samples.sort()
    return samples[int(Decimal("0.05") * Decimal(BOOTSTRAP_SAMPLES))]


def maximum_drawdown(rows: list[dict[str, object]]) -> Decimal:
    cumulative = Decimal(0)
    peak = Decimal(0)
    drawdown = Decimal(0)
    for row in sorted(rows, key=lambda value: (str(value["market_date"]), str(value["station_id"]))):
        cumulative += Decimal(str(row["fixed_price_return"]))
        peak = max(peak, cumulative)
        drawdown = max(drawdown, peak - cumulative)
    return drawdown


def score_rows(rows: list[dict[str, object]]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    by_station: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        by_station[str(row["station_id"])].append(row)
    scored = []
    fee = exact_fee(PRICE)
    for station in sorted(by_station):
        station_rows = sorted(by_station[station], key=lambda row: str(row["market_date"]))
        for row in station_rows:
            market_date = dt.date.fromisoformat(str(row["market_date"]))
            if not DEVELOPMENT_START <= market_date <= DEVELOPMENT_END:
                continue
            cutoff = market_date - dt.timedelta(days=2)
            window_start = cutoff - dt.timedelta(days=364)
            history = [
                prior for prior in station_rows
                if window_start <= dt.date.fromisoformat(str(prior["market_date"])) <= cutoff
            ]
            if len(history) != 365:
                raise ValueError(f"Causal station history is incomplete for {station}|{market_date}: {len(history)}.")
            same_band = [prior for prior in history if prior["proxy_band"] == row["proxy_band"]]
            if len(same_band) < MIN_HISTORY:
                continue
            successes = sum(int(prior["outcome_no"]) for prior in same_band)
            model_probability = (Decimal(successes) + Decimal("0.5")) / (Decimal(len(same_band)) + Decimal(1))
            conservative_score = wilson_lower(successes, len(same_band))
            climatology_successes = sum(int(prior["outcome_no"]) for prior in history)
            station_climatology = (Decimal(climatology_successes) + Decimal("0.5")) / Decimal(366)
            economic_eligible = conservative_score - PRICE - fee >= MIN_EDGE
            fixed_return = Decimal(1) - PRICE - fee if int(row["outcome_no"]) else -PRICE - fee
            scored.append({
                **row,
                "history_start": window_start.isoformat(),
                "history_cutoff": cutoff.isoformat(),
                "same_band_history_count": len(same_band),
                "same_band_history_no": successes,
                "model_probability_no": str(model_probability),
                "conservative_score_no": str(conservative_score),
                "station_climatology_no": str(station_climatology),
                "conservative_residual": str(Decimal(int(row["outcome_no"])) - conservative_score),
                "fixed_price": str(PRICE),
                "fixed_price_fee": str(fee),
                "fixed_price_edge": str(conservative_score - PRICE - fee),
                "fixed_price_return": str(fixed_return),
                "economic_eligible": economic_eligible,
            })
    candidates: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in scored:
        if row["economic_eligible"]:
            candidates[str(row["market_date"])].append(row)
    selected = [
        sorted(values, key=lambda row: (-Decimal(str(row["conservative_score_no"])), str(row["station_id"])))[0]
        for _, values in sorted(candidates.items())
    ]
    return scored, selected


def reliability(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    output = []
    for low, high, label in RELIABILITY_BANDS:
        selected = [row for row in rows if low <= Decimal(str(row["model_probability_no"])) < high]
        dates = {str(row["market_date"]) for row in selected}
        predicted = sum((Decimal(str(row["model_probability_no"])) for row in selected), Decimal(0)) / Decimal(len(selected)) if selected else None
        observed = Decimal(sum(int(row["outcome_no"]) for row in selected)) / Decimal(len(selected)) if selected else None
        error = abs(predicted - observed) if predicted is not None and observed is not None else None
        populated = len(dates) >= 30
        output.append({
            "band": label,
            "rows": len(selected),
            "independent_dates": len(dates),
            "mean_predicted_no": str(predicted) if predicted is not None else None,
            "observed_no_rate": str(observed) if observed is not None else None,
            "absolute_error": str(error) if error is not None else None,
            "populated": populated,
            "passes": populated and error is not None and error <= Decimal("0.05"),
        })
    return output


def evaluate(rows: list[dict[str, object]]) -> dict[str, object]:
    scored, selected = score_rows(rows)
    model_brier = brier(scored, "model_probability_no")
    raw_brier = brier(scored, "raw_no_rain_proxy")
    climatology_brier = brier(scored, "station_climatology_no")
    reliability_rows = reliability(scored)
    populated = [row for row in reliability_rows if row["populated"]]
    dates = {str(row["market_date"]) for row in selected}
    stations = {str(row["station_id"]) for row in selected}
    station_counts = {station: sum(row["station_id"] == station for row in selected) for station in stations}
    date_counts = {market_date: sum(row["market_date"] == market_date for row in selected) for market_date in dates}
    maximum_station_share = Decimal(max(station_counts.values())) / Decimal(len(selected)) if selected else Decimal(1)
    maximum_date_share = Decimal(max(date_counts.values())) / Decimal(len(selected)) if selected else Decimal(1)
    conservative_lower = clustered_lower(selected, "conservative_residual", 0x50524350)
    return_lower = clustered_lower(selected, "fixed_price_return", 0x50524351)
    holdouts = []
    for excluded in sorted(stations):
        remaining = [row for row in selected if row["station_id"] != excluded]
        mean_return = sum((Decimal(str(row["fixed_price_return"])) for row in remaining), Decimal(0)) / Decimal(len(remaining)) if remaining else None
        holdouts.append({
            "excluded_station_id": excluded,
            "remaining_rows": len(remaining),
            "mean_fixed_price_return": str(mean_return) if mean_return is not None else None,
            "passes": mean_return is not None and mean_return > 0,
        })
    drawdown = maximum_drawdown(selected)
    gates = {
        "minimum_100_independent_dates": len(dates) >= 100,
        "minimum_10_stations": len(stations) >= 10,
        "maximum_station_share": maximum_station_share <= Decimal("0.20"),
        "maximum_date_share": maximum_date_share <= Decimal("0.01"),
        "brier_beats_raw_proxy": model_brier < raw_brier,
        "brier_beats_station_climatology": model_brier < climatology_brier,
        "two_reliable_populated_bands": len(populated) >= 2 and all(row["passes"] for row in populated),
        "clustered_conservative_residual_nonnegative": conservative_lower is not None and conservative_lower >= 0,
        "clustered_fixed_price_return_positive": return_lower is not None and return_lower > 0,
        "leave_one_station_out_positive": len(holdouts) >= 10 and all(row["passes"] for row in holdouts),
        "maximum_drawdown_at_most_10": drawdown <= Decimal(10),
    }
    return {
        "scored_rows": len(scored),
        "selected_rows": len(selected),
        "selected_independent_dates": len(dates),
        "selected_stations": len(stations),
        "selected_station_ids": sorted(stations),
        "maximum_station_share": str(maximum_station_share),
        "maximum_date_share": str(maximum_date_share),
        "model_brier_score": str(model_brier),
        "raw_proxy_brier_score": str(raw_brier),
        "station_climatology_brier_score": str(climatology_brier),
        "reliability_bands": reliability_rows,
        "clustered_95_lower_conservative_residual": str(conservative_lower) if conservative_lower is not None else None,
        "clustered_95_lower_fixed_price_return": str(return_lower) if return_lower is not None else None,
        "maximum_drawdown_dollars": str(drawdown),
        "leave_one_station_out": holdouts,
        "gates": gates,
        "successor_freeze_permitted": all(gates.values()),
        "scored_predictions": scored,
        "selected_predictions": selected,
    }


def main() -> None:
    args = parse_args()
    assert_not_production_host()
    if file_sha256(ROOT / "gfs_mos_precipitation" / "DEVELOPMENT.md") != DEVELOPMENT_SHA256:
        raise ValueError("Development freeze hash is invalid.")
    station_path = ROOT / "stations.json"
    if file_sha256(station_path) != STATIONS_SHA256:
        raise ValueError("Frozen station inventory hash is invalid.")
    stations = json.loads(station_path.read_text(encoding="utf-8"))
    if (
        not isinstance(stations, list)
        or len(stations) != EXPECTED_STATIONS
        or len({row.get("station_id") for row in stations if isinstance(row, dict)}) != EXPECTED_STATIONS
    ):
        raise ValueError("Frozen station inventory is invalid.")
    history_dates, development_dates = assert_frozen_dates()
    all_dates = history_dates + development_dates
    budget = RequestBudget(args.max_requests)
    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    forecasts: dict[tuple[str, str], dict[str, object]] = {}
    forecast_sources = []
    for index, station in enumerate(stations, start=1):
        station_id = str(station["station_id"])
        url = mos_url(station_id)
        payload, headers = fetch(url, budget)
        create_once(output / "raw" / f"iem-gfs-mos-{station_id}.csv", payload)
        atomic_json(output / "raw" / f"iem-gfs-mos-{station_id}.headers.json", headers)
        parsed, fields, duplicates = parse_mos(payload, station, all_dates)
        for row in parsed:
            key = (station_id, str(row["market_date"]))
            if key in forecasts:
                raise ValueError(f"Forecast identity is duplicated for {key[0]}|{key[1]}.")
            forecasts[key] = row
        forecast_sources.append({
            "station_id": station_id,
            "url": url,
            "sha256": sha256(payload),
            "headers": headers,
            "csv_fields": list(fields),
            "selected_exact_duplicate_count": duplicates,
        })
        print(json.dumps({"forecast_station": station_id, "completed_stations": index, "network_requests": budget.used}, sort_keys=True), flush=True)
    expected_rows = EXPECTED_STATIONS * (EXPECTED_HISTORY_DATES + EXPECTED_DEVELOPMENT_DATES)
    if len(forecasts) != expected_rows:
        raise ValueError(f"Forecast coverage is incomplete: {len(forecasts)} != {expected_rows}.")
    isd_payload, isd_headers = fetch(ISD_URL, budget)
    create_once(output / "raw" / "noaa-isd-history.csv", isd_payload)
    atomic_json(output / "raw" / "noaa-isd-history.headers.json", isd_headers)
    identities = parse_isd(isd_payload, stations)
    outcomes: dict[tuple[str, str], dict[str, object]] = {}
    outcome_sources = [{"label": "identity", "url": ISD_URL, "sha256": sha256(isd_payload), "headers": isd_headers}]
    for label, dates in (("history", history_dates), ("development", development_dates)):
        url = outcome_url(identities, dates[0], dates[-1])
        payload, headers = fetch(url, budget)
        create_once(output / "raw" / f"noaa-ncei-{label}-prcp.json", payload)
        atomic_json(output / "raw" / f"noaa-ncei-{label}-prcp.headers.json", headers)
        parsed = parse_outcomes(payload, identities, dates)
        if set(outcomes).intersection(parsed):
            raise ValueError("History and development outcomes overlap.")
        outcomes.update(parsed)
        outcome_sources.append({"label": label, "url": url, "sha256": sha256(payload), "headers": headers})
    rows = []
    for station in stations:
        station_id = str(station["station_id"])
        for market_date in all_dates:
            key = (station_id, market_date.isoformat())
            rows.append({**forecasts[key], **outcomes[key]})
    result = evaluate(rows)
    report = {
        "schema": SCHEMA,
        "identity": IDENTITY,
        "research_only": True,
        "training_and_development_only": True,
        "reserved_evaluation_accessed": False,
        "active_trading_capability_changed": False,
        "production_database_accessed": False,
        "credential_required": False,
        "historical_exchange_prices_inspected": False,
        "exchange_outcomes_inspected": False,
        "development_sha256": DEVELOPMENT_SHA256,
        "stations_sha256": STATIONS_SHA256,
        "request_policy": {
            "maximum_requests": EXPECTED_REQUESTS,
            "actual_requests": budget.used,
            "no_retry": True,
            "stop_on_http_429": True,
        },
        "design": {
            "history_first_date": HISTORY_START.isoformat(),
            "history_last_date": HISTORY_END.isoformat(),
            "history_dates": EXPECTED_HISTORY_DATES,
            "development_first_date": DEVELOPMENT_START.isoformat(),
            "development_last_date": DEVELOPMENT_END.isoformat(),
            "development_dates": EXPECTED_DEVELOPMENT_DATES,
            "reserved_first_date": RESERVED_START.isoformat(),
            "reserved_last_date": RESERVED_END.isoformat(),
            "reserved_dates": EXPECTED_RESERVED_DATES,
            "station_count": EXPECTED_STATIONS,
            "source_model": SOURCE_MODEL,
            "forecast_model": FORECAST_MODEL,
            "forecast_runtime_utc": "12:00:00",
            "forecast_available_by_utc": "20:00:00",
            "rolling_history_dates": 365,
            "outcome_lag_dates": 2,
            "minimum_same_band_history": MIN_HISTORY,
            "fixed_price": str(PRICE),
            "fixed_price_fee": str(exact_fee(PRICE)),
            "minimum_edge": str(MIN_EDGE),
            "bootstrap_samples": BOOTSTRAP_SAMPLES,
        },
        "coverage": {
            "station_dates": len(rows),
            "history_station_dates": EXPECTED_HISTORY_DATES * EXPECTED_STATIONS,
            "development_station_dates": EXPECTED_DEVELOPMENT_DATES * EXPECTED_STATIONS,
            "trace_as_rain_rows": sum(row["measurement_flag"] == "T" for row in rows),
            "four_interval_rows": sum(len(row["selected_interval_ends_utc"]) == 4 for row in rows),
            "five_interval_rows": sum(len(row["selected_interval_ends_utc"]) == 5 for row in rows),
        },
        "station_identities": identities,
        "forecast_sources": forecast_sources,
        "outcome_sources": outcome_sources,
        "evaluation": result,
        "successor_freeze_permitted": result["successor_freeze_permitted"],
        "initial_evidence_passes": False,
        "scale_evidence_passes": False,
        "executable_fill_evidence_passes": False,
        "profitability_claim_permitted": False,
        "rows": rows,
    }
    atomic_json(output / "development.json", report)
    print(json.dumps({
        "ok": True,
        "network_requests": budget.used,
        "coverage": report["coverage"],
        "scored_rows": result["scored_rows"],
        "selected_rows": result["selected_rows"],
        "successor_freeze_permitted": report["successor_freeze_permitted"],
    }, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
