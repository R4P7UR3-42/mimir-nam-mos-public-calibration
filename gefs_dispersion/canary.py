#!/usr/bin/env python3
"""Verify one exact NOAA GEFSv12 reforecast range and decode station values."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import urllib.error
import urllib.request
from pathlib import Path


BASE = "https://noaa-gefs-retrospective.s3.amazonaws.com"
KEY = "GEFSv12/reforecast/2019/2019082900/c00/Days:1-10/tmp_2m_2019082900_c00.grib2"
INDEX_SHA256 = "853fa5fcf71ecc705df245f0203458cc0760a9b0c63d701c6e5549feef22f619"
OBJECT_ETAG = "fff7e6bf2e3669e063b7840ad8763550"
OBJECT_LENGTH = 34_727_288
EXPECTED_STEPS = tuple(range(27, 60, 3))
STATIONS_SHA256 = "297e7cdf081c38212c3a1298d09921dfcb79fff9f3fa3bae6ccafc3b8ed09d12"
INDEX_PATTERN = re.compile(
    r"^(?P<ordinal>[1-9][0-9]*):(?P<offset>[0-9]+):d=2019082900:TMP:2 m above ground:"
    r"(?P<step>[1-9][0-9]*) hour fcst:ENS=low-res ctl$"
)


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def create_once(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError(f"Create-once evidence changed: {path}.")
        return
    path.write_bytes(payload)


def parse_index(payload: bytes) -> list[dict[str, int]]:
    try:
        lines = payload.decode("utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise ValueError("GEFS index is not UTF-8.") from error
    rows: list[dict[str, int]] = []
    previous_offset = -1
    for line in lines:
        match = INDEX_PATTERN.fullmatch(line)
        if match is None:
            raise ValueError(f"Unexpected GEFS index identity: {line}.")
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
    start = by_step[EXPECTED_STEPS[0]]["offset"]
    end = by_step[60]["offset"] - 1
    if start < 0 or end < start:
        raise ValueError("GEFS byte range is invalid.")
    return start, end


class Client:
    def __init__(self, max_requests: int) -> None:
        self.max_requests = max_requests
        self.requests = 0

    def request(self, url: str, method: str = "GET", headers: dict[str, str] | None = None) -> tuple[bytes, dict[str, str], int]:
        if self.requests >= self.max_requests:
            raise ValueError("GEFS canary request budget exhausted.")
        self.requests += 1
        request_headers = {"User-Agent": "mimir-public-gefs-canary/1"}
        request_headers.update(headers or {})
        request = urllib.request.Request(url, method=method, headers=request_headers)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read(), {key.lower(): value for key, value in response.headers.items()}, response.status
        except urllib.error.HTTPError as error:
            if error.code == 429:
                raise ValueError("GEFS source returned terminal HTTP 429.") from error
            raise ValueError(f"GEFS source returned HTTP {error.code} without retry.") from error
        except urllib.error.URLError as error:
            raise ValueError("GEFS source request failed without retry.") from error


def decode_range(path: Path, stations: list[dict[str, object]]) -> list[dict[str, object]]:
    import eccodes

    messages: list[dict[str, object]] = []
    with path.open("rb") as source:
        while True:
            handle = eccodes.codes_grib_new_from_file(source)
            if handle is None:
                break
            try:
                identity = {
                    "short_name": str(eccodes.codes_get(handle, "shortName")),
                    "level_type": str(eccodes.codes_get(handle, "typeOfLevel")),
                    "level": int(eccodes.codes_get(handle, "level")),
                    "grid_type": str(eccodes.codes_get(handle, "gridType")),
                    "step": int(eccodes.codes_get(handle, "step")),
                    "data_date": int(eccodes.codes_get(handle, "dataDate")),
                    "data_time": int(eccodes.codes_get(handle, "dataTime")),
                }
                if identity != {
                    "short_name": "2t",
                    "level_type": "heightAboveGround",
                    "level": 2,
                    "grid_type": "regular_ll",
                    "step": identity["step"],
                    "data_date": 20190829,
                    "data_time": 0,
                } or identity["step"] not in EXPECTED_STEPS:
                    raise ValueError(f"Unexpected decoded GEFS identity: {identity}.")
                values = []
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
                    if not math.isfinite(kelvin) or not 180.0 <= kelvin <= 340.0:
                        raise ValueError("GEFS station temperature is invalid.")
                    if not math.isfinite(distance) or distance > 25.0:
                        raise ValueError("GEFS nearest-grid distance exceeds 25 km.")
                    values.append({
                        "station_id": station["station_id"],
                        "grid_latitude": float(nearest["lat"]),
                        "grid_longitude": float(nearest["lon"]),
                        "distance_km": distance,
                        "temperature_kelvin": kelvin,
                    })
                messages.append({**identity, "values": values})
            finally:
                eccodes.codes_release(handle)
    steps = [int(message["step"]) for message in messages]
    if steps != list(EXPECTED_STEPS):
        raise ValueError(f"Decoded GEFS steps are incomplete or out of order: {steps}.")
    return messages


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--max-requests", type=int, required=True)
    parser.add_argument("--stations", default=str(Path(__file__).parent.parent / "stations.json"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.max_requests != 3:
        raise ValueError("The frozen canary requires exactly three requests.")
    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    stations_path = Path(args.stations).resolve()
    if sha256(stations_path.read_bytes()) != STATIONS_SHA256:
        raise ValueError("Frozen station inventory hash is invalid.")
    stations = json.loads(stations_path.read_text(encoding="utf-8"))
    if not isinstance(stations, list) or len(stations) != 20:
        raise ValueError("Frozen station inventory is malformed.")

    client = Client(args.max_requests)
    index_payload, index_headers, index_status = client.request(f"{BASE}/{KEY}.idx")
    if index_status != 200 or sha256(index_payload) != INDEX_SHA256:
        raise ValueError("GEFS canary index identity changed.")
    rows = parse_index(index_payload)
    start, end = exact_range(rows)

    _, head_headers, head_status = client.request(f"{BASE}/{KEY}", method="HEAD")
    if head_status != 200:
        raise ValueError("GEFS canary HEAD status changed.")
    etag = head_headers.get("etag", "").strip('"')
    if etag != OBJECT_ETAG or int(head_headers.get("content-length", "-1")) != OBJECT_LENGTH:
        raise ValueError("GEFS canary object identity changed.")

    payload, range_headers, range_status = client.request(
        f"{BASE}/{KEY}", headers={"Range": f"bytes={start}-{end}"}
    )
    expected_content_range = f"bytes {start}-{end}/{OBJECT_LENGTH}"
    if range_status != 206 or range_headers.get("content-range") != expected_content_range:
        raise ValueError("GEFS canary range response identity changed.")
    if len(payload) != end - start + 1 or range_headers.get("etag", "").strip('"') != OBJECT_ETAG:
        raise ValueError("GEFS canary range payload identity changed.")

    create_once(output / "source.idx", index_payload)
    create_once(output / "source.grib2", payload)
    messages = decode_range(output / "source.grib2", stations)
    report = {
        "schema": "noaa_gefs_v12_source_canary_v1",
        "source": {
            "url": f"{BASE}/{KEY}",
            "index_sha256": sha256(index_payload),
            "etag": etag,
            "object_length": OBJECT_LENGTH,
            "range": f"bytes={start}-{end}",
            "range_sha256": sha256(payload),
            "requests": client.requests,
        },
        "decoder": {"messages": messages},
        "research_only": True,
        "active_trading_capability_changed": False,
        "production_database_accessed": False,
    }
    encoded = (json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n").encode()
    create_once(output / "canary.json", encoded)
    print(json.dumps({"schema": report["schema"], "source": report["source"], "steps": list(EXPECTED_STEPS)}))


if __name__ == "__main__":
    main()
