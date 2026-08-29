import datetime as dt
import unittest
from decimal import Decimal

import evaluate


class MarketImpliedTest(unittest.TestCase):
    def test_archived_market_optional_fields_are_fail_closed_when_present(self) -> None:
        market = {
            "ticker": "KXHIGHNY-26MAR20-T80",
            "event_ticker": "KXHIGHNY-26MAR20",
            "market_type": "binary",
            "strike_type": "greater",
            "floor_strike": 80,
            "cap_strike": None,
            "result": "no",
            "occurrence_datetime": "2026-03-20T14:00:00Z",
        }

        class Client:
            def __init__(self, value):
                self.value = value

            def fetch(self, _url, _label):
                return {"markets": [self.value], "cursor": ""}

        result = evaluate.discover_top_markets(
            Client(market), "KXHIGHNY", dt.date(2026, 3, 20), dt.date(2026, 3, 20), "test", True,
        )
        self.assertEqual(result[dt.date(2026, 3, 20)]["ticker"], market["ticker"])
        with self.assertRaisesRegex(ValueError, "unsupported"):
            evaluate.discover_top_markets(
                Client({**market, "is_provisional": True}),
                "KXHIGHNY", dt.date(2026, 3, 20), dt.date(2026, 3, 20), "test", True,
            )

    def test_event_date_parser_is_exact(self) -> None:
        self.assertEqual(
            evaluate.event_market_date("KXHIGHNY-26MAR20", "KXHIGHNY"),
            dt.date(2026, 3, 20),
        )
        self.assertEqual(
            evaluate.event_market_date("KXHIGHNY-26JUN7", "KXHIGHNY"),
            dt.date(2026, 6, 7),
        )
        with self.assertRaises(ValueError):
            evaluate.event_market_date("KXHIGHNY-26FOO20", "KXHIGHNY")

    def test_fee_uses_exact_provider_rounding(self) -> None:
        self.assertEqual(evaluate.fee(Decimal("0.85")), Decimal("0.0090"))
        self.assertEqual(evaluate.fee(Decimal("0")), Decimal("0.0000"))
        with self.assertRaises(ValueError):
            evaluate.fee(Decimal("1.0001"))

    def test_price_bins_bind_adjacent_boundaries(self) -> None:
        self.assertIsNone(evaluate.price_bin(Decimal("0.6999")))
        self.assertEqual(evaluate.price_bin(Decimal("0.7000")), "0.70-0.80")
        self.assertEqual(evaluate.price_bin(Decimal("0.7999")), "0.70-0.80")
        self.assertEqual(evaluate.price_bin(Decimal("0.8000")), "0.80-0.90")
        self.assertEqual(evaluate.price_bin(Decimal("0.9000")), "0.90-0.97")
        self.assertEqual(evaluate.price_bin(Decimal("0.9700")), "0.90-0.97")
        self.assertIsNone(evaluate.price_bin(Decimal("0.9701")))

    def test_training_requires_thirty_dates_and_fifty_rows(self) -> None:
        rows = []
        start = dt.date(2026, 1, 12)
        for offset in range(29):
            for station in ("A", "B"):
                rows.append({
                    "candidate": True,
                    "price_bin": "0.70-0.80",
                    "market_date": (start + dt.timedelta(days=offset)).isoformat(),
                    "outcome_no": 1,
                    "series_ticker": station,
                })
        result = evaluate.calibrate(rows)
        self.assertFalse(result["bins"][0]["accepted"])
        for station in ("A", "B"):
            rows.append({
                "candidate": True,
                "price_bin": "0.70-0.80",
                "market_date": (start + dt.timedelta(days=29)).isoformat(),
                "outcome_no": 1,
                "series_ticker": station,
            })
        result = evaluate.calibrate(rows)
        self.assertTrue(result["bins"][0]["accepted"])
        self.assertEqual(result["bins"][0]["rows"], 60)

    def test_decision_clock_is_prior_day_20z(self) -> None:
        self.assertEqual(
            evaluate.decision_clock(dt.date(2026, 3, 20)),
            dt.datetime(2026, 3, 19, 20, tzinfo=dt.timezone.utc),
        )

    def test_drawdown_uses_realized_sequence(self) -> None:
        values = [Decimal("0.10"), Decimal("-0.80"), Decimal("0.20")]
        self.assertEqual(evaluate.maximum_drawdown(values), Decimal("0.80"))

    def test_request_ceiling_is_exact(self) -> None:
        with self.assertRaises(ValueError):
            evaluate.PublicClient.__init__(object(), dt.date.today(), 2_199)


if __name__ == "__main__":
    unittest.main()
