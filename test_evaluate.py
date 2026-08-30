import datetime as dt
import unittest
from decimal import Decimal

import capture
import evaluate


def row(station: str, market_date: str, residual: str = "-10.0") -> dict[str, object]:
    forecast = Decimal("70.0")
    observed = forecast + Decimal(residual)
    return {
        "station_id": station,
        "market_date": market_date,
        "forecast_high_f": str(forecast),
        "observed_high_f": str(observed),
        "residual_f": residual,
    }


class EvaluateTest(unittest.TestCase):
    def test_capture_row_binds_causal_clock_and_residual(self) -> None:
        valid = {
            "station_id": "KATL",
            "market_date": "2021-07-10",
            "forecast_model": "noaa_nam_v4_station_mos_n_x",
            "forecast_initialized_at": "2021-07-09T12:00:00Z",
            "forecast_available_by": "2021-07-09T20:00:00Z",
            "forecast_time": "2021-07-11T00:00:00Z",
            "forecast_high_f": "80.0",
            "observed_high_f": "82.0",
            "residual_f": "2.0",
            "observation_source": "noaa_ncei_daily_summaries_tmax",
        }
        evaluate.validate_capture_row(valid)
        with self.assertRaisesRegex(ValueError, "residual identity"):
            evaluate.validate_capture_row({**valid, "residual_f": "1.9"})
        with self.assertRaisesRegex(ValueError, "causal identity"):
            evaluate.validate_capture_row({**valid, "forecast_available_by": "2021-07-10T20:00:00Z"})

    def test_boundaries_and_wilson_are_frozen(self) -> None:
        self.assertEqual(evaluate.boundaries(Decimal("100.0")), [Decimal("104.5"), Decimal("105.5"), Decimal("106.5"), Decimal("107.5")])
        self.assertEqual(evaluate.distance_bin(Decimal("4.0")), "4-5")
        self.assertEqual(evaluate.distance_bin(Decimal("7.9999")), "7-8")
        self.assertGreaterEqual(evaluate.wilson_lower(120, 120), Decimal("0.9000"))
        self.assertLess(evaluate.wilson_lower(100, 120), Decimal("0.9000"))
        with self.assertRaises(ValueError):
            evaluate.wilson_lower(120, 121)

    def test_rolling_history_enforces_two_day_lag(self) -> None:
        calibration_dates, evaluation_dates = capture.frozen_dates()
        calibration = [row("KATL", date) for date in calibration_dates]
        calibration[-1] = row("KATL", calibration_dates[-1], "100.0")
        evaluation = [row("KATL", evaluation_dates[0]), row("KATL", evaluation_dates[1])]
        predictions = evaluate.build_predictions(calibration, evaluation)
        first = [value for value in predictions if value["market_date"] == evaluation_dates[0]]
        second = [value for value in predictions if value["market_date"] == evaluation_dates[1]]
        self.assertTrue(first and second)
        self.assertEqual({value["history_last_date"] for value in first}, {"2021-07-08"})
        self.assertEqual({value["history_last_date"] for value in second}, {"2021-07-09"})
        self.assertGreater(int(first[0]["history_successes"]), int(second[0]["history_successes"]))

    def test_calibration_baseline_requires_all_twenty_stations(self) -> None:
        calibration_dates, _ = capture.frozen_dates()
        rows = [row(f"K{index:03d}", date) for index in range(20) for date in calibration_dates]
        baseline = evaluate.calibration_climatology(rows)
        self.assertEqual(set(baseline), {"4-5", "5-6", "6-7", "7-8"})
        self.assertTrue(all(value > Decimal("0.99") for value in baseline.values()))
        with self.assertRaisesRegex(ValueError, "wrong count"):
            evaluate.calibration_climatology(rows[:-1])

    def test_clustered_sampler_resamples_whole_dates(self) -> None:
        rows = []
        start = dt.date(2021, 7, 10)
        for offset in range(40):
            market_date = (start + dt.timedelta(days=offset)).isoformat()
            for station in ("KATL", "KBOS"):
                rows.append({"station_id": station, "market_date": market_date, "outcome": 1, "score": "0.90"})
        self.assertEqual(evaluate.clustered_lower(rows, 0.05), Decimal("0.1"))

    def test_nam_duplicate_coverage_is_exact_and_bound_to_sources(self) -> None:
        sources = [{"selected_exact_duplicate_count": 1} for _ in range(20)]
        evaluate.validate_duplicate_counts({"selected_exact_duplicate_rows": 20}, sources)
        with self.assertRaisesRegex(ValueError, "duplicate count identity"):
            evaluate.validate_duplicate_counts({"selected_exact_duplicate_rows": 19}, sources)


if __name__ == "__main__":
    unittest.main()
