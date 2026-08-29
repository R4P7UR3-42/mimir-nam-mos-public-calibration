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
                self.urls = []

            def fetch(self, url, _label):
                self.urls.append(url)
                return {"markets": [self.value], "cursor": ""}

        client = Client(market)
        result = evaluate.discover_top_markets(
            client, "KXHIGHNY", dt.date(2026, 3, 20), dt.date(2026, 3, 20), "test", True,
        )
        self.assertEqual(result[dt.date(2026, 3, 20)]["ticker"], market["ticker"])
        self.assertIn("event_ticker=KXHIGHNY-26MAR20", client.urls[0])
        self.assertNotIn("series_ticker=", client.urls[0])
        with self.assertRaisesRegex(ValueError, "unsupported"):
            evaluate.discover_top_markets(
                Client({**market, "is_provisional": True}),
                "KXHIGHNY", dt.date(2026, 3, 20), dt.date(2026, 3, 20), "test", True,
            )

    def test_event_date_parser_is_exact(self) -> None:
        self.assertEqual(
            evaluate.exact_event_ticker("KXHIGHNY", dt.date(2026, 6, 7)),
            "KXHIGHNY-26JUN07",
        )
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

    def test_event_scoped_market_response_must_be_terminal(self) -> None:
        class Client:
            def fetch(self, _url, _label):
                return {"markets": [], "cursor": "unexpected"}

        with self.assertRaisesRegex(ValueError, "not terminal"):
            evaluate.discover_top_markets(
                Client(), "KXHIGHNY", dt.date(2026, 3, 21), dt.date(2026, 3, 21), "test", True,
            )

    def test_historical_cutoff_contains_complete_frozen_window(self) -> None:
        class Client:
            def __init__(self, market_cutoff: str):
                self.market_cutoff = market_cutoff

            def fetch(self, _url, _label):
                return {
                    "market_settled_ts": self.market_cutoff,
                    "trades_created_ts": "2026-06-30T00:00:00Z",
                }

        result = evaluate.validate_historical_cutoff(Client("2026-06-30T00:00:00Z"))
        self.assertEqual(result["market_settled_ts"], "2026-06-30T00:00:00Z")
        with self.assertRaisesRegex(ValueError, "does not contain"):
            evaluate.validate_historical_cutoff(Client("2026-06-29T00:00:00Z"))

    def test_fee_uses_exact_provider_rounding(self) -> None:
        self.assertEqual(evaluate.fee(Decimal("0.85")), Decimal("0.0090"))
        self.assertEqual(evaluate.fee(Decimal("0")), Decimal("0.0000"))
        with self.assertRaises(ValueError):
            evaluate.fee(Decimal("1.0001"))

    def test_price_bins_bind_adjacent_boundaries(self) -> None:
        self.assertIsNone(evaluate.price_bin(Decimal("0.8499")))
        self.assertEqual(evaluate.price_bin(Decimal("0.8500")), "0.85-0.90")
        self.assertEqual(evaluate.price_bin(Decimal("0.8999")), "0.85-0.90")
        self.assertIsNone(evaluate.price_bin(Decimal("0.9000")))
        self.assertIsNone(evaluate.price_bin(Decimal("0.9499")))
        self.assertEqual(evaluate.price_bin(Decimal("0.9500")), "0.95-0.97")
        self.assertEqual(evaluate.price_bin(Decimal("0.9700")), "0.95-0.97")
        self.assertIsNone(evaluate.price_bin(Decimal("0.9701")))

    def test_training_requires_twenty_dates_and_twenty_five_rows(self) -> None:
        rows = []
        start = dt.date(2026, 1, 12)
        for offset in range(19):
            for station in ("A", "B"):
                rows.append({
                    "candidate": True,
                    "price_bin": "0.85-0.90",
                    "market_date": (start + dt.timedelta(days=offset)).isoformat(),
                    "outcome_no": 1,
                    "series_ticker": station,
                })
        result = evaluate.calibrate(rows)
        self.assertFalse(result["bins"][0]["accepted"])
        for station in ("A", "B"):
            rows.append({
                "candidate": True,
                "price_bin": "0.85-0.90",
                "market_date": (start + dt.timedelta(days=19)).isoformat(),
                "outcome_no": 1,
                "series_ticker": station,
            })
        result = evaluate.calibrate(rows)
        self.assertTrue(result["bins"][0]["accepted"])
        self.assertEqual(result["bins"][0]["rows"], 40)

    def test_wilson_lower_is_finite_and_fail_closed(self) -> None:
        self.assertEqual(evaluate.wilson_lower(0, 0), None)
        self.assertEqual(evaluate.wilson_lower(2, 1), None)
        lower = evaluate.wilson_lower(25, 25)
        self.assertIsNotNone(lower)
        self.assertGreater(lower, Decimal("0.93"))
        self.assertLess(lower, Decimal("1"))

    def test_decision_clock_is_prior_day_18z(self) -> None:
        self.assertEqual(
            evaluate.decision_clock(dt.date(2026, 3, 20)),
            dt.datetime(2026, 3, 19, 18, tzinfo=dt.timezone.utc),
        )

    def test_drawdown_uses_realized_sequence(self) -> None:
        values = [Decimal("0.10"), Decimal("-0.80"), Decimal("0.20")]
        self.assertEqual(evaluate.maximum_drawdown(values), Decimal("0.80"))

    def test_request_ceiling_is_exact(self) -> None:
        with self.assertRaises(ValueError):
            evaluate.PublicClient.__init__(object(), dt.date.today(), 4_999)


if __name__ == "__main__":
    unittest.main()
