import unittest

import canary


def exact_index() -> bytes:
    lines = []
    for ordinal, step in enumerate(range(3, 64, 3), start=1):
        lines.append(
            f"{ordinal}:{(ordinal - 1) * 100}:d=2019082900:TMP:2 m above ground:{step} hour fcst:ENS=low-res ctl"
        )
    return ("\n".join(lines) + "\n").encode()


class CanaryTests(unittest.TestCase):
    def test_exact_range_selects_27_through_before_60(self):
        rows = canary.parse_index(exact_index())
        self.assertEqual(canary.exact_range(rows), (800, 1899))

    def test_index_rejects_identity_or_missing_boundary(self):
        with self.assertRaisesRegex(ValueError, "identity"):
            canary.parse_index(exact_index().replace(b"TMP", b"TMAX", 1))
        rows = [row for row in canary.parse_index(exact_index()) if row["step"] != 60]
        with self.assertRaisesRegex(ValueError, "missing"):
            canary.exact_range(rows)

    def test_index_rejects_duplicate_step(self):
        rows = canary.parse_index(exact_index())
        rows[-1]["step"] = rows[-2]["step"]
        with self.assertRaisesRegex(ValueError, "duplicate"):
            canary.exact_range(rows)


if __name__ == "__main__":
    unittest.main()
