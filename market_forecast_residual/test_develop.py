import datetime as dt
import unittest
from decimal import Decimal

import develop


class FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.urls = []

    def fetch(self, url, _label):
        self.urls.append(url)
        return self.payload


class DevelopmentTest(unittest.TestCase):
    def test_forecast_run_is_prior_day_06z(self):
        self.assertEqual(
            develop.forecast_run(dt.date(2026, 3, 19)),
            dt.datetime(2026, 3, 18, 6, tzinfo=dt.timezone.utc),
        )

    def test_exact_price_boundaries_are_eligible(self):
        self.assertLessEqual(develop.MIN_PRICE, Decimal("0.5000"))
        self.assertGreaterEqual(develop.MAX_PRICE, Decimal("0.9700"))
        self.assertGreater(develop.MIN_PRICE, Decimal("0.4999"))
        self.assertLess(develop.MAX_PRICE, Decimal("0.9701"))

    def test_forecast_parser_uses_exact_local_date(self):
        start = dt.datetime(2026, 2, 10, 6)
        times = [(start + dt.timedelta(hours=index)).isoformat(timespec="minutes") for index in range(96)]
        values = list(range(96))
        payload = {
            "latitude": 33.63796,
            "longitude": -84.41687,
            "utc_offset_seconds": 0,
            "timezone": "GMT",
            "hourly_units": {"temperature_2m": "°F"},
            "hourly": {"time": times, "temperature_2m": values},
        }
        station = {
            "station_id": "KATL",
            "series_ticker": "KXHIGHTATL",
            "latitude": 33.64,
            "longitude": -84.427,
            "time_zone": "America/New_York",
        }
        result = develop.fetch_forecast(FakeClient(payload), station, dt.date(2026, 2, 11))
        self.assertEqual(result["forecast_local_hour_count"], 24)
        self.assertEqual(result["forecast_first_utc"], "2026-02-11T05:00Z")
        self.assertEqual(result["forecast_last_utc"], "2026-02-12T04:00Z")
        self.assertEqual(result["forecast_max_f"], "46")
        self.assertIn("run=2026-02-10T06%3A00", result["forecast_source_url"])

    def test_ridge_logistic_fit_learns_positive_distance(self):
        rows = []
        for index in range(40):
            distance = -2 if index < 20 else 2
            rows.append({
                "no_limit": "0.70",
                "forecast_distance_f": str(distance * 5),
                "outcome_no": int(distance > 0),
            })
        for name in develop.MODEL_ORDER:
            coefficients = develop.fit(rows, name)
            distance_index = 2 if name == "market_free" else 1
            self.assertGreater(coefficients[distance_index], 0)
            self.assertLess(develop.predict(rows[0], name, coefficients), develop.predict(rows[-1], name, coefficients))

    def test_unknown_model_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "Unknown model"):
            develop.design({"no_limit": "0.8", "forecast_distance_f": "1"}, "other")


if __name__ == "__main__":
    unittest.main()
