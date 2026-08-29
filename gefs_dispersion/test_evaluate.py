import datetime as dt
import unittest

import evaluate


class EvaluationTests(unittest.TestCase):
    def test_wilson_and_score_band_boundaries(self):
        self.assertGreater(evaluate.wilson_lower(119, 119), 0.97)
        self.assertLess(evaluate.wilson_lower(100, 119), 0.90)
        self.assertEqual(evaluate.score_band(0.90), "0.90_0.93")
        self.assertEqual(evaluate.score_band(0.93), "0.93_0.96")
        self.assertEqual(evaluate.score_band(0.96), "0.96_1.00")
        self.assertEqual(evaluate.score_band(1.0), "0.96_1.00")
        with self.assertRaisesRegex(ValueError, "outside"):
            evaluate.score_band(0.899999)

    def test_frozen_rolling_prediction_uses_119_lagged_station_dates(self):
        features = {}
        start = dt.date(2018, 12, 27)
        end = dt.date(2019, 12, 31)
        current = start
        stations = [f"K{index:03d}" for index in range(20)]
        while current <= end:
            for station in stations:
                features[(station, current.isoformat())] = {
                    "center_f": 70.2,
                    "raw_dispersion_f": 0.2,
                    "dispersion_f": 0.5,
                    "outcome_f": 70.0,
                    "standardized_error": -0.4,
                }
            current += dt.timedelta(days=1)
        rows = evaluate.build_predictions(features)
        self.assertEqual(len(rows), 20 * 250 * 4)
        first = rows[0]
        self.assertEqual(first["market_date"], "2019-04-26")
        self.assertEqual(first["calibration_dates"], 119)
        self.assertEqual(first["calibration_successes"], 119)
        self.assertEqual(first["threshold_f"], 75)
        self.assertGreaterEqual(first["threshold_distance_f"], 4)
        self.assertLess(first["threshold_distance_f"], 5)

    def test_clustered_lower_preserves_constant_sign(self):
        positive = [{"market_date": f"2019-01-{day:02d}", "margin": 0.01} for day in range(1, 6)]
        negative = [{"market_date": f"2019-01-{day:02d}", "margin": -0.01} for day in range(1, 6)]
        self.assertAlmostEqual(evaluate.clustered_lower(positive, "margin", 0.05, 7), 0.01)
        self.assertAlmostEqual(evaluate.clustered_lower(negative, "margin", 0.05, 7), -0.01)


if __name__ == "__main__":
    unittest.main()
