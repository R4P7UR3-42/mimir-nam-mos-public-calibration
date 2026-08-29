#!/usr/bin/env python3
"""Capture the frozen NOAA GEFSv12 dispersion calibration evidence."""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import datetime as dt
import hashlib
import io
import json
import math
import os
import re
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


SCHEMA = "noaa_gefs_v12_dispersion_capture_v1"
ROW_SCHEMA = "noaa_gefs_v12_dispersion_member_row_v1"
MODEL_IDENTITY = "noaa_gefs_v12_five_member_station_z_wilson95_rolling120_lag2_v1"
PREDECLARATION_SHA256 = "7bc055938dcb0332e94dd6486f5249be2fa6eef632cf2d5ee44524274036f9d0"
STATIONS_SHA256 = "297e7cdf081c38212c3a1298d09921dfcb79fff9f3fa3bae6ccafc3b8ed09d12"
BASE = "https://noaa-gefs-retrospective.s3.amazonaws.com"
ISD_URL = "https://www.ncei.noaa.gov/pub/data/noaa/isd-history.csv"
NCEI_URL = "https://www.ncei.noaa.gov/access/services/data/v1"
MEMBERS = ("c00", "p01", "p02", "p03", "p04")
MEMBER_NUMBERS = {member: index for index, member in enumerate(MEMBERS)}
EXPECTED_STEPS = tuple(range(27, 60, 3))
TARGET_START = dt.date(2018, 12, 27)
TARGET_END = dt.date(2019, 12, 31)
EVALUATION_START = dt.date(2019, 4, 26)
EVALUATION_END = dt.date(2019, 12, 31)
STANDARD_OFFSETS = {
    "America/New_York": 5,
    "America/Chicago": 6,
    "America/Denver": 7,
    "America/Phoenix": 7,
    "America/Los_Angeles": 8,
}
INDEX_PATTERN = re.compile(
    r"^(?P<ordinal>[1-9][0-9]*):(?P<offset>[0-9]+):d=(?P<cycle>[0-9]{10}):TMP:2 m above ground:"
    r"(?P<step>[1-9][0-9]*) hour fcst:ENS=(?P<ensemble>.+)$"
)


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def create_once(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError(f"Create-once source changed: {path}.")
        return
    path.write_bytes(payload)


def date_range(start: dt.date, end: dt.date) -> list[dt.date]:
    values: list[dt.date] = []
    current = start
    while current <= end:
        values.append(current)
        current += dt.timedelta(days=1)
    return values


def frozen_dates() -> tuple[list[dt.date], list[dt.date]]:
    targets = date_range(TARGET_START, TARGET_END)
    evaluation = date_range(EVALUATION_START, EVALUATION_END)
    if len(targets) != 370 or len(evaluation) != 250 or evaluation != targets[-250:]:
        raise ValueError("Frozen GEFS calendar identity is invalid.")
    return targets, evaluation


def member_key(initialization: dt.date, member: str) -> str:
    cycle = initialization.strftime("%Y%m%d00")
    return f"GEFSv12/reforecast/{initialization.year}/{cycle}/{member}/Days:1-10/tmp_2m_{cycle}_{member}.grib2"


def parse_index(payload: bytes, initialization: dt.date, member: str) -> list[dict[str, int]]:
    expected_cycle = initialization.strftime("%Y%m%d00")
    expected_ensemble = "low-res ctl" if member == "c00" else f"+{MEMBER_NUMBERS[member]}"
    try:
        lines = payload.decode("utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise ValueError("GEFS index is not UTF-8.") from error
    rows: list[dict[str, int]] = []
    previous_offset = -1
    for line in lines:
        match = INDEX_PATTERN.fullmatch(line)
        if match is None or match.group("cycle") != expected_cycle or match.group("ensemble") != expected_ensemble:
            raise ValueError(f"Unexpected GEFS index identity for {initialization}/{member}.")
        row = {name: int(match.group(name)) for name in ("ordinal", "offset", "step")}
        if row["ordinal"] != len(rows) + 1 or row["offset"] <= previous_offset:
            raise ValueError("GEFS index ordinal/offset order is invalid.")
        previous_offset = row["offset"]
        rows.append(row)
    if not rows:
        raise ValueError("GEFS index is empty.")
    return rows


def exact_range(rows: list[dict[str, int]]) -> tuple[int, int]:
    by_step = {row["step"]: row for row in rows}
    if len(by_step) != len(rows):
        raise ValueError("GEFS index contains duplicate forecast steps.")
    if any(step not in by_step for step in (*EXPECTED_STEPS, 60)):
        raise ValueError("GEFS index is missing a required forecast step.")
    return by_step[27]["offset"], by_step[60]["offset"] - 1


class RequestBudget:
    def __init__(self, maximum: int) -> None:
        if maximum != 3_900:
            raise ValueError("The frozen GEFS request ceiling is exactly 3,900.")
        self.maximum = maximum
        self.used = 0
        self.lock = threading.Lock()

    def reserve(self) -> int:
        with self.lock:
            if self.used >= self.maximum:
                raise ValueError("Frozen GEFS request ceiling exhausted.")
            self.used += 1
            return self.used


def fetch(budget: RequestBudget, url: str, headers: dict[str, str] | None = None) -> tuple[bytes, dict[str, str], int]:
    budget.reserve()
    request_headers = {"User-Agent": "mimir-public-gefs-dispersion/1"}
    request_headers.update(headers or {})
    request = urllib.request.Request(url, headers=request_headers)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read(), {key.lower(): value for key, value in response.headers.items()}, response.status
    except urllib.error.HTTPError as error:
        if error.code == 429:
            raise ValueError("GEFS/NOAA source returned terminal HTTP 429 without retry.") from error
        raise ValueError(f"GEFS/NOAA source returned HTTP {error.code} without retry.") from error
    except urllib.error.URLError as error:
        raise ValueError("GEFS/NOAA source request failed without retry.") from error


def fetch_member(budget: RequestBudget, initialization: dt.date, member: str) -> dict[str, object]:
    key = member_key(initialization, member)
    index_payload, _, index_status = fetch(budget, f"{BASE}/{key}.idx")
    if index_status != 200:
        raise ValueError("GEFS index status changed.")
    start, end = exact_range(parse_index(index_payload, initialization, member))
    payload, headers, status = fetch(budget, f"{BASE}/{key}", {"Range": f"bytes={start}-{end}"})
    content_range = headers.get("content-range", "")
    match = re.fullmatch(rf"bytes {start}-{end}/(?P<length>[1-9][0-9]*)", content_range)
    etag = headers.get("etag", "").strip('"')
    if status != 206 or match is None or len(payload) != end - start + 1 or not re.fullmatch(r"[0-9a-f]{32}", etag):
        raise ValueError(f"GEFS range identity changed for {initialization}/{member}.")
    return {
        "initialization": initialization,
        "member": member,
        "key": key,
        "index_sha256": sha256(index_payload),
        "range": f"bytes={start}-{end}",
        "range_sha256": sha256(payload),
        "etag": etag,
        "object_length": int(match.group("length")),
        "payload": payload,
    }


def bounded_results(
    executor: concurrent.futures.Executor,
    items: list[tuple[object, ...]],
    worker: object,
    concurrency: int,
):
    """Yield completed work while retaining no more than the declared concurrency."""
    if concurrency <= 0:
        raise ValueError("Bounded GEFS concurrency must be positive.")
    if not callable(worker):
        raise ValueError("Bounded GEFS worker must be callable.")
    iterator = iter(items)
    pending: dict[concurrent.futures.Future[object], tuple[object, ...]] = {}

    def submit_one() -> bool:
        try:
            item = next(iterator)
        except StopIteration:
            return False
        pending[executor.submit(worker, *item)] = item
        return True

    for _ in range(min(concurrency, len(items))):
        submit_one()
    while pending:
        completed, _ = concurrent.futures.wait(
            tuple(pending),
            return_when=concurrent.futures.FIRST_COMPLETED,
        )
        for future in completed:
            item = pending.pop(future)
            result = future.result()
            yield item, result
            submit_one()


def decode_member(source: dict[str, object], stations: list[dict[str, object]]) -> dict[str, object]:
    import eccodes

    initialization = source["initialization"]
    member = str(source["member"])
    if not isinstance(initialization, dt.date):
        raise ValueError("GEFS initialization is malformed.")
    messages: dict[int, dict[str, dict[str, float]]] = {}
    with tempfile.TemporaryFile() as stream:
        stream.write(source["payload"])
        stream.seek(0)
        while True:
            handle = eccodes.codes_grib_new_from_file(stream)
            if handle is None:
                break
            try:
                step = int(eccodes.codes_get(handle, "step"))
                number = int(eccodes.codes_get(handle, "number")) if eccodes.codes_is_defined(handle, "number") else None
                expected_number = MEMBER_NUMBERS[member]
                number_matches = number == expected_number or (member == "c00" and number is None)
                identity = (
                    str(eccodes.codes_get(handle, "shortName")),
                    str(eccodes.codes_get(handle, "typeOfLevel")),
                    int(eccodes.codes_get(handle, "level")),
                    str(eccodes.codes_get(handle, "gridType")),
                    int(eccodes.codes_get(handle, "dataDate")),
                    int(eccodes.codes_get(handle, "dataTime")),
                )
                expected = ("2t", "heightAboveGround", 2, "regular_ll", int(initialization.strftime("%Y%m%d")), 0)
                if identity != expected or not number_matches or step not in EXPECTED_STEPS or step in messages:
                    raise ValueError(f"Unexpected decoded GEFS identity for {initialization}/{member}/{step}: {identity}/{number}.")
                station_values: dict[str, dict[str, float]] = {}
                for station in stations:
                    nearest = eccodes.codes_grib_find_nearest(
                        handle,
                        float(station["latitude"]),
                        float(station["longitude"]),
                        is_lsm=False,
                        npoints=1,
                    )[0]
                    kelvin = float(nearest["value"])
                    distance = float(nearest["distance"])
                    if not math.isfinite(kelvin) or not 180 <= kelvin <= 340 or not math.isfinite(distance) or distance > 25:
                        raise ValueError(f"GEFS station value is invalid for {station['station_id']}.")
                    station_values[str(station["station_id"])] = {
                        "kelvin": kelvin,
                        "grid_latitude": float(nearest["lat"]),
                        "grid_longitude": float(nearest["lon"]),
                        "distance_km": distance,
                    }
                messages[step] = station_values
            finally:
                eccodes.codes_release(handle)
    if tuple(sorted(messages)) != EXPECTED_STEPS:
        raise ValueError(f"Decoded GEFS steps are incomplete for {initialization}/{member}.")

    highs = []
    for station in stations:
        station_id = str(station["station_id"])
        offset = STANDARD_OFFSETS.get(str(station["time_zone"]))
        if offset is None:
            raise ValueError(f"Unsupported local-standard offset for {station_id}.")
        start = 24 + offset
        selected_steps = [step for step in EXPECTED_STEPS if start <= step < start + 24]
        if len(selected_steps) != 8:
            raise ValueError(f"GEFS sampled-day coverage is invalid for {station_id}: {selected_steps}.")
        selected = [messages[step][station_id] for step in selected_steps]
        grids = {(row["grid_latitude"], row["grid_longitude"], row["distance_km"]) for row in selected}
        if len(grids) != 1:
            raise ValueError(f"GEFS nearest-grid identity drifted for {station_id}.")
        grid_latitude, grid_longitude, distance_km = grids.pop()
        highs.append({
            "station_id": station_id,
            "selected_steps": selected_steps,
            "member_high_kelvin": max(row["kelvin"] for row in selected),
            "grid_latitude": grid_latitude,
            "grid_longitude": grid_longitude,
            "distance_km": distance_km,
        })
    target = initialization + dt.timedelta(days=1)
    return {
        "schema": ROW_SCHEMA,
        "model_identity": MODEL_IDENTITY,
        "initialization_date": initialization.isoformat(),
        "target_market_date": target.isoformat(),
        "member": member,
        "member_number": MEMBER_NUMBERS[member],
        "source": {key: value for key, value in source.items() if key not in {"payload", "initialization", "member"}},
        "station_highs": highs,
    }


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
            key=lambda row: row["END"],
            reverse=True,
        )
        if not matches:
            raise ValueError(f"NOAA ISD has no exact identity for {station['station_id']}.")
        selected = matches[0]
        if selected["BEGIN"] > "20181227" or selected["END"] < "20191231":
            raise ValueError(f"NOAA ISD identity does not cover the frozen interval for {station['station_id']}.")
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
    if len(identities) != 20 or len({row["ghcn_station_id"] for row in identities}) != 20:
        raise ValueError("NOAA station mapping is not one-to-one.")
    return identities


def outcome_url(identities: list[dict[str, object]], start: dt.date, end: dt.date) -> str:
    query = urllib.parse.urlencode({
        "dataset": "daily-summaries",
        "stations": ",".join(str(identity["ghcn_station_id"]) for identity in identities),
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "dataTypes": "TMAX",
        "format": "json",
        "units": "standard",
        "includeAttributes": "true",
        "includeStationName": "true",
        "includeStationLocation": "true",
    })
    return f"{NCEI_URL}?{query}"


def parse_outcomes(payloads: list[bytes], identities: list[dict[str, object]], targets: list[dt.date]) -> list[dict[str, object]]:
    by_ghcn = {str(identity["ghcn_station_id"]): identity for identity in identities}
    desired_dates = {date.isoformat() for date in targets}
    outcomes: dict[tuple[str, str], dict[str, object]] = {}
    for payload in payloads:
        rows = json.loads(payload)
        if not isinstance(rows, list):
            raise ValueError("NOAA Daily Summaries payload is malformed.")
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("NOAA outcome row is malformed.")
            identity = by_ghcn.get(str(row.get("STATION", "")))
            market_date = str(row.get("DATE", ""))
            if identity is None or market_date not in desired_dates:
                raise ValueError("NOAA outcome identity is outside the frozen set.")
            key = (str(identity["station_id"]), market_date)
            if key in outcomes or row.get("TMAX") in (None, ""):
                raise ValueError(f"NOAA TMAX is missing or duplicated for {key}.")
            high = float(row["TMAX"])
            if not math.isfinite(high) or not -100 <= high <= 150:
                raise ValueError(f"NOAA TMAX is malformed for {key}.")
            outcomes[key] = {
                "station_id": key[0],
                "market_date": key[1],
                "high_temp_f": high,
                "attributes": str(row.get("TMAX_ATTRIBUTES", "")),
                "source_station_name": str(row.get("NAME") or identity["station_name"]),
            }
    expected = {(str(identity["station_id"]), date.isoformat()) for identity in identities for date in targets}
    if set(outcomes) != expected:
        missing = sorted(expected - set(outcomes))
        raise ValueError(f"NOAA outcome coverage is incomplete: {missing[:5]}.")
    return [outcomes[key] for key in sorted(outcomes)]


def row_path(output: Path, initialization: dt.date, member: str) -> Path:
    return output / "rows" / initialization.isoformat() / f"{member}.json"


def valid_existing_row(path: Path, initialization: dt.date, member: str) -> bool:
    if not path.exists():
        return False
    row = json.loads(path.read_text(encoding="utf-8"))
    return (
        row.get("schema") == ROW_SCHEMA
        and row.get("model_identity") == MODEL_IDENTITY
        and row.get("initialization_date") == initialization.isoformat()
        and row.get("target_market_date") == (initialization + dt.timedelta(days=1)).isoformat()
        and row.get("member") == member
        and row.get("member_number") == MEMBER_NUMBERS[member]
        and isinstance(row.get("station_highs"), list)
        and len(row["station_highs"]) == 20
        and {item.get("station_id") for item in row["station_highs"]} == set(FROZEN_STATION_IDS)
    )


FROZEN_STATION_IDS: tuple[str, ...] = ()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--max-requests", type=int, required=True)
    parser.add_argument("--concurrency", type=int, required=True)
    parser.add_argument("--stations", default=str(Path(__file__).parent.parent / "stations.json"))
    return parser.parse_args()


def main() -> None:
    global FROZEN_STATION_IDS
    args = parse_args()
    if args.concurrency != 10:
        raise ValueError("The frozen GEFS concurrency is exactly ten.")
    if Path("/var/lib/mimir/mimir.sqlite3").exists() or os.environ.get("MIMIR_ENV") == "production":
        raise ValueError("GEFS research capture refuses a production host.")
    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    stations_path = Path(args.stations).resolve()
    if sha256(stations_path.read_bytes()) != STATIONS_SHA256:
        raise ValueError("Frozen station inventory hash is invalid.")
    stations = json.loads(stations_path.read_text(encoding="utf-8"))
    if not isinstance(stations, list) or len(stations) != 20:
        raise ValueError("Frozen station inventory is malformed.")
    FROZEN_STATION_IDS = tuple(str(station["station_id"]) for station in stations)
    if len(set(FROZEN_STATION_IDS)) != 20:
        raise ValueError("Frozen station identifiers are not unique.")
    targets, evaluation = frozen_dates()
    budget = RequestBudget(args.max_requests)

    isd_payload, _, isd_status = fetch(budget, ISD_URL)
    if isd_status != 200:
        raise ValueError("NOAA ISD status changed.")
    create_once(output / "sources" / "isd-history.csv", isd_payload)
    identities = parse_isd(isd_payload, stations)

    tasks = []
    for target in targets:
        initialization = target - dt.timedelta(days=1)
        for member in MEMBERS:
            path = row_path(output, initialization, member)
            if not valid_existing_row(path, initialization, member):
                tasks.append((initialization, member, path))
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        fetch_items = [(budget, initialization, member) for initialization, member, _ in tasks]
        targets = {(initialization, member): path for initialization, member, path in tasks}
        for item, source in bounded_results(executor, fetch_items, fetch_member, args.concurrency):
            _, initialization, member = item
            path = targets[(initialization, member)]
            row = decode_member(source, stations)
            encoded = (json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n").encode()
            create_once(path, encoded)
            print(json.dumps({"captured": f"{initialization}/{member}", "requests": budget.used}), flush=True)

    row_manifest = []
    for target in targets:
        initialization = target - dt.timedelta(days=1)
        for member in MEMBERS:
            path = row_path(output, initialization, member)
            if not valid_existing_row(path, initialization, member):
                raise ValueError(f"GEFS capture row is missing after acquisition: {initialization}/{member}.")
            relative = path.relative_to(output).as_posix()
            row_manifest.append({"path": relative, "sha256": sha256(path.read_bytes())})

    split = dt.date(2019, 7, 14)
    outcome_payloads = []
    outcome_sources = []
    for index, (start, end) in enumerate(((TARGET_START, split - dt.timedelta(days=1)), (split, TARGET_END)), start=1):
        url = outcome_url(identities, start, end)
        payload, _, status = fetch(budget, url)
        if status != 200:
            raise ValueError("NOAA Daily Summaries status changed.")
        create_once(output / "sources" / f"outcomes-{index}.json", payload)
        outcome_payloads.append(payload)
        outcome_sources.append({"url": url, "sha256": sha256(payload), "start": start.isoformat(), "end": end.isoformat()})
    outcomes = parse_outcomes(outcome_payloads, identities, targets)
    atomic_json(output / "outcomes.json", {"schema": "noaa_gefs_v12_dispersion_outcomes_v1", "rows": outcomes})

    report = {
        "schema": SCHEMA,
        "model_identity": MODEL_IDENTITY,
        "predeclaration_sha256": PREDECLARATION_SHA256,
        "research_only": True,
        "active_trading_capability_changed": False,
        "production_database_accessed": False,
        "request_policy": {"maximum": 3_900, "performed": budget.used, "concurrency": 10, "retry_count": 0},
        "design": {
            "members": list(MEMBERS),
            "expected_steps": list(EXPECTED_STEPS),
            "target_start": TARGET_START.isoformat(),
            "target_end": TARGET_END.isoformat(),
            "evaluation_start": EVALUATION_START.isoformat(),
            "evaluation_end": EVALUATION_END.isoformat(),
        },
        "coverage": {
            "target_dates": len(targets),
            "evaluation_dates": len(evaluation),
            "stations": len(stations),
            "member_rows": len(row_manifest),
            "outcomes": len(outcomes),
        },
        "station_identities": identities,
        "row_manifest": row_manifest,
        "outcome_sources": outcome_sources,
        "outcomes_sha256": sha256((output / "outcomes.json").read_bytes()),
    }
    atomic_json(output / "capture.json", report)
    print(json.dumps({key: report[key] for key in ("schema", "model_identity", "request_policy", "coverage")}, sort_keys=True))


if __name__ == "__main__":
    main()
