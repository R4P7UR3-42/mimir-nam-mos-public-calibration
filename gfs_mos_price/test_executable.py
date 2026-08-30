import datetime as dt
from decimal import Decimal
import csv
import io
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import capture  # noqa: E402
from gfs_mos_price.profile import configure  # noqa: E402

configure(capture)
from gfs_mos_price import evaluate_executable as executable  # noqa: E402


def source_row() -> dict[str, object]:
    return {
        "station_id": "KSEA",
        "market_date": "2025-12-31",
        "forecast_high_f": "70",
        "observed_high_f": "72",
    }


def history(residual: str = "-5") -> list[dict[str, object]]:
    start = dt.date(2025, 9, 1)
    return [
        {"market_date": (start + dt.timedelta(days=index)).isoformat(), "residual_f": residual}
        for index in range(120)
    ]


def source_market(**overrides: object) -> dict[str, object]:
    market = {
        "ticker": "KXHIGHTSEA-25DEC31-T75",
        "event_ticker": "KXHIGHTSEA-25DEC31",
        "market_type": "binary",
        "strike_type": "greater",
        "floor_strike": 74,
        "cap_strike": None,
        "yes_sub_title": "75° or above",
        "result": "no",
        "is_provisional": False,
        "mve_collection_ticker": None,
        "fee_waiver_expiration_time": None,
        "_source_partition": "historical",
    }
    market.update(overrides)
    return market


class FakeClient:
    def __init__(self, payload: dict[str, object]):
        self.payload = payload

    def fetch(self, _url: str, _label: str) -> dict[str, object]:
        return self.payload


class ExecutableTest(unittest.TestCase):
    def test_source_profile_freezes_121_plus_180_dates_and_thirteen_requests(self) -> None:
        calibration_dates, evaluation_dates = capture.frozen_dates()
        self.assertEqual((len(calibration_dates), calibration_dates[0], calibration_dates[-1]), (121, "2025-09-01", "2025-12-30"))
        self.assertEqual((len(evaluation_dates), evaluation_dates[0], evaluation_dates[-1]), (180, "2025-12-31", "2026-06-28"))
        capture.RequestBudget(13)
        with self.assertRaises(ValueError):
            capture.RequestBudget(12)
        rows = [{"station_id": "test"}] * 3010
        sources = [{"selected_exact_duplicate_count": 0} for _ in range(10)]
        self.assertEqual(capture.coverage_report(calibration_dates + evaluation_dates, rows, sources), {
            "requested_dates": 301,
            "complete_dates": 301,
            "station_dates": 3010,
            "selected_exact_duplicate_rows": 0,
        })

    def test_stale_isd_catalog_end_exception_is_exactly_bounded(self) -> None:
        fields = ["USAF", "WBAN", "STATION NAME", "CTRY", "STATE", "ICAO", "LAT", "LON", "ELEV(M)", "BEGIN", "END"]
        station = {"station_id": "KSEA", "latitude": 47.45, "longitude": -122.309}

        def payload(end: str) -> bytes:
            buffer = io.StringIO()
            writer = csv.DictWriter(buffer, fieldnames=fields)
            writer.writeheader()
            writer.writerow({
                "USAF": "727930", "WBAN": "24233", "STATION NAME": "SEATTLE-TACOMA INTERNATIONAL AIRPORT",
                "CTRY": "US", "STATE": "WA", "ICAO": "KSEA", "LAT": "47.450", "LON": "-122.309",
                "ELEV(M)": "132.9", "BEGIN": "19480101", "END": end,
            })
            return buffer.getvalue().encode()

        expected_count = capture.EXPECTED_STATION_COUNT
        capture.EXPECTED_STATION_COUNT = 1
        try:
            identities = capture.parse_isd(payload("20250825"), [station])
            self.assertEqual(identities[0]["ghcn_station_id"], "USW00024233")
            with self.assertRaisesRegex(ValueError, "does not cover"):
                capture.parse_isd(payload("20250824"), [station])
        finally:
            capture.EXPECTED_STATION_COUNT = expected_count

    def test_contract_mapping_uses_residual_distance_not_absolute_boundary(self) -> None:
        candidate = executable.score_market(source_row(), history("-5"), source_market())
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate["losing_boundary_f"], "74.5")
        self.assertEqual(candidate["distance_f"], "4.5")
        self.assertEqual(candidate["history_successes"], 120)
        self.assertEqual(candidate["outcome_no"], 1)
        self.assertIsNone(executable.score_market(source_row(), history("-5"), source_market(floor_strike=73, yes_sub_title="74° or above")))
        self.assertIsNone(executable.score_market(source_row(), history("-5"), source_market(floor_strike=78, yes_sub_title="79° or above")))

    def test_immediately_below_score_floor_fails_closed(self) -> None:
        below = history("-5")
        for row in below[-8:]:
            row["residual_f"] = "10"
        self.assertIsNone(executable.score_market(source_row(), below, source_market()))
        passing = history("-5")
        for row in passing[-7:]:
            row["residual_f"] = "10"
        candidate = executable.score_market(source_row(), passing, source_market())
        self.assertEqual(candidate["history_successes"], 113)
        self.assertEqual(candidate["score"], "0.9078")

    def test_rolling_history_is_exactly_two_days_lagged_and_contiguous(self) -> None:
        rows = history("0") + [
            {"market_date": "2025-12-30", "residual_f": "100"},
            {"market_date": "2025-12-31", "residual_f": "100"},
        ]
        selected = executable.rolling_history(rows, dt.date(2025, 12, 31))
        self.assertEqual(selected[0]["market_date"], "2025-09-01")
        self.assertEqual(selected[-1]["market_date"], "2025-12-29")
        with self.assertRaisesRegex(ValueError, "history is incomplete"):
            executable.rolling_history(rows[:-3] + rows[-2:], dt.date(2025, 12, 31))

    def test_wrong_contract_subtitle_and_result_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "contract identity"):
            executable.score_market(source_row(), history(), source_market(yes_sub_title="74° or above"))
        with self.assertRaisesRegex(ValueError, "contract identity"):
            executable.score_market(source_row(), history(), source_market(result="yes"))

    def test_quote_uses_exact_clock_complement_fee_and_edge(self) -> None:
        candidate = executable.score_market(source_row(), history(), source_market())
        payload = {
            "ticker": candidate["market_ticker"],
            "candlesticks": [{"end_period_ts": 1767125100, "yes_bid": {"close": "0.15"}}],
        }
        quote = executable.capture_quote(FakeClient(payload), "KXHIGHTSEA", candidate)
        self.assertEqual(quote["decision_at"], "2025-12-30T20:05:00Z")
        self.assertEqual(quote["no_limit"], "0.85")
        self.assertEqual(quote["fee"], "0.0090")
        self.assertTrue(quote["candidate"])
        self.assertGreaterEqual(Decimal(quote["conservative_edge"]), Decimal("0.0150"))

    def test_price_and_edge_adjacent_boundaries_fail(self) -> None:
        self.assertTrue(executable.MIN_PRICE <= Decimal("0.55") <= executable.MAX_PRICE)
        self.assertTrue(executable.MIN_PRICE <= Decimal("0.97") <= executable.MAX_PRICE)
        self.assertFalse(executable.MIN_PRICE <= Decimal("0.5499") <= executable.MAX_PRICE)
        self.assertFalse(executable.MIN_PRICE <= Decimal("0.9701") <= executable.MAX_PRICE)
        self.assertGreaterEqual(Decimal("0.0150"), executable.MIN_EDGE)
        self.assertLess(Decimal("0.0149"), executable.MIN_EDGE)

    def test_exact_historical_cutoff_boundary_passes_and_immediately_earlier_fails(self) -> None:
        executable.validate_historical_cutoffs({
            "market_settled_ts": "2026-06-30T00:00:00Z",
            "trades_created_ts": "2026-06-30T00:00:00Z",
        })
        with self.assertRaisesRegex(ValueError, "market cutoff"):
            executable.validate_historical_cutoffs({
                "market_settled_ts": "2026-06-29T23:59:59.999999Z",
                "trades_created_ts": "2026-06-30T00:00:00Z",
            })


if __name__ == "__main__":
    unittest.main()
