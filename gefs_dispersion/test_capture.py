import datetime as dt
import unittest

import capture


def index_payload(initialization: dt.date, member: str) -> bytes:
    cycle = initialization.strftime("%Y%m%d00")
    ensemble = "low-res ctl" if member == "c00" else f"+{capture.MEMBER_NUMBERS[member]}"
    return ("\n".join(
        f"{ordinal}:{(ordinal - 1) * 100}:d={cycle}:TMP:2 m above ground:{step} hour fcst:ENS={ensemble}"
        for ordinal, step in enumerate(range(3, 64, 3), start=1)
    ) + "\n").encode()


class CaptureTests(unittest.TestCase):
    def test_frozen_calendar_and_key_are_exact(self):
        targets, evaluation = capture.frozen_dates()
        self.assertEqual((len(targets), targets[0], targets[-1]), (370, dt.date(2018, 12, 27), dt.date(2019, 12, 31)))
        self.assertEqual((len(evaluation), evaluation[0], evaluation[-1]), (250, dt.date(2019, 4, 26), dt.date(2019, 12, 31)))
        self.assertEqual(
            capture.member_key(dt.date(2019, 8, 29), "p01"),
            "GEFSv12/reforecast/2019/2019082900/p01/Days:1-10/tmp_2m_2019082900_p01.grib2",
        )

    def test_index_accepts_exact_control_and_perturbed_identity(self):
        for member in capture.MEMBERS:
            rows = capture.parse_index(index_payload(dt.date(2019, 8, 29), member), dt.date(2019, 8, 29), member)
            self.assertEqual(capture.exact_range(rows), (800, 1899))

    def test_index_fails_adjacent_member_cycle_and_parameter(self):
        payload = index_payload(dt.date(2019, 8, 29), "p01")
        with self.assertRaisesRegex(ValueError, "identity"):
            capture.parse_index(payload, dt.date(2019, 8, 29), "p02")
        with self.assertRaisesRegex(ValueError, "identity"):
            capture.parse_index(payload, dt.date(2019, 8, 28), "p01")
        with self.assertRaisesRegex(ValueError, "identity"):
            capture.parse_index(payload.replace(b"TMP", b"TMAX", 1), dt.date(2019, 8, 29), "p01")

    def test_request_and_concurrency_boundaries_are_frozen(self):
        self.assertEqual(capture.RequestBudget(3900).maximum, 3900)
        with self.assertRaisesRegex(ValueError, "exactly 3,900"):
            capture.RequestBudget(3899)


if __name__ == "__main__":
    unittest.main()
