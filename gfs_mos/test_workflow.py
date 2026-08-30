from pathlib import Path
import unittest


class GfsWorkflowTest(unittest.TestCase):
    def test_workflow_is_fixed_order_free_and_terminal(self) -> None:
        text = Path(".github/workflows/gfs-mos-calibration.yml").read_text()
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("runs-on: ubuntu-latest", text)
        self.assertIn("timeout-minutes: 60", text)
        self.assertIn("--max-requests 23", text)
        self.assertIn("gfs_mos/capture_gfs.py", text)
        self.assertIn("gfs_mos/evaluate_gfs.py", text)
        self.assertIn("historical_price_data_inspected:false", text)
        self.assertIn("active_trading_capability_changed:false", text)
        self.assertIn("if: always()", text)
        self.assertIn("retention-days: 1", text)
        self.assertNotIn("pull_request:", text)
        self.assertNotIn("schedule:", text)
        self.assertNotIn("KALSHI", text)
        self.assertNotIn("/var/lib/mimir", text)
        self.assertNotIn("curl --retry", text)


if __name__ == "__main__":
    unittest.main()
