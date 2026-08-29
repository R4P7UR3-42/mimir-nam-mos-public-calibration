from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github/workflows/gefs-dispersion-canary.yml"
EVALUATION_WORKFLOW = ROOT / ".github/workflows/gefs-dispersion-evaluation.yml"
OPERATIONAL_WORKFLOW = ROOT / ".github/workflows/gefs-operational-compatibility.yml"


class WorkflowTests(unittest.TestCase):
    def test_public_canary_is_fixed_order_free_and_terminal(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("github.run_attempt == 1", text)
        self.assertIn("--max-requests 3", text)
        self.assertIn("env -u LD_LIBRARY_PATH", text)
        self.assertIn("steps.canary.outcome != 'success'", text)
        self.assertIn("retention-days: 1", text)
        self.assertNotIn("schedule:", text)
        self.assertNotIn("secrets.", text)
        self.assertNotIn("/var/lib/mimir", text)
        self.assertNotIn("kalshi", text.lower())

    def test_workflow_pins_every_action_to_a_commit(self):
        for path in (WORKFLOW, EVALUATION_WORKFLOW, OPERATIONAL_WORKFLOW):
            for line in path.read_text(encoding="utf-8").splitlines():
                if "uses:" in line:
                    reference = line.split("uses:", 1)[1].strip().split()[0]
                    self.assertRegex(reference, r"^[^@]+@[0-9a-f]{40}$")

    def test_full_evaluation_is_bounded_resumable_and_non_authorizing(self):
        text = EVALUATION_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("--max-requests 3900", text)
        self.assertIn("--concurrency 10", text)
        self.assertIn("digest-mismatch: error", text)
        self.assertIn("sha256sum -c SHA256SUMS", text)
        self.assertIn("github.run_attempt == 1", text)
        self.assertIn("steps.capture.outcome != 'success' || steps.evaluate.outcome != 'success'", text)
        self.assertNotIn("schedule:", text)
        self.assertNotIn("secrets.", text)
        self.assertNotIn("/var/lib/mimir", text)
        self.assertNotIn("kalshi", text.lower())

    def test_operational_canary_is_bounded_order_free_and_terminal(self):
        text = OPERATIONAL_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("--max-requests 110", text)
        self.assertIn("--concurrency 10", text)
        self.assertIn("github.run_attempt == 1", text)
        self.assertIn("steps.canary.outcome != 'success'", text)
        self.assertIn("retention-days: 1", text)
        self.assertNotIn("schedule:", text)
        self.assertNotIn("secrets.", text)
        self.assertNotIn("/var/lib/mimir", text)
        self.assertNotIn("kalshi", text.lower())


if __name__ == "__main__":
    unittest.main()
