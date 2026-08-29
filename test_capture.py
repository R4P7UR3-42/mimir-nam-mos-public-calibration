import csv
import io
import unittest
import urllib.parse

import capture


def csv_payload(rows: list[dict[str, str]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=["runtime", "ftime", "model", "n_x", "station"])
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode()


class CaptureTest(unittest.TestCase):
    def test_frozen_dates_are_exact_and_disjoint(self) -> None:
        calibration, evaluation = capture.frozen_dates()
        self.assertEqual((len(calibration), calibration[0], calibration[-1]), (145, "2021-02-15", "2021-07-09"))
        self.assertEqual((len(evaluation), evaluation[0], evaluation[-1]), (250, "2021-07-10", "2022-03-16"))
        self.assertFalse(set(calibration).intersection(evaluation))

    def test_bulk_url_freezes_exact_runtime_bounds(self) -> None:
        parsed = urllib.parse.urlparse(capture.mos_url("KATL"))
        query = urllib.parse.parse_qs(parsed.query)
        self.assertEqual(parsed.scheme + "://" + parsed.netloc + parsed.path, capture.IEM_BULK_URL)
        self.assertEqual(query, {
            "station": ["KATL"], "model": ["NAM"],
            "year1": ["2021"], "month1": ["2"], "day1": ["14"], "hour1": ["12"],
            "year2": ["2022"], "month2": ["3"], "day2": ["15"], "hour2": ["12"],
        })

    def test_mos_parser_selects_only_exact_maximum_identity(self) -> None:
        payload = csv_payload([
            {"runtime": "2021-02-14 12:00:00", "ftime": "2021-02-16 00:00:00", "model": "NAM", "n_x": "52.0", "station": "KATL"},
            {"runtime": "2021-02-14 12:00:00", "ftime": "2021-02-15 12:00:00", "model": "NAM", "n_x": "41.0", "station": "KATL"},
        ])
        rows, fields, duplicate_count = capture.parse_mos(payload, "KATL", ["2021-02-15"])
        self.assertEqual(fields, ("runtime", "ftime", "model", "n_x", "station"))
        self.assertEqual(duplicate_count, 0)
        self.assertEqual(rows, [{
            "station_id": "KATL",
            "market_date": "2021-02-15",
            "forecast_model": "noaa_nam_v4_station_mos_n_x",
            "forecast_initialized_at": "2021-02-14T12:00:00Z",
            "forecast_available_by": "2021-02-14T20:00:00Z",
            "forecast_time": "2021-02-16T00:00:00Z",
            "forecast_high_f": "52.0",
        }])

    def test_mos_parser_collapses_only_an_exact_duplicate(self) -> None:
        exact = {"runtime": "2021-02-14 12:00:00", "ftime": "2021-02-16 00:00:00", "model": "NAM", "n_x": "52.0", "station": "KATL"}
        rows, _, duplicate_count = capture.parse_mos(csv_payload([exact, exact]), "KATL", ["2021-02-15"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(duplicate_count, 1)
        with self.assertRaisesRegex(ValueError, "conflicting duplicate"):
            capture.parse_mos(csv_payload([exact, {**exact, "n_x": "53.0"}]), "KATL", ["2021-02-15"])

    def test_duplicate_identity_requires_exactly_one(self) -> None:
        capture.require_exact_duplicate_identity("KATL", 1)
        with self.assertRaisesRegex(ValueError, "invalid"):
            capture.require_exact_duplicate_identity("KATL", 0)
        with self.assertRaisesRegex(ValueError, "invalid"):
            capture.require_exact_duplicate_identity("KATL", 2)

    def test_mos_parser_fails_closed_on_null_and_wrong_station(self) -> None:
        exact = {"runtime": "2021-02-14 12:00:00", "ftime": "2021-02-16 00:00:00", "model": "NAM", "n_x": "52.0", "station": "KATL"}
        with self.assertRaisesRegex(ValueError, "missing"):
            capture.parse_mos(csv_payload([{**exact, "n_x": ""}]), "KATL", ["2021-02-15"])
        with self.assertRaisesRegex(ValueError, "identity drifted"):
            capture.parse_mos(csv_payload([{**exact, "station": "KBOS"}]), "KATL", ["2021-02-15"])

    def test_request_budget_is_exact(self) -> None:
        with self.assertRaises(ValueError):
            capture.RequestBudget(22)
        with self.assertRaises(ValueError):
            capture.RequestBudget(24)
        budget = capture.RequestBudget(23)
        for _ in range(23):
            budget.consume()
        with self.assertRaisesRegex(ValueError, "exhausted"):
            budget.consume()


if __name__ == "__main__":
    unittest.main()
