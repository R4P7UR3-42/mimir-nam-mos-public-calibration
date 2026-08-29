import datetime as dt
import importlib.util
import unittest
from decimal import Decimal
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("evaluate.py")
SPEC = importlib.util.spec_from_file_location("nbm_q90_time_evaluate", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
evaluate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evaluate)


class NbmQ90TimeTest(unittest.TestCase):
    def test_five_clocks_are_exact_and_pre_observation(self) -> None:
        market_date = dt.date(2026, 7, 11)
        self.assertEqual(
            [evaluate.decision_at(market_date, clock).isoformat() for clock in evaluate.CLOCKS],
            [
                "2026-07-10T14:30:00+00:00",
                "2026-07-10T18:00:00+00:00",
                "2026-07-10T21:00:00+00:00",
                "2026-07-11T00:00:00+00:00",
                "2026-07-11T03:00:00+00:00",
            ],
        )

    def test_selection_retains_one_highest_edge_row_per_date(self) -> None:
        rows = [
            {"clock_id": "prior_1800z", "candidate": True, "market_date": "2026-05-08", "conservative_edge": "0.0200", "no_limit": "0.80", "market_ticker": "B"},
            {"clock_id": "prior_1800z", "candidate": True, "market_date": "2026-05-08", "conservative_edge": "0.0300", "no_limit": "0.85", "market_ticker": "A"},
            {"clock_id": "market_0000z", "candidate": True, "market_date": "2026-05-08", "conservative_edge": "0.0400", "no_limit": "0.70", "market_ticker": "C"},
        ]
        selected = evaluate.select_rows(
            rows, "prior_1800z", dt.date(2026, 5, 8), dt.date(2026, 5, 8),
        )
        self.assertEqual([row["market_ticker"] for row in selected], ["A"])

    def test_training_clock_qualification_has_exact_adjacent_boundaries(self) -> None:
        rows = []
        for index in range(10):
            rows.append({
                "station_id": f"K{index % 5}",
                "submission_return": "0",
                "executable_trade": {"trade_id": str(index)} if index < 5 else None,
            })
        self.assertTrue(evaluate.training_diagnostic(rows)["qualifies_for_clock_selection"])
        self.assertFalse(evaluate.training_diagnostic(rows[:9])["qualifies_for_clock_selection"])
        fewer_fills = [{**row, "executable_trade": None} if index == 4 else row for index, row in enumerate(rows)]
        self.assertFalse(evaluate.training_diagnostic(fewer_fills)["qualifies_for_clock_selection"])

    def test_trade_artifact_identity_includes_the_selected_clock(self) -> None:
        class Client:
            def __init__(self):
                self.labels = []

            def fetch(self, _url, label):
                self.labels.append(label)
                return {"trades": [], "cursor": ""}

        client = Client()
        base = {
            "market_ticker": "TEST-TICKER",
            "station_id": "KATL",
            "market_date": "2026-06-01",
            "decision_at": "2026-05-31T18:00:00Z",
            "no_limit": "0.80",
        }
        for clock_id in ("prior_1800z", "prior_2100z"):
            self.assertIsNone(evaluate.executable_trade(
                client, {**base, "clock_id": clock_id}, "2026-06-29T00:00:00Z",
            ))
        self.assertEqual(len(set(client.labels)), 2)

    def test_held_out_diagnostic_passes_full_synthetic_boundary(self) -> None:
        rows = []
        start = dt.date(2026, 6, 27)
        for index in range(40):
            outcome = 0 if index in (9, 29) else 1
            fill_price = Decimal("0.80")
            fill_fee = evaluate.price.fee(fill_price)
            rows.append({
                "market_date": str(start + dt.timedelta(days=index)),
                "station_id": f"K{index % 10:03d}",
                "outcome_no": outcome,
                "no_limit": "0.8000",
                "submission_return": str(Decimal(1) - fill_price - fill_fee if outcome else -fill_price - fill_fee),
                "executable_trade": {"no_price": "0.8000", "fee": str(fill_fee)},
            })
        result = evaluate.held_out_diagnostic(rows)
        self.assertTrue(result["development_support_passes"])
        self.assertEqual(result["failed_development_gates"], [])
        self.assertGreater(Decimal(result["lower_90_submission_return"]), 0)
        self.assertFalse(result["gates"]["scale_250_date_clustered_95"])


if __name__ == "__main__":
    unittest.main()
