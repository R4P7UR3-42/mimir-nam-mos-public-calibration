import datetime as dt
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest import mock

import develop


def terminal_market(ticker: str, event: str, strike_type: str) -> dict[str, object]:
    return {
        "ticker": ticker,
        "event_ticker": event,
        "market_type": "binary",
        "strike_type": strike_type,
        "floor_strike": 50 if strike_type != "less" else None,
        "cap_strike": 50 if strike_type != "greater" else None,
        "result": "no",
        "occurrence_datetime": "2026-01-16T12:00:00Z",
    }


class LowMarketDevelopmentTest(unittest.TestCase):
    def test_frozen_inventories_are_sorted_disjoint_and_low_temperature(self) -> None:
        root = Path(__file__).resolve().parent
        training = develop.load_inventory(root / "training_series.json", develop.TRAINING_SERIES_SHA256, 12)
        reserved = develop.load_inventory(
            root / "reserved_evaluation_series.json", develop.RESERVED_SERIES_SHA256, 11,
        )
        self.assertFalse(set(training).intersection(reserved))
        self.assertEqual(len(set(training + reserved)), 23)
        self.assertIn("KXLOWTATL", training)
        self.assertIn("KXLOWTNYC", training)
        self.assertIn("KXLOWTTTN", reserved)

    def test_reserved_series_is_rejected_before_network(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            client = develop.TrainingClient(Path(temporary), 5_000, ["KXLOWTNYC"])
            with mock.patch.object(develop.market.PublicClient, "fetch") as fetched:
                with self.assertRaisesRegex(ValueError, "Reserved evaluation"):
                    client.fetch(
                        f"{develop.market.BASE_URL}/historical/markets?series_ticker=KXLOWTNYC",
                        "training-page",
                    )
            fetched.assert_not_called()

    def test_series_pagination_is_cursor_exhausted_and_date_bounded(self) -> None:
        event = "KXLOWTATL-26JAN15"
        pages = [
            {
                "markets": [
                    terminal_market(f"{event}-T55", event, "greater"),
                    terminal_market(f"{event}-T45", event, "less"),
                ],
                "cursor": "next-page",
            },
            {
                "markets": [terminal_market(f"{event}-B50.5", event, "between")],
                "cursor": "",
            },
        ]

        class Client:
            def __init__(self):
                self.urls = []

            def fetch(self, url, _label):
                self.urls.append(url)
                return pages[len(self.urls) - 1]

        client = Client()
        result = develop.discover_training_events(client, "KXLOWTATL")
        self.assertEqual(len(result[dt.date(2026, 1, 15)]), 3)
        self.assertNotIn("cursor=", client.urls[0])
        self.assertIn("cursor=next-page", client.urls[1])

    def test_repeated_market_and_cursor_fail_closed(self) -> None:
        event = "KXLOWTATL-26JAN15"
        row = terminal_market(f"{event}-T55", event, "greater")

        class DuplicateClient:
            def __init__(self):
                self.count = 0

            def fetch(self, _url, _label):
                self.count += 1
                return {"markets": [row], "cursor": "again" if self.count == 1 else ""}

        with self.assertRaisesRegex(ValueError, "duplicated"):
            develop.discover_training_events(DuplicateClient(), "KXLOWTATL")

    def test_extreme_contract_identity_is_exact(self) -> None:
        event = "KXLOWTATL-26JAN15"
        rows = [
            terminal_market(f"{event}-T55", event, "greater"),
            terminal_market(f"{event}-T45", event, "less"),
            terminal_market(f"{event}-B50.5", event, "between"),
        ]
        selected = develop.select_extremes(rows)
        self.assertEqual(selected["upper"]["ticker"], f"{event}-T55")
        self.assertEqual(selected["lower"]["ticker"], f"{event}-T45")
        with self.assertRaisesRegex(ValueError, "one exact"):
            develop.select_extremes(rows[:-2])

    def test_exact_finalized_scalar_is_excluded_without_outcome_credit(self) -> None:
        event = "KXLOWTATL-26JAN15"
        scalar = {
            **terminal_market(f"{event}-T55", event, "greater"),
            "result": "scalar",
            "status": "finalized",
            "settlement_value_dollars": "0.0000",
            "expiration_value": "",
            "occurrence_datetime": "2026-01-24T12:00:00Z",
        }
        self.assertIsNone(develop.validate_terminal_market(scalar, "KXLOWTATL"))
        self.assertIsNone(develop.validate_terminal_market({**scalar, "settlement_value_dollars": "0.9900"}, "KXLOWTATL"))
        with self.assertRaisesRegex(ValueError, "scalar exclusion"):
            develop.validate_terminal_market({**scalar, "settlement_value_dollars": "1.0001"}, "KXLOWTATL")
        with self.assertRaisesRegex(ValueError, "scalar exclusion"):
            develop.validate_terminal_market({**scalar, "settlement_value_dollars": "0.99"}, "KXLOWTATL")
        with self.assertRaisesRegex(ValueError, "identity is malformed"):
            develop.validate_terminal_market({**scalar, "ticker": "OTHER-T55"}, "KXLOWTATL")

    def test_any_exact_scalar_row_excludes_the_entire_event(self) -> None:
        event = "KXLOWTATL-26JAN15"
        scalar = {
            **terminal_market(f"{event}-B50.5", event, "between"),
            "result": "scalar",
            "status": "finalized",
            "settlement_value_dollars": "0.9900",
            "expiration_value": "",
            "occurrence_datetime": "2026-01-24T12:00:00Z",
        }

        class Client:
            def fetch(self, _url, _label):
                return {
                    "markets": [
                        terminal_market(f"{event}-T55", event, "greater"),
                        terminal_market(f"{event}-T45", event, "less"),
                        scalar,
                    ],
                    "cursor": "",
                }

        self.assertEqual(develop.discover_training_events(Client(), "KXLOWTATL"), {})

    def test_occurrence_identity_is_exact_next_day_when_present(self) -> None:
        event = "KXLOWTATL-26JAN15"
        row = terminal_market(f"{event}-T55", event, "greater")
        self.assertEqual(develop.validate_terminal_market(row, "KXLOWTATL"), dt.date(2026, 1, 15))
        with self.assertRaisesRegex(ValueError, "Occurrence date conflicts"):
            develop.validate_terminal_market({**row, "occurrence_datetime": "2026-01-15T12:00:00Z"}, "KXLOWTATL")

    def test_price_cells_bind_exact_adjacent_boundaries(self) -> None:
        self.assertIsNone(develop.cell_for("upper", Decimal("0.6999")))
        self.assertEqual(develop.cell_for("upper", Decimal("0.7000")), "upper_0.70_0.80")
        self.assertEqual(develop.cell_for("upper", Decimal("0.7999")), "upper_0.70_0.80")
        self.assertEqual(develop.cell_for("upper", Decimal("0.8000")), "upper_0.80_0.90")
        self.assertEqual(develop.cell_for("lower", Decimal("0.9700")), "lower_0.95_0.97")
        self.assertIsNone(develop.cell_for("lower", Decimal("0.9701")))
        self.assertIsNone(develop.cell_for("other", Decimal("0.9000")))

    def test_exact_fee_return_and_training_gates_have_adjacent_failure(self) -> None:
        rows = []
        start = dt.date(2025, 12, 13)
        exact_return = Decimal(1) - Decimal("0.70") - develop.market.fee(Decimal("0.70"))
        for index in range(120):
            rows.append({
                "candidate": True,
                "cell": "upper_0.70_0.80",
                "market_date": (start + dt.timedelta(days=index % 60)).isoformat(),
                "series_ticker": f"KXLOWT{index % 8:02d}",
                "outcome_no": 1,
                "exact_fee_return": str(exact_return),
            })
        passing = develop.evaluate_cell(rows, 0)
        self.assertTrue(passing["admissible"])
        self.assertEqual(passing["score_jeffreys"], "0.99586777")
        failing = develop.evaluate_cell(rows[:99], 0)
        self.assertFalse(failing["gates"]["minimum_100_rows"])
        self.assertFalse(failing["admissible"])

    def test_decision_clock_is_exact_prior_day_18z(self) -> None:
        self.assertEqual(
            develop.decision_clock(dt.date(2026, 1, 15)),
            dt.datetime(2026, 1, 14, 18, tzinfo=dt.timezone.utc),
        )


if __name__ == "__main__":
    unittest.main()
