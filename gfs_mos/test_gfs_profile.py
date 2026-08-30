import csv
import io
from pathlib import Path
import sys
import unittest
import urllib.parse


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import capture  # noqa: E402
from gfs_mos.profile import configure  # noqa: E402

configure(capture)
import evaluate  # noqa: E402


def csv_payload(rows: list[dict[str, str]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=["runtime", "ftime", "model", "n_x", "station", "snw"],
    )
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode()


class GfsProfileTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        configure(capture)

    def test_profile_freezes_distinct_gfs_identity(self) -> None:
        self.assertEqual(capture.SOURCE_MODEL, "GFS")
        self.assertEqual(capture.FORECAST_MODEL, "noaa_gfs_station_mos_n_x")
        self.assertEqual(capture.EXPECTED_EXACT_DUPLICATES_PER_STATION, None)
        self.assertFalse(capture.REQUIRE_GLOBAL_OPTIONAL_SCHEMA)
        self.assertEqual(
            capture.file_sha256(ROOT / "gfs_mos" / "PREDECLARATION.md"),
            capture.PREDECLARATION_SHA256,
        )

    def test_url_binds_gfs_and_exact_frozen_runtime_window(self) -> None:
        query = urllib.parse.parse_qs(urllib.parse.urlparse(capture.mos_url("KATL")).query)
        self.assertEqual(query, {
            "station": ["KATL"], "model": ["GFS"],
            "year1": ["2021"], "month1": ["2"], "day1": ["14"], "hour1": ["12"],
            "year2": ["2022"], "month2": ["3"], "day2": ["15"], "hour2": ["12"],
        })

    def test_optional_schema_drift_does_not_change_semantic_duplicate(self) -> None:
        exact = {
            "runtime": "2021-02-14 12:00:00",
            "ftime": "2021-02-16 00:00:00",
            "model": "GFS",
            "n_x": "52.0",
            "station": "KATL",
            "snw": "0",
        }
        rows, fields, duplicate_count = capture.parse_mos(
            csv_payload([exact, {**exact, "snw": ""}]),
            "KATL",
            ["2021-02-15"],
        )
        self.assertEqual(len(rows), 1)
        self.assertIn("snw", fields)
        self.assertEqual(duplicate_count, 1)
        self.assertEqual(rows[0]["forecast_model"], "noaa_gfs_station_mos_n_x")

    def test_conflicting_semantic_duplicate_fails_closed(self) -> None:
        exact = {
            "runtime": "2021-02-14 12:00:00",
            "ftime": "2021-02-16 00:00:00",
            "model": "GFS",
            "n_x": "52.0",
            "station": "KATL",
            "snw": "0",
        }
        with self.assertRaisesRegex(ValueError, "conflicting duplicate"):
            capture.parse_mos(
                csv_payload([exact, {**exact, "n_x": "53.0"}]),
                "KATL",
                ["2021-02-15"],
            )

    def test_gfs_accepts_any_nonnegative_duplicate_count_only(self) -> None:
        capture.require_exact_duplicate_identity("KATL", 0)
        capture.require_exact_duplicate_identity("KATL", 2)
        with self.assertRaisesRegex(ValueError, "invalid"):
            capture.require_exact_duplicate_identity("KATL", -1)

    def test_variable_duplicate_counts_are_bound_to_aggregate(self) -> None:
        sources = [
            {"selected_exact_duplicate_count": index % 3}
            for index in range(20)
        ]
        total = sum(source["selected_exact_duplicate_count"] for source in sources)
        evaluate.validate_duplicate_counts({"selected_exact_duplicate_rows": total}, sources)
        with self.assertRaisesRegex(ValueError, "duplicate count identity"):
            evaluate.validate_duplicate_counts({"selected_exact_duplicate_rows": total + 1}, sources)


if __name__ == "__main__":
    unittest.main()
