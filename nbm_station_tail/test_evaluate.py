import datetime as dt
import importlib.util
import unittest
from decimal import Decimal
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).with_name("evaluate.py")
SPEC = importlib.util.spec_from_file_location("nbm_station_tail_evaluate", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
evaluate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evaluate)


class NbmStationTailTest(unittest.TestCase):
    def test_frozen_parent_inputs_and_station_training_are_exact(self) -> None:
        rows, stations = evaluate.parent.load_model_rows()
        training = evaluate.parent.training_rows(rows)
        counts = {}
        for row in training:
            counts[row["station_id"]] = counts.get(row["station_id"], 0) + 1
        self.assertEqual(len(rows), 1_980)
        self.assertEqual(len(stations), 20)
        self.assertEqual(set(counts.values()), {50})
        self.assertEqual(
            evaluate.parent.price.file_sha256(Path(__file__).with_name("PREDECLARATION.md")),
            evaluate.PREDECLARATION_SHA256,
        )

    def test_wilson_boundary_is_station_specific_and_conservative(self) -> None:
        self.assertGreaterEqual(evaluate.wilson_lower(48, 50), Decimal("0.9000"))
        self.assertLess(evaluate.wilson_lower(47, 50), Decimal("0.9000"))
        with self.assertRaisesRegex(ValueError, "invalid"):
            evaluate.wilson_lower(51, 50)

    def test_station_score_never_exceeds_pooled_ceiling_and_adjacent_fails(self) -> None:
        rows = []
        for station_index in range(20):
            for date_index in range(50):
                successes = 48 if station_index == 0 else 50
                rows.append({
                    "station_id": f"K{station_index:03d}",
                    "market_date": str(dt.date(2026, 5, 8) + dt.timedelta(days=date_index)),
                    "residual_f": "0" if date_index < successes else "10",
                })
        structures = [{"strike_type": "greater", "offset_f": "5"}]
        pooled = {
            "greater:5": {
                "reason": "eligible_score", "eligible": True, "score": "0.9500",
            }
        }
        with mock.patch.object(evaluate.parent, "derive_score_table", return_value=pooled):
            table, returned_pooled = evaluate.derive_station_score_table(rows, structures)
        self.assertEqual(returned_pooled, pooled)
        self.assertTrue(table["K000|greater:5"]["eligible"])
        self.assertLessEqual(Decimal(table["K000|greater:5"]["score"]), Decimal("0.9500"))
        self.assertEqual(table["K001|greater:5"]["score"], "0.9500")

        for row in rows:
            if row["station_id"] == "K000" and row["market_date"] == "2026-06-24":
                row["residual_f"] = "10"
        with mock.patch.object(evaluate.parent, "derive_score_table", return_value=pooled):
            table, _ = evaluate.derive_station_score_table(rows, structures)
        self.assertFalse(table["K000|greater:5"]["eligible"])
        self.assertEqual(table["K000|greater:5"]["reason"], "station_wilson90_score_below_0.9000")

    def test_pooled_rejection_cannot_be_reopened_by_station_result(self) -> None:
        rows = [
            {
                "station_id": f"K{station_index:03d}",
                "market_date": str(dt.date(2026, 5, 8) + dt.timedelta(days=date_index)),
                "residual_f": "0",
            }
            for station_index in range(20) for date_index in range(50)
        ]
        pooled = {
            "greater:5": {
                "reason": "station_robust_score_below_0.9000", "eligible": False, "score": "0.8999",
            }
        }
        with mock.patch.object(evaluate.parent, "derive_score_table", return_value=pooled):
            table, _ = evaluate.derive_station_score_table(rows, [{"strike_type": "greater", "offset_f": "5"}])
        self.assertTrue(all(not row["eligible"] for row in table.values()))
        self.assertTrue(all(row["score"] is None for row in table.values()))


if __name__ == "__main__":
    unittest.main()
