from pathlib import Path
import unittest


class WorkflowTest(unittest.TestCase):
    def test_workflow_is_public_order_free_and_terminal(self) -> None:
        text = Path("../.github/workflows/market-implied-calibration.yml").read_text()
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("runs-on: ubuntu-latest", text)
        self.assertIn("--max-requests 5000", text)
        self.assertIn("retention-days: 1", text)
        self.assertIn("active_trading_capability_changed:false", text)
        self.assertIn("production_database_accessed:false", text)
        self.assertNotIn("pull_request:", text)
        self.assertNotIn("schedule:", text)
        self.assertNotIn("KALSHI", text)
        self.assertNotIn("/var/lib/mimir", text)
        self.assertNotIn("curl --retry", text)


if __name__ == "__main__":
    unittest.main()
