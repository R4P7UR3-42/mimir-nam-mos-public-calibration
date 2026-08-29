#!/usr/bin/env python3
"""Verify the frozen GEFS method against one exact operational NOAA cycle."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import math
import os
import re
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path


SCHEMA = "noaa_gefs_v12_operational_compatibility_v1"
MODEL_IDENTITY = "noaa_gefs_v12_five_member_station_z_wilson95_rolling120_lag2_v1"
BASE = "https://noaa-gefs-pds.s3.amazonaws.com"
INITIALIZATION = "2026082800"
MEMBERS = ("c00", "p01", "p02", "p03", "p04")
MEMBER_NUMBERS = {member: index for index, member in enumerate(MEMBERS)}
EXPECTED_STEPS = tuple(range(27, 60, 3))
STANDARD_OFFSETS = {
    "America/New_York": 5,
    "America/Chicago": 6,
    "America/Denver": 7,
    "America/Phoenix": 7,
    "America/Los_Angeles": 8,
}
STATIONS_SHA256 = "297e7cdf081c38212c3a1298d09921dfcb79fff9f3fa3bae6ccafc3b8ed09d12"
INDEX_PATTERN = re.compile(
    r"^(?P<ordinal>[1-9][0-9]*):(?P<offset>[0-9]+):d=(?P<cycle>[0-9]{10}):(?P<descriptor>.+)$"
)


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    if path.exists():
        if path.read_bytes() != encoded:
            raise ValueError(f"Create-once operational evidence changed: {path}.")
        return
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temporary.write_bytes(encoded)
    os.replace(temporary, path)


def object_key(member: str, step: int) -> str:
    prefix = "gec" if member == "c00" else "gep"
    suffix = member[1:]
    return (
        f"gefs.{INITIALIZATION[:8]}/00/atmos/pgrb2sp25/"
        f"{prefix}{suffix}.t00z.pgrb2s.0p25.f{step:03d}"
    )


def parse_field_range(payload: bytes, member: str, step: int) -> tuple[int, int]:
    expected_ensemble = "low-res ctl" if member == "c00" else f"+{MEMBER_NUMBERS[member]}"
    expected_descriptor = f"TMP:2 m above ground:{step} hour fcst:ENS={expected_ensemble}"
    rows: list[tuple[int, int, str]] = []
    try:
        lines = payload.decode("utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise ValueError("Operational GEFS index is not UTF-8.") from error
    previous_offset = -1
    for line in lines:
        match = INDEX_PATTERN.fullmatch(line)
        if match is None or match.group("cycle") != INITIALIZATION:
            raise ValueError(f"Operational GEFS index identity changed: {line}.")
        ordinal = int(match.group("ordinal"))
        offset = int(match.group("offset"))
        if ordinal != len(rows) + 1 or offset <= previous_offset:
            raise ValueError("Operational GEFS index order is invalid.")
        previous_offset = offset
        rows.append((ordinal, offset, match.group("descriptor")))
    matches = [index for index, row in enumerate(rows) if row[2] == expected_descriptor]
    if len(matches) != 1:
        raise ValueError(f"Operational GEFS 2 m temperature identity is missing or ambiguous for {member}/{step}.")
    index = matches[0]
    if index + 1 >= len(rows):
        raise ValueError("Operational GEFS temperature field has no exact end boundary.")
    start = rows[index][1]
    end = rows[index + 1][1] - 1
    if start < 0 or end < start:
        raise ValueError("Operational GEFS byte range is invalid.")
    return start, end


class RequestBudget:
    def __init__(self, maximum: int) -> None:
        if maximum != 110:
            raise ValueError("The operational canary request ceiling is exactly 110.")
        self.maximum = maximum
        self.used = 0
        self.lock = threading.Lock()

    def reserve(self) -> None:
        with self.lock:
            if self.used >= self.maximum:
                raise ValueError("Operational GEFS request ceiling exhausted.")
            self.used += 1


def fetch(budget: RequestBudget, url: str, headers: dict[str, str] | None = None) -> tuple[bytes, dict[str, str], int]:
    budget.reserve()
    request_headers = {"User-Agent": "mimir-public-gefs-operational-canary/1"}
    request_headers.update(headers or {})
    request = urllib.request.Request(url, headers=request_headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read(), {key.lower(): value for key, value in response.headers.items()}, response.status
    except urllib.error.HTTPError as error:
        if error.code == 429:
            raise ValueError("Operational GEFS source returned terminal HTTP 429 without retry.") from error
        raise ValueError(f"Operational GEFS source returned HTTP {error.code} without retry.") from error
    except urllib.error.URLError as error:
        raise ValueError("Operational GEFS source request failed without retry.") from error


def fetch_field(budget: RequestBudget, member: str, step: int) -> dict[str, object]:
    key = object_key(member, step)
    index_payload, _, index_status = fetch(budget, f"{BASE}/{key}.idx")
    if index_status != 200:
        raise ValueError("Operational GEFS index status changed.")
    start, end = parse_field_range(index_payload, member, step)
    payload, headers, status = fetch(budget, f"{BASE}/{key}", {"Range": f"bytes={start}-{end}"})
    content_range = headers.get("content-range", "")
    match = re.fullmatch(rf"bytes {start}-{end}/(?P<length>[1-9][0-9]*)", content_range)
    etag = headers.get("etag", "").strip('"')
    if (
        status != 206
        or match is None
        or len(payload) != end - start + 1
        or not re.fullmatch(r"[0-9a-f]{32}", etag)
    ):
        raise ValueError(f"Operational GEFS range identity changed for {member}/{step}.")
    return {
        "member": member,
        "step": step,
        "key": key,
        "index_sha256": sha256(index_payload),
        "range": f"bytes={start}-{end}",
        "range_sha256": sha256(payload),
        "etag": etag,
        "object_length": int(match.group("length")),
        "payload": payload,
    }


def decode_field(source: dict[str, object], stations: list[dict[str, object]]) -> dict[str, object]:
    import eccodes

    member = str(source["member"])
    step = int(source["step"])
    with tempfile.TemporaryFile() as stream:
        stream.write(source["payload"])
        stream.seek(0)
        handle = eccodes.codes_grib_new_from_file(stream)
        if handle is None:
            raise ValueError("Operational GEFS range contains no GRIB message.")
        try:
            number = int(eccodes.codes_get(handle, "number")) if eccodes.codes_is_defined(handle, "number") else None
            expected_number = MEMBER_NUMBERS[member]
            identity = (
                str(eccodes.codes_get(handle, "shortName")),
                str(eccodes.codes_get(handle, "typeOfLevel")),
                int(eccodes.codes_get(handle, "level")),
                str(eccodes.codes_get(handle, "gridType")),
                int(eccodes.codes_get(handle, "step")),
                int(eccodes.codes_get(handle, "dataDate")),
                int(eccodes.codes_get(handle, "dataTime")),
            )
            if identity != ("2t", "heightAboveGround", 2, "regular_ll", step, 20260828, 0):
                raise ValueError(f"Operational GEFS decoded identity changed: {identity}.")
            if number != expected_number and not (member == "c00" and number is None):
                raise ValueError(f"Operational GEFS member number changed for {member}: {number}.")
            values = {}
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
                if not math.isfinite(kelvin) or not 180 <= kelvin <= 340:
                    raise ValueError(f"Operational GEFS temperature is invalid for {station['station_id']}.")
                if not math.isfinite(distance) or distance > 25:
                    raise ValueError(f"Operational GEFS grid distance is invalid for {station['station_id']}.")
                values[str(station["station_id"])] = {
                    "temperature_kelvin": kelvin,
                    "grid_latitude": float(nearest["lat"]),
                    "grid_longitude": float(nearest["lon"]),
                    "distance_km": distance,
                }
            extra_handle = eccodes.codes_grib_new_from_file(stream)
            if extra_handle is not None:
                eccodes.codes_release(extra_handle)
                raise ValueError("Operational GEFS exact range contains multiple messages.")
        finally:
            eccodes.codes_release(handle)
    return {"member": member, "step": step, "values": values}


def summarize(decoded: list[dict[str, object]], stations: list[dict[str, object]]) -> list[dict[str, object]]:
    by_member_step = {(str(row["member"]), int(row["step"])): row["values"] for row in decoded}
    if set(by_member_step) != {(member, step) for member in MEMBERS for step in EXPECTED_STEPS}:
        raise ValueError("Operational GEFS decoded coverage is incomplete.")
    rows = []
    for member in MEMBERS:
        highs = []
        for station in stations:
            station_id = str(station["station_id"])
            offset = STANDARD_OFFSETS.get(str(station["time_zone"]))
            if offset is None:
                raise ValueError(f"Unsupported standard-time offset for {station_id}.")
            start = 24 + offset
            selected_steps = [step for step in EXPECTED_STEPS if start <= step < start + 24]
            if len(selected_steps) != 8:
                raise ValueError(f"Operational GEFS sampled-day coverage is invalid for {station_id}.")
            values = [by_member_step[(member, step)][station_id] for step in selected_steps]
            grids = {
                (value["grid_latitude"], value["grid_longitude"], value["distance_km"])
                for value in values
            }
            if len(grids) != 1:
                raise ValueError(f"Operational GEFS grid identity drifted for {station_id}.")
            grid_latitude, grid_longitude, distance_km = grids.pop()
            highs.append({
                "station_id": station_id,
                "selected_steps": selected_steps,
                "member_high_kelvin": max(value["temperature_kelvin"] for value in values),
                "grid_latitude": grid_latitude,
                "grid_longitude": grid_longitude,
                "distance_km": distance_km,
            })
        rows.append({"member": member, "member_number": MEMBER_NUMBERS[member], "station_highs": highs})
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-requests", type=int, required=True)
    parser.add_argument("--concurrency", type=int, required=True)
    parser.add_argument("--stations", default=str(Path(__file__).parent.parent / "stations.json"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.concurrency != 10:
        raise ValueError("The operational canary concurrency is exactly ten.")
    if Path("/var/lib/mimir/mimir.sqlite3").exists() or os.environ.get("MIMIR_ENV") == "production":
        raise ValueError("Operational GEFS canary refuses a production host.")
    stations_path = Path(args.stations).resolve()
    if sha256(stations_path.read_bytes()) != STATIONS_SHA256:
        raise ValueError("Frozen station inventory hash is invalid.")
    stations = json.loads(stations_path.read_text(encoding="utf-8"))
    if not isinstance(stations, list) or len(stations) != 20:
        raise ValueError("Frozen station inventory is malformed.")
    budget = RequestBudget(args.max_requests)
    sources: list[dict[str, object]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = [
            executor.submit(fetch_field, budget, member, step)
            for member in MEMBERS
            for step in EXPECTED_STEPS
        ]
        for future in concurrent.futures.as_completed(futures):
            sources.append(future.result())
    decoded = [decode_field(source, stations) for source in sources]
    source_manifest = [
        {key: value for key, value in source.items() if key != "payload"}
        for source in sorted(sources, key=lambda row: (str(row["member"]), int(row["step"])))
    ]
    report = {
        "schema": SCHEMA,
        "model_identity": MODEL_IDENTITY,
        "initialization": INITIALIZATION,
        "target_market_date": "2026-08-29",
        "members": list(MEMBERS),
        "steps": list(EXPECTED_STEPS),
        "request_policy": {"maximum": 110, "performed": budget.used, "concurrency": 10, "retry_count": 0},
        "source_manifest": source_manifest,
        "member_highs": summarize(decoded, stations),
        "research_only": True,
        "active_trading_capability_changed": False,
        "production_database_accessed": False,
        "calibration_evidence": False,
        "executable_economics_evidence": False,
        "trading_authority": False,
    }
    atomic_json(Path(args.output).resolve(), report)
    print(json.dumps({
        "schema": report["schema"],
        "initialization": report["initialization"],
        "requests": report["request_policy"],
        "members": len(report["member_highs"]),
        "stations": len(stations),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
