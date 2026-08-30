#!/usr/bin/env python3
"""Capture the frozen NAM MOS v4 calibration and evaluation source rows."""

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
from pathlib import Path


SCHEMA = "nam_mos_v4_station_rolling_capture_v1"
MODEL_IDENTITY = "nam_mos_v4_station_rolling_wilson90_v1"
PREDECLARATION_SHA256 = "d5e958578155c5b7ef3a2b2d59477b256cda5a936249abb4e1ca219cbd74b442"
STATIONS_SHA256 = "297e7cdf081c38212c3a1298d09921dfcb79fff9f3fa3bae6ccafc3b8ed09d12"
IEM_BULK_URL = "https://mesonet.agron.iastate.edu/cgi-bin/request/mos.py"
ISD_URL = "https://www.ncei.noaa.gov/pub/data/noaa/isd-history.csv"
NCEI_URL = "https://www.ncei.noaa.gov/access/services/data/v1"
CALIBRATION_START = dt.date(2021, 2, 15)
CALIBRATION_END = dt.date(2021, 7, 9)
EVALUATION_START = dt.date(2021, 7, 10)
EVALUATION_END = dt.date(2022, 3, 16)
REQUIRED_MOS_FIELDS = {"runtime", "ftime", "model", "n_x", "station"}
SOURCE_MODEL = "NAM"
FORECAST_MODEL = "noaa_nam_v4_station_mos_n_x"
DUPLICATE_COMPARE_FIELDS: set[str] | None = None
EXPECTED_EXACT_DUPLICATES_PER_STATION: int | None = 1
REQUIRE_GLOBAL_OPTIONAL_SCHEMA = True
EXPECTED_CALIBRATION_DATES = 145
EXPECTED_EVALUATION_DATES = 250
EXPECTED_STATION_COUNT = 20
EXPECTED_NETWORK_REQUESTS = 23
SOURCE_FILE_PREFIX = "iem-nam-mos"
REQUIRE_ISD_HISTORY_THROUGH_WINDOW = True
MINIMUM_ISD_HISTORY_END: str | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--max-requests", type=int, required=True)
    parser.add_argument("--stations", default=str(Path(__file__).with_name("stations.json")))
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


def date_range(start: dt.date, end: dt.date) -> list[str]:
    values = []
    current = start
    while current <= end:
        values.append(current.isoformat())
        current += dt.timedelta(days=1)
    return values


def frozen_dates() -> tuple[list[str], list[str]]:
    calibration = date_range(CALIBRATION_START, CALIBRATION_END)
    evaluation = date_range(EVALUATION_START, EVALUATION_END)
    if (
        len(calibration) != EXPECTED_CALIBRATION_DATES
        or len(evaluation) != EXPECTED_EVALUATION_DATES
        or calibration[-1] >= evaluation[0]
    ):
        raise ValueError("Frozen date identity is invalid.")
    return calibration, evaluation


class RequestBudget:
    def __init__(self, maximum: int):
        if maximum != EXPECTED_NETWORK_REQUESTS:
            raise ValueError(f"The frozen request budget is exactly {EXPECTED_NETWORK_REQUESTS}.")
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
    request = urllib.request.Request(url, headers={"User-Agent": "mimir-nam-mos-public-calibration/1"})
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            return response.read(), {key.lower(): value for key, value in response.headers.items()}
    except urllib.error.HTTPError as error:
        if error.code == 429:
            raise ValueError("Frozen acquisition stopped on HTTP 429 without retry.") from error
        raise


def assert_not_production_host() -> None:
    try:
        with urllib.request.urlopen("http://127.0.0.1:8787/api/status", timeout=1) as response:
            payload = json.load(response)
    except (OSError, ValueError, urllib.error.URLError):
        return
    if not isinstance(payload, dict) or not isinstance(payload.get("environment"), str):
        raise ValueError("Local Mimir runtime identity is malformed.")
    if payload["environment"] == "production":
        raise ValueError("NAM MOS evidence acquisition is forbidden on a production Mimir host.")


def mos_url(station_id: str) -> str:
    first_runtime = CALIBRATION_START - dt.timedelta(days=1)
    last_runtime = EVALUATION_END - dt.timedelta(days=1)
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
    return f"{IEM_BULK_URL}?{query}"


def parse_mos(
    payload: bytes,
    station_id: str,
    desired_dates: list[str],
) -> tuple[list[dict[str, object]], tuple[str, ...], int]:
    reader = csv.DictReader(io.StringIO(payload.decode("utf-8")))
    fieldnames = tuple(reader.fieldnames or ())
    if len(fieldnames) != len(set(fieldnames)) or not REQUIRED_MOS_FIELDS.issubset(fieldnames):
        raise ValueError(f"IEM MOS schema drifted for {station_id}.")
    wanted: dict[tuple[str, str], dict[str, str]] = {}
    exact_duplicate_count = 0
    desired = set(desired_dates)
    for row in reader:
        if row.get("station") != station_id or row.get("model") != SOURCE_MODEL:
            raise ValueError(f"IEM MOS identity drifted for {station_id}.")
        try:
            runtime = dt.datetime.strptime(row["runtime"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=dt.timezone.utc)
            forecast_time = dt.datetime.strptime(row["ftime"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=dt.timezone.utc)
        except (KeyError, ValueError) as error:
            raise ValueError(f"IEM MOS clock is malformed for {station_id}.") from error
        if runtime.hour != 12:
            continue
        market_date = (runtime.date() + dt.timedelta(days=1)).isoformat()
        expected_forecast = runtime.date() + dt.timedelta(days=2)
        if market_date not in desired or forecast_time.date() != expected_forecast or forecast_time.hour != 0:
            continue
        if row.get("n_x") in (None, ""):
            raise ValueError(f"IEM MOS maximum temperature is missing for {station_id}|{market_date}.")
        key = (station_id, market_date)
        if key in wanted:
            compare_fields = fieldnames if DUPLICATE_COMPARE_FIELDS is None else tuple(sorted(DUPLICATE_COMPARE_FIELDS))
            if any(row.get(field) != wanted[key].get(field) for field in compare_fields):
                raise ValueError(f"IEM MOS maximum temperature has a conflicting duplicate for {station_id}|{market_date}.")
            exact_duplicate_count += 1
            continue
        try:
            maximum = float(row["n_x"])
        except ValueError as error:
            raise ValueError(f"IEM MOS maximum temperature is malformed for {station_id}|{market_date}.") from error
        if not -100 <= maximum <= 150:
            raise ValueError(f"IEM MOS maximum temperature is outside bounds for {station_id}|{market_date}.")
        wanted[key] = row
    missing = [date for date in desired_dates if (station_id, date) not in wanted]
    if missing:
        raise ValueError(f"IEM MOS coverage is incomplete for {station_id}: {missing[:5]}.")
    return [{
        "station_id": station_id,
        "market_date": market_date,
        "forecast_model": FORECAST_MODEL,
        "forecast_initialized_at": f"{dt.date.fromisoformat(market_date) - dt.timedelta(days=1)}T12:00:00Z",
        "forecast_available_by": f"{dt.date.fromisoformat(market_date) - dt.timedelta(days=1)}T20:00:00Z",
        "forecast_time": f"{dt.date.fromisoformat(market_date) + dt.timedelta(days=1)}T00:00:00Z",
        "forecast_high_f": f"{float(wanted[(station_id, market_date)]['n_x']):.1f}",
    } for market_date in desired_dates], fieldnames, exact_duplicate_count


def require_exact_duplicate_identity(station_id: str, exact_duplicate_count: int) -> None:
    if exact_duplicate_count < 0 or (
        EXPECTED_EXACT_DUPLICATES_PER_STATION is not None
        and exact_duplicate_count != EXPECTED_EXACT_DUPLICATES_PER_STATION
    ):
        raise ValueError(
            f"IEM MOS exact duplicate identity is invalid for {station_id}: {exact_duplicate_count}."
        )


def parse_isd(payload: bytes, stations: list[dict[str, object]]) -> list[dict[str, object]]:
    reader = csv.DictReader(io.StringIO(payload.decode("utf-8")))
    expected = ["USAF", "WBAN", "STATION NAME", "CTRY", "STATE", "ICAO", "LAT", "LON", "ELEV(M)", "BEGIN", "END"]
    if reader.fieldnames != expected:
        raise ValueError("NOAA ISD station-history header is unsupported.")
    rows = list(reader)
    identities = []
    for station in stations:
        matches = sorted(
            [row for row in rows if row["ICAO"] == station["station_id"] and len(row["WBAN"]) == 5 and row["WBAN"] != "99999"],
            key=lambda row: row["END"], reverse=True,
        )
        if not matches:
            raise ValueError(f"NOAA ISD has no exact identity for {station['station_id']}.")
        selected = matches[0]
        required_begin = CALIBRATION_START.strftime("%Y%m%d")
        required_end = EVALUATION_END.strftime("%Y%m%d")
        if (
            selected["BEGIN"] > required_begin
            or (REQUIRE_ISD_HISTORY_THROUGH_WINDOW and selected["END"] < required_end)
            or (
                not REQUIRE_ISD_HISTORY_THROUGH_WINDOW
                and (MINIMUM_ISD_HISTORY_END is None or selected["END"] < MINIMUM_ISD_HISTORY_END)
            )
        ):
            raise ValueError(f"NOAA ISD identity does not cover the frozen window for {station['station_id']}.")
        if abs(float(selected["LAT"]) - float(station["latitude"])) > 0.2 or abs(float(selected["LON"]) - float(station["longitude"])) > 0.2:
            raise ValueError(f"NOAA ISD coordinates conflict for {station['station_id']}.")
        identities.append({
            "station_id": station["station_id"],
            "ghcn_station_id": f"USW000{selected['WBAN']}",
            "usaf": selected["USAF"],
            "wban": selected["WBAN"],
            "station_name": selected["STATION NAME"],
            "latitude": float(selected["LAT"]),
            "longitude": float(selected["LON"]),
            "history_begin": selected["BEGIN"],
            "history_end": selected["END"],
        })
    if len({row["ghcn_station_id"] for row in identities}) != EXPECTED_STATION_COUNT:
        raise ValueError("NOAA station mapping is not one-to-one.")
    return identities


def outcome_url(identities: list[dict[str, object]], start: str, end: str) -> str:
    query = urllib.parse.urlencode({
        "dataset": "daily-summaries",
        "stations": ",".join(str(identity["ghcn_station_id"]) for identity in identities),
        "startDate": start,
        "endDate": end,
        "dataTypes": "TMAX",
        "format": "json",
        "units": "standard",
        "includeAttributes": "true",
        "includeStationName": "true",
        "includeStationLocation": "true",
    })
    return f"{NCEI_URL}?{query}"


def parse_outcomes(payload: bytes, identities: list[dict[str, object]], dates: list[str]) -> dict[tuple[str, str], dict[str, object]]:
    rows = json.loads(payload)
    if not isinstance(rows, list):
        raise ValueError("NOAA NCEI daily summaries response is malformed.")
    by_ghcn = {identity["ghcn_station_id"]: identity for identity in identities}
    desired = set(dates)
    outcomes: dict[tuple[str, str], dict[str, object]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("NOAA NCEI outcome row is malformed.")
        identity = by_ghcn.get(row.get("STATION"))
        market_date = str(row.get("DATE", ""))
        if identity is None or market_date not in desired:
            raise ValueError("NOAA NCEI returned an unexpected station/date.")
        if row.get("TMAX") in (None, ""):
            raise ValueError(f"NOAA NCEI TMAX is missing for {identity['station_id']}|{market_date}.")
        try:
            high = float(row["TMAX"])
        except (TypeError, ValueError) as error:
            raise ValueError(f"NOAA NCEI TMAX is malformed for {identity['station_id']}|{market_date}.") from error
        if not -100 <= high <= 150:
            raise ValueError(f"NOAA NCEI TMAX is outside bounds for {identity['station_id']}|{market_date}.")
        key = (str(identity["station_id"]), market_date)
        if key in outcomes:
            raise ValueError(f"NOAA NCEI TMAX is duplicated for {key[0]}|{key[1]}.")
        outcomes[key] = {
            "high_temp_f": f"{high:.1f}",
            "attributes": str(row.get("TMAX_ATTRIBUTES", "")),
            "source_station_name": str(row.get("NAME") or identity["station_name"]),
        }
    expected = {(str(identity["station_id"]), date) for identity in identities for date in dates}
    missing = sorted(expected - set(outcomes))
    if missing:
        raise ValueError(f"NOAA NCEI outcome coverage is incomplete: {missing[:5]}.")
    if set(outcomes) != expected:
        raise ValueError("NOAA NCEI outcome identity is not exact.")
    return outcomes


def main() -> None:
    args = parse_args()
    assert_not_production_host()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    station_path = Path(args.stations).resolve()
    if file_sha256(station_path) != STATIONS_SHA256:
        raise ValueError("Frozen station inventory hash is invalid.")
    stations = json.loads(station_path.read_text(encoding="utf-8"))
    if (
        not isinstance(stations, list)
        or len(stations) != EXPECTED_STATION_COUNT
        or len({row.get("station_id") for row in stations}) != EXPECTED_STATION_COUNT
    ):
        raise ValueError(f"Frozen station inventory must contain {EXPECTED_STATION_COUNT} unique stations.")
    calibration_dates, evaluation_dates = frozen_dates()
    all_dates = calibration_dates + evaluation_dates
    budget = RequestBudget(args.max_requests)

    forecasts: dict[tuple[str, str], dict[str, object]] = {}
    forecast_sources = []
    mos_schema: tuple[str, ...] | None = None
    for index, station in enumerate(stations, start=1):
        station_id = str(station["station_id"])
        url = mos_url(station_id)
        payload, headers = fetch(url, budget)
        create_once(output_dir / "raw" / f"{SOURCE_FILE_PREFIX}-{station_id}.csv", payload)
        atomic_json(output_dir / "raw" / f"{SOURCE_FILE_PREFIX}-{station_id}.headers.json", headers)
        rows, fieldnames, exact_duplicate_count = parse_mos(payload, station_id, all_dates)
        require_exact_duplicate_identity(station_id, exact_duplicate_count)
        if mos_schema is None:
            mos_schema = fieldnames
        elif REQUIRE_GLOBAL_OPTIONAL_SCHEMA and fieldnames != mos_schema:
            raise ValueError(f"IEM MOS bulk schemas conflict at {station_id}.")
        for row in rows:
            key = (str(row["station_id"]), str(row["market_date"]))
            if key in forecasts:
                raise ValueError(f"Forecast row is duplicated for {key[0]}|{key[1]}.")
            forecasts[key] = row
        forecast_sources.append({
            "station_id": station_id,
            "url": url,
            "sha256": sha256(payload),
            "headers": headers,
            "csv_fields": list(fieldnames),
            "selected_exact_duplicate_count": exact_duplicate_count,
        })
        print(json.dumps({"forecast_station": station_id, "completed_stations": index, "network_requests": budget.used}, sort_keys=True), flush=True)
    expected_rows = (EXPECTED_CALIBRATION_DATES + EXPECTED_EVALUATION_DATES) * EXPECTED_STATION_COUNT
    if len(forecasts) != expected_rows:
        raise ValueError(f"Complete forecast coverage must contain exactly {expected_rows} station/dates.")

    isd_payload, isd_headers = fetch(ISD_URL, budget)
    create_once(output_dir / "raw" / "noaa-isd-history.csv", isd_payload)
    atomic_json(output_dir / "raw" / "noaa-isd-history.headers.json", isd_headers)
    identities = parse_isd(isd_payload, stations)

    outcomes: dict[tuple[str, str], dict[str, object]] = {}
    outcome_sources = []
    for label, dates in (("calibration", calibration_dates), ("evaluation", evaluation_dates)):
        url = outcome_url(identities, dates[0], dates[-1])
        payload, headers = fetch(url, budget)
        create_once(output_dir / "raw" / f"noaa-ncei-{label}-tmax.json", payload)
        atomic_json(output_dir / "raw" / f"noaa-ncei-{label}-tmax.headers.json", headers)
        parsed = parse_outcomes(payload, identities, dates)
        if set(outcomes).intersection(parsed):
            raise ValueError("Calibration and evaluation outcomes overlap.")
        outcomes.update(parsed)
        outcome_sources.append({"label": label, "url": url, "sha256": sha256(payload), "headers": headers})

    rows = []
    for station in stations:
        station_id = str(station["station_id"])
        for market_date in all_dates:
            forecast = forecasts[(station_id, market_date)]
            outcome = outcomes[(station_id, market_date)]
            rows.append({
                **forecast,
                "observed_high_f": outcome["high_temp_f"],
                "residual_f": f"{float(outcome['high_temp_f']) - float(forecast['forecast_high_f']):.1f}",
                "observation_source": "noaa_ncei_daily_summaries_tmax",
                "observation_station_name": outcome["source_station_name"],
                "observation_attributes": outcome["attributes"],
            })
    report = {
        "schema": SCHEMA,
        "model_identity": MODEL_IDENTITY,
        "predeclaration_sha256": PREDECLARATION_SHA256,
        "stations_sha256": STATIONS_SHA256,
        "research_only": True,
        "active_trading_capability_changed": False,
        "production_database_accessed": False,
        "credential_required": False,
        "historical_price_data_inspected": False,
        "request_policy": {"no_retry": True, "stop_on_http_429": True, "maximum_requests": EXPECTED_NETWORK_REQUESTS, "actual_network_requests": budget.used},
        "design": {
            "forecast_model": FORECAST_MODEL,
            "source_model": SOURCE_MODEL,
            "forecast_runtime_utc": "12:00:00",
            "forecast_available_by_utc": "20:00:00",
            "duplicate_policy": "collapse_only_identical_semantic_selected_row",
            "selected_exact_duplicates_per_station": EXPECTED_EXACT_DUPLICATES_PER_STATION,
            "global_optional_schema_required": REQUIRE_GLOBAL_OPTIONAL_SCHEMA,
            "isd_history_through_window_required": REQUIRE_ISD_HISTORY_THROUGH_WINDOW,
            "minimum_isd_history_end": MINIMUM_ISD_HISTORY_END,
            "calibration_first_date": calibration_dates[0],
            "calibration_last_date": calibration_dates[-1],
            "calibration_dates": len(calibration_dates),
            "evaluation_first_date": evaluation_dates[0],
            "evaluation_last_date": evaluation_dates[-1],
            "evaluation_dates": len(evaluation_dates),
            "station_count": EXPECTED_STATION_COUNT,
        },
        "coverage": {
            "requested_dates": 395,
            "complete_dates": 395,
            "station_dates": len(rows),
            "selected_exact_duplicate_rows": sum(
                int(source["selected_exact_duplicate_count"]) for source in forecast_sources
            ),
        },
        "station_identities": identities,
        "forecast_sources": forecast_sources,
        "outcome_sources": [{"url": ISD_URL, "sha256": sha256(isd_payload), "headers": isd_headers}, *outcome_sources],
        "rows": rows,
    }
    atomic_json(output_dir / "capture.json", report)
    print(json.dumps({"ok": True, "coverage": report["coverage"], "network_requests": budget.used}, sort_keys=True))


if __name__ == "__main__":
    main()
