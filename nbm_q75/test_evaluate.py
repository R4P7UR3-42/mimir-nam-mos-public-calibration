import datetime as dt
import importlib.util
import unittest
from decimal import Decimal
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).with_name("evaluate.py")
SPEC = importlib.util.spec_from_file_location("nbm_q75_evaluate", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
evaluate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evaluate)


class NbmQ75Test(unittest.TestCase):
    def test_frozen_parent_q75_coverage_is_exact(self) -> None:
        rows, stations = evaluate.load_q75_rows()
        self.assertEqual(len(rows), 1_980)
        self.assertEqual(len(stations), 20)
        self.assertEqual(len({row["market_date"] for row in rows}), 99)
        self.assertEqual(len({row["station_id"] for row in rows}), 20)
        self.assertTrue(all(Decimal(row["q75_f"]) == Decimal(row["q75_f"]).to_integral_value() for row in rows))

    def test_training_score_uses_worst_station_robust_lower_bound_and_floor(self) -> None:
        rows = []
        start = evaluate.TRAINING_START
        for date_index in range(50):
            for station_index in range(20):
                rows.append({
                    "market_date": str(start + dt.timedelta(days=date_index)),
                    "station_id": f"K{station_index:03d}",
                    "observed_high_f": "70" if (date_index + station_index) % 10 else "80",
                    "q75_f": "75",
                })
        lowers = [Decimal("0.82709")] + [Decimal("0.81999")] + [Decimal("0.82555")] * 19
        with mock.patch.object(evaluate.price, "clustered_lower", side_effect=lowers):
            result = evaluate.derive_training_score(rows)
        self.assertEqual(result["frozen_score"], "0.8199")
        self.assertTrue(result["passes_minimum_score"])
        self.assertEqual(len(result["station_holdouts"]), 20)

    def test_exact_q75_contract_accepts_only_exact_greater_identity(self) -> None:
        row = {"q75_f": "75", "observed_high_f": "75", "series_ticker": "SERIES"}
        market = {
            "ticker": "SERIES-26JUN27-T75",
            "event_ticker": "SERIES-26JUN27",
            "strike_type": "greater",
            "floor_strike": "75",
            "cap_strike": None,
            "market_type": "binary",
            "result": "no",
            "yes_sub_title": "76° or above",
            "is_provisional": False,
            "mve_collection_ticker": None,
            "fee_waiver_expiration_time": None,
        }
        self.assertEqual(evaluate.exact_q75_market(row, [market]), market)
        self.assertIsNone(evaluate.exact_q75_market(row, [{**market, "floor_strike": "76"}]))
        with self.assertRaisesRegex(ValueError, "identity is invalid"):
            evaluate.exact_q75_market(row, [{**market, "strike_type": "greater", "result": "yes"}])

    def test_price_and_edge_boundaries_are_exact(self) -> None:
        score = Decimal("0.8189")
        exact_min = evaluate.apply_score({"no_limit": "0.50"}, score)
        self.assertTrue(exact_min["candidate"])
        self.assertFalse(evaluate.apply_score({"no_limit": "0.49"}, score)["candidate"])
        self.assertFalse(evaluate.apply_score({"no_limit": "0.85"}, score)["candidate"])
        edge_limit = Decimal("0.79")
        edge_score = edge_limit + evaluate.price.fee(edge_limit) + evaluate.MIN_EDGE
        at_edge = evaluate.apply_score({"no_limit": str(edge_limit)}, edge_score)
        self.assertEqual(Decimal(at_edge["conservative_edge"]), evaluate.MIN_EDGE)
        self.assertTrue(at_edge["candidate"])
        below_edge = evaluate.apply_score({"no_limit": str(edge_limit + Decimal("0.0001"))}, edge_score)
        self.assertFalse(below_edge["candidate"])

    def test_dynamic_score_drives_held_out_diagnostic(self) -> None:
        rows = []
        start = evaluate.HELD_OUT_START
        score = Decimal("0.8189")
        for index in range(40):
            outcome = 0 if index in (5, 11, 17, 23, 29, 35, 39) else 1
            fill_price = Decimal("0.70")
            fee = evaluate.price.fee(fill_price)
            rows.append({
                "market_date": str(start + dt.timedelta(days=index)),
                "station_id": f"K{index % 10:03d}",
                "outcome_no": outcome,
                "no_limit": "0.7000",
                "submission_return": str(Decimal(1) - fill_price - fee if outcome else -fill_price - fee),
                "executable_trade": {"no_price": "0.7000", "fee": str(fee)},
            })
        result = evaluate.held_out_metrics(rows, score)
        self.assertTrue(result["development_support_passes"])
        self.assertEqual(evaluate.price.PROBABILITY, Decimal("0.933000"))


if __name__ == "__main__":
    unittest.main()
