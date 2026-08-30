import csv
import datetime as dt
import io
import json
from decimal import Decimal
from pathlib import Path
import unittest
import urllib.parse

from gfs_mos_precipitation import develop


STATION = {
    "station_id": "KATL",
    "latitude": 33.64,
    "longitude": -84.427,
    "time_zone": "America/New_York",
}


def mos_payload(rows: list[dict[str, str]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=["runtime", "ftime", "model", "p06", "station", "q06"])
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode()


def exact_rows(market_date: dt.date, values: list[str]) -> list[dict[str, str]]:
    endpoints = develop.local_day_interval_ends(market_date, "America/New_York")
    return [{
        "runtime": f"{(market_date - dt.timedelta(days=1)).isoformat()} 12:00:00",
        "ftime": endpoint.strftime("%Y-%m-%d %H:%M:%S"),
        "model": "GFS",
        "p06": value,
        "station": "KATL",
        "q06": "0",
    } for endpoint, value in zip(endpoints, values, strict=True)]


class DevelopTest(unittest.TestCase):
    def test_frozen_dates_are_disjoint_and_reserved_has_250(self) -> None:
        history, development = develop.assert_frozen_dates()
        self.assertEqual((len(history), len(development)), (366, 327))
        self.assertEqual((develop.RESERVED_END - develop.RESERVED_START).days + 1, 250)
        self.assertLess(development[-1], develop.RESERVED_START)

    def test_url_binds_only_history_and_development_runtimes(self) -> None:
        query = urllib.parse.parse_qs(urllib.parse.urlparse(develop.mos_url("KATL")).query)
        self.assertEqual(query["model"], ["GFS"])
        self.assertEqual(query["station"], ["KATL"])
        self.assertEqual(
            (query["year1"], query["month1"], query["day1"], query["hour1"]),
            (["2023"], ["12"], ["31"], ["12"]),
        )
        self.assertEqual(
            (query["year2"], query["month2"], query["day2"], query["hour2"]),
            (["2025"], ["11"], ["22"], ["12"]),
        )

    def test_local_day_uses_four_or_five_intersecting_intervals(self) -> None:
        winter_eastern = develop.local_day_interval_ends(dt.date(2025, 1, 2), "America/New_York")
        winter_central = develop.local_day_interval_ends(dt.date(2025, 1, 2), "America/Chicago")
        summer_central = develop.local_day_interval_ends(dt.date(2025, 7, 2), "America/Chicago")
        self.assertEqual(len(winter_eastern), 5)
        self.assertEqual(len(winter_central), 4)
        self.assertEqual(len(summer_central), 5)
        self.assertEqual(winter_central[0].hour, 12)

    def test_parser_builds_exact_product_proxy_and_collapses_exact_duplicate(self) -> None:
        market_date = dt.date(2025, 1, 2)
        rows = exact_rows(market_date, ["0", "10", "20", "30", "40"])
        parsed, fields, duplicates, missing = develop.parse_mos(
            mos_payload([*rows, dict(rows[0])]), STATION, [market_date],
        )
        self.assertIn("p06", fields)
        self.assertEqual(duplicates, 1)
        self.assertEqual(missing, [])
        self.assertEqual(parsed[0]["selected_p06_percent"], ["0", "10", "20", "30", "40"])
        self.assertEqual(parsed[0]["raw_no_rain_proxy"], "0.30240000")
        self.assertEqual(parsed[0]["proxy_band"], "0.00-0.50")

    def test_conflicting_duplicate_fails_closed(self) -> None:
        market_date = dt.date(2025, 1, 2)
        rows = exact_rows(market_date, ["0", "10", "20", "30", "40"])
        conflicting = {**rows[0], "p06": "1"}
        with self.assertRaisesRegex(ValueError, "conflicting duplicate"):
            develop.parse_mos(mos_payload([*rows, conflicting]), STATION, [market_date])

    def test_missing_intersecting_interval_fails_closed(self) -> None:
        market_date = dt.date(2025, 1, 2)
        rows = exact_rows(market_date, ["0", "10", "20", "30", "40"])
        with self.assertRaisesRegex(ValueError, "coverage is incomplete"):
            develop.parse_mos(mos_payload(rows[:-1]), STATION, [market_date])

    def test_entire_missing_runtime_is_reported_without_substitution(self) -> None:
        market_date = dt.date(2025, 1, 2)
        alternate = exact_rows(market_date, ["0", "10", "20", "30", "40"])
        for row in alternate:
            row["runtime"] = f"{(market_date - dt.timedelta(days=1)).isoformat()} 06:00:00"
        parsed, _, _, missing = develop.parse_mos(mos_payload(alternate), STATION, [market_date])
        self.assertEqual(parsed, [])
        self.assertEqual(missing, [market_date])

    def test_trace_is_rain_and_nontrace_zero_is_no(self) -> None:
        identities = [{"station_id": "KATL", "ghcn_station_id": "USW00013874", "station_name": "ATL"}]
        dates = [dt.date(2024, 1, 1), dt.date(2024, 1, 2)]
        payload = json.dumps([
            {"STATION": "USW00013874", "DATE": "2024-01-01", "PRCP": "0.00", "PRCP_ATTRIBUTES": "T,,W,2400"},
            {"STATION": "USW00013874", "DATE": "2024-01-02", "PRCP": "0.00", "PRCP_ATTRIBUTES": ",,W,2400"},
        ]).encode()
        outcomes = develop.parse_outcomes(payload, identities, dates)
        self.assertEqual(outcomes[("KATL", "2024-01-01")]["outcome_no"], 0)
        self.assertEqual(outcomes[("KATL", "2024-01-02")]["outcome_no"], 1)

    def test_quality_flag_and_unsafe_measurement_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsafe"):
            develop.parse_attributes("T,X,W,2400", "KATL|2024-01-01")
        with self.assertRaisesRegex(ValueError, "unsafe"):
            develop.parse_attributes("P,,W,2400", "KATL|2024-01-01")

    def test_isd_mapping_may_end_before_development_when_it_overlaps_window(self) -> None:
        header = ["USAF", "WBAN", "STATION NAME", "CTRY", "STATE", "ICAO", "LAT", "LON", "ELEV(M)", "BEGIN", "END"]
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=header)
        writer.writeheader()
        writer.writerow({
            "USAF": "722190", "WBAN": "13874", "STATION NAME": "ATL", "CTRY": "US", "STATE": "GA",
            "ICAO": "KATL", "LAT": "+33.630", "LON": "-084.442", "ELEV(M)": "308.2",
            "BEGIN": "19730101", "END": "20250827",
        })
        identities = develop.parse_isd(buffer.getvalue().encode(), [STATION])
        self.assertEqual(identities[0]["ghcn_station_id"], "USW00013874")
        self.assertEqual(identities[0]["history_end"], "20250827")

    def test_ghcnd_inventory_independently_attests_prcp_coverage(self) -> None:
        identities = [{
            "station_id": "KATL", "ghcn_station_id": "USW00013874", "station_name": "ATL",
            "latitude": 33.630, "longitude": -84.442,
        }]
        parsed = develop.parse_ghcnd_inventory(
            b"USW00013874  33.6297  -84.4422 PRCP 1930 2026\n", identities,
        )
        self.assertEqual(parsed[0]["element"], "PRCP")
        self.assertEqual(parsed[0]["last_year"], 2026)
        with self.assertRaisesRegex(ValueError, "does not cover"):
            develop.parse_ghcnd_inventory(
                b"USW00013874  33.6297  -84.4422 PRCP 1930 2024\n", identities,
            )

    def test_exact_fee_and_adjacent_edge_boundary(self) -> None:
        self.assertEqual(develop.exact_fee(Decimal("0.70")), Decimal("0.0147"))
        threshold = Decimal("0.70") + Decimal("0.0147") + Decimal("0.015")
        self.assertGreaterEqual(threshold - Decimal("0.70") - develop.exact_fee(Decimal("0.70")), develop.MIN_EDGE)
        self.assertLess(threshold - Decimal("0.0001") - Decimal("0.70") - develop.exact_fee(Decimal("0.70")), develop.MIN_EDGE)

    def test_freeze_hashes_match(self) -> None:
        self.assertEqual(
            develop.file_sha256(Path(__file__).with_name("DEVELOPMENT.md")),
            develop.DEVELOPMENT_SHA256,
        )
        self.assertEqual(develop.file_sha256(develop.ROOT / "stations.json"), develop.STATIONS_SHA256)


if __name__ == "__main__":
    unittest.main()
