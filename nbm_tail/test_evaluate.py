import datetime as dt
import importlib.util
import unittest
from decimal import Decimal
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).with_name("evaluate.py")
SPEC = importlib.util.spec_from_file_location("nbm_tail_evaluate", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
evaluate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evaluate)


class NbmTailTest(unittest.TestCase):
    def test_frozen_q50_and_training_coverage_are_exact(self) -> None:
        rows, stations = evaluate.load_model_rows()
        training = evaluate.training_rows(rows)
        self.assertEqual(len(rows), 1_980)
        self.assertEqual(len(stations), 20)
        self.assertEqual(len(training), 1_000)
        self.assertEqual(len({row["market_date"] for row in training}), 50)
        self.assertTrue(all(Decimal(row["q50_f"]) == Decimal(row["q50_f"]).to_integral_value() for row in rows))

    def test_tail_structure_and_outcome_arithmetic_are_exact(self) -> None:
        row = {"station_id": "KTEST", "market_date": "2026-07-01", "q50_f": "75", "observed_high_f": "80"}
        base = {
            "ticker": "TEST",
            "market_type": "binary",
            "status": "finalized",
            "is_provisional": False,
            "mve_collection_ticker": None,
            "fee_waiver_expiration_time": None,
        }
        greater = {**base, "strike_type": "greater", "floor_strike": "81", "cap_strike": None,
                   "yes_sub_title": "82° or above", "result": "no"}
        structure = evaluate.tail_structure(row, greater)
        self.assertEqual(structure["score_key"], "greater:6")
        self.assertEqual(evaluate.provider_tail_outcome(row, greater, structure), (1, None))
        less = {**base, "strike_type": "less", "floor_strike": None, "cap_strike": "74",
                "yes_sub_title": "73° or below", "result": "no"}
        structure = evaluate.tail_structure(row, less)
        self.assertEqual(structure["score_key"], "less:-1")
        self.assertEqual(evaluate.provider_tail_outcome(row, less, structure), (1, None))
        self.assertIsNone(evaluate.tail_structure(row, {**base, "strike_type": "between"}))
        provider_no, conflict = evaluate.provider_tail_outcome(
            row, {**greater, "result": "yes"}, evaluate.tail_structure(row, greater),
        )
        self.assertEqual(provider_no, 0)
        self.assertEqual(conflict["provider_result"], "yes")

    def test_exact_known_ncei_conflict_identity_is_frozen(self) -> None:
        row = {"station_id": "KMIA", "market_date": "2026-07-07", "observed_high_f": "0"}
        market = {"ticker": "KXHIGHMIA-26JUL07-T88", "result": "no"}
        structure = {"strike_type": "less", "boundary_f": "88"}
        provider_no, conflict = evaluate.provider_tail_outcome(row, market, structure)
        self.assertEqual(provider_no, 1)
        self.assertEqual(conflict["identity"], evaluate.EXPECTED_OUTCOME_CONFLICT)

    def test_score_table_prescreens_and_uses_worst_robust_floor(self) -> None:
        rows = []
        start = evaluate.TRAINING_START
        for date_index in range(50):
            for station_index in range(20):
                rows.append({
                    "market_date": str(start + dt.timedelta(days=date_index)),
                    "station_id": f"K{station_index:03d}",
                    "residual_f": "0" if (date_index + station_index) % 20 else "10",
                })
        structures = [
            {"strike_type": "greater", "offset_f": "5"},
            {"strike_type": "greater", "offset_f": "-5"},
        ]
        lowers = [Decimal("0.93459"), Decimal("0.92555")] + [Decimal("0.93111")] * 19
        with mock.patch.object(evaluate.price, "clustered_lower", side_effect=lowers):
            table = evaluate.derive_score_table(rows, structures)
        self.assertEqual(table["greater:5"]["score"], "0.9255")
        self.assertTrue(table["greater:5"]["eligible"])
        self.assertEqual(table["greater:-5"]["reason"], "empirical_prescreen_below_0.920000")

    def test_price_edge_and_selection_rank_are_exact(self) -> None:
        score = Decimal("0.9400")
        self.assertTrue(evaluate.apply_score({"no_limit": "0.80"}, score)["candidate"])
        self.assertFalse(evaluate.apply_score({"no_limit": "0.54"}, score)["candidate"])
        self.assertFalse(evaluate.apply_score({"no_limit": "0.98"}, score)["candidate"])
        market_date = str(evaluate.HELD_OUT_START)
        rows = [
            {"candidate": True, "market_date": market_date, "conservative_edge": "0.0300",
             "conservative_probability": "0.9300", "no_limit": "0.80", "market_ticker": "B"},
            {"candidate": True, "market_date": market_date, "conservative_edge": "0.0300",
             "conservative_probability": "0.9400", "no_limit": "0.82", "market_ticker": "A"},
        ]
        self.assertEqual(evaluate.select_rows(rows)[0]["market_ticker"], "A")

    def test_two_tails_receive_distinct_artifact_station_identities(self) -> None:
        class Client:
            def __init__(self):
                self.labels = []

            def fetch(self, _url, label):
                self.labels.append(label)
                ticker = "UPPER" if "UPPER" in label else "LOWER"
                return {"ticker": ticker, "candlesticks": []}

        client = Client()
        station = {"station_id": "KATL", "series_ticker": "SERIES", "market_date": "2026-07-01"}
        base = {"event_ticker": "SERIES-26JUL01", "_source_partition": "live", "result": "no"}
        first = evaluate.capture_tail(client, station, {**base, "ticker": "UPPER"})
        second = evaluate.capture_tail(client, station, {**base, "ticker": "LOWER"})
        self.assertEqual(first["station_id"], "KATL")
        self.assertEqual(second["station_id"], "KATL")
        self.assertEqual(len(set(client.labels)), 2)
        self.assertIn("KATL-UPPER-2026-07-01-prior_1430z-candle", client.labels)
        self.assertIn("KATL-LOWER-2026-07-01-prior_1430z-candle", client.labels)

    def test_legacy_and_current_bid_schemas_are_exact_and_exclusive(self) -> None:
        self.assertEqual(
            evaluate.yes_bid_close({"yes_bid": {"close": "0.41"}}, "LEGACY"),
            (Decimal("0.41"), "close"),
        )
        self.assertEqual(
            evaluate.yes_bid_close({"yes_bid": {"close_dollars": "0.4100"}}, "CURRENT"),
            (Decimal("0.4100"), "close_dollars"),
        )
        self.assertEqual(evaluate.yes_bid_close({"yes_bid": {}}, "MISSING"), (None, None))
        with self.assertRaisesRegex(ValueError, "both close schemas"):
            evaluate.yes_bid_close(
                {"yes_bid": {"close": "0.41", "close_dollars": "0.4100"}}, "BOTH",
            )
        with self.assertRaisesRegex(ValueError, "malformed"):
            evaluate.yes_bid_close({"yes_bid": {"close_dollars": "0.41"}}, "MALFORMED")

    def test_current_boundary_bid_fails_closed_as_noncandidate(self) -> None:
        class Client:
            def fetch(self, _url, _label):
                decision = evaluate.time_model.decision_at(
                    dt.date(2026, 7, 1), evaluate.DECISION_CLOCK,
                )
                return {
                    "ticker": "UPPER",
                    "candlesticks": [{
                        "end_period_ts": int(decision.timestamp()),
                        "yes_bid": {"close_dollars": "0.0000"},
                    }],
                }

        station = {"station_id": "KATL", "series_ticker": "SERIES", "market_date": "2026-07-01"}
        market = {"ticker": "UPPER", "event_ticker": "SERIES-26JUL01", "_source_partition": "live", "result": "no"}
        self.assertEqual(evaluate.capture_tail(Client(), station, market)["reason"], "boundary_yes_bid")

    def test_variable_score_evaluation_passes_synthetic_boundary(self) -> None:
        rows = []
        for index in range(40):
            outcome = 0 if index in (7, 15, 23) else 1
            fill_price = Decimal("0.80")
            fee = evaluate.price.fee(fill_price)
            rows.append({
                "market_date": str(evaluate.HELD_OUT_START + dt.timedelta(days=index)),
                "station_id": f"K{index % 10:03d}",
                "outcome_no": outcome,
                "conservative_probability": "0.9200",
                "no_limit": "0.8000",
                "submission_return": str(Decimal(1) - fill_price - fee if outcome else -fill_price - fee),
                "executable_trade": {"no_price": "0.8000", "fee": str(fee)},
            })
        result = evaluate.evaluate_selections(rows)
        self.assertTrue(result["development_support_passes"])
        self.assertEqual(result["failed_development_gates"], [])


if __name__ == "__main__":
    unittest.main()
