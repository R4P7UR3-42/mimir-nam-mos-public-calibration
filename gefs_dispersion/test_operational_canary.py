import unittest

import operational_canary as canary


def exact_index(member: str = "c00", step: int = 27) -> bytes:
    ensemble = "low-res ctl" if member == "c00" else f"+{canary.MEMBER_NUMBERS[member]}"
    descriptors = [
        "PRES:surface:27 hour fcst:ENS=" + ensemble,
        f"TMP:2 m above ground:{step} hour fcst:ENS={ensemble}",
        "RH:2 m above ground:27 hour fcst:ENS=" + ensemble,
    ]
    return ("\n".join(
        f"{index}:{(index - 1) * 100}:d={canary.INITIALIZATION}:{descriptor}"
        for index, descriptor in enumerate(descriptors, start=1)
    ) + "\n").encode()


class OperationalCanaryTests(unittest.TestCase):
    def test_object_key_preserves_exact_operational_layout(self):
        self.assertEqual(
            canary.object_key("c00", 27),
            "gefs.20260828/00/atmos/pgrb2sp25/gec00.t00z.pgrb2s.0p25.f027",
        )
        self.assertEqual(
            canary.object_key("p04", 57),
            "gefs.20260828/00/atmos/pgrb2sp25/gep04.t00z.pgrb2s.0p25.f057",
        )

    def test_field_range_requires_exact_member_and_next_boundary(self):
        self.assertEqual(canary.parse_field_range(exact_index(), "c00", 27), (100, 199))
        self.assertEqual(canary.parse_field_range(exact_index("p04", 57), "p04", 57), (100, 199))
        with self.assertRaisesRegex(ValueError, "missing or ambiguous"):
            canary.parse_field_range(exact_index().replace(b"TMP", b"TMAX"), "c00", 27)
        with self.assertRaisesRegex(ValueError, "no exact end"):
            canary.parse_field_range(b"1:0:d=2026082800:TMP:2 m above ground:27 hour fcst:ENS=low-res ctl\n", "c00", 27)

    def test_field_range_rejects_identity_and_order_drift(self):
        with self.assertRaisesRegex(ValueError, "identity"):
            canary.parse_field_range(exact_index().replace(b"2026082800", b"2026082812", 1), "c00", 27)
        with self.assertRaisesRegex(ValueError, "order"):
            canary.parse_field_range(exact_index().replace(b"2:100", b"3:100", 1), "c00", 27)

    def test_request_budget_is_exact_and_terminal(self):
        budget = canary.RequestBudget(110)
        for _ in range(110):
            budget.reserve()
        with self.assertRaisesRegex(ValueError, "exhausted"):
            budget.reserve()
        with self.assertRaisesRegex(ValueError, "exactly 110"):
            canary.RequestBudget(111)


if __name__ == "__main__":
    unittest.main()
