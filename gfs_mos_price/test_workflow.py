from pathlib import Path
import unittest


class WorkflowTest(unittest.TestCase):
    def test_workflow_is_public_order_free_and_terminal(self) -> None:
        text = Path(".github/workflows/gfs-mos-executable-oos.yml").read_text()
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("runs-on: ubuntu-latest", text)
        self.assertIn("timeout-minutes: 90", text)
        self.assertIn("--max-requests 13", text)
        self.assertIn("--max-requests 12000", text)
        self.assertIn("historical_price_data_inspected:false", text)
        self.assertIn("active_trading_capability_changed:false", text)
        self.assertIn("retention-days: 1", text)
        self.assertIn("if: always()", text)
        self.assertNotIn("pull_request:", text)
        self.assertNotIn("schedule:", text)
        self.assertNotIn("KALSHI_API", text)
        self.assertNotIn("/var/lib/mimir", text)
        self.assertNotIn("curl --retry", text)


if __name__ == "__main__":
    unittest.main()
