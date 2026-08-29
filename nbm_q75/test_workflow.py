from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent.parent


class WorkflowTest(unittest.TestCase):
    def test_workflow_is_single_attempt_public_and_non_authorizing(self) -> None:
        text = (ROOT / ".github/workflows/nbm-q75-development.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("github.run_attempt == 1", text)
        self.assertIn("runs-on: ubuntu-latest", text)
        self.assertIn("--max-requests 3000", text)
        self.assertIn("noaa_nbm_v5_q75_station_robust_midnight_split_development_v1", text)
        self.assertIn("retention-days: 1", text)
        self.assertIn("active_trading_capability_changed:false", text)
        self.assertIn("production_database_accessed:false", text)
        self.assertNotIn("pull_request:", text)
        self.assertNotIn("schedule:", text)
        self.assertNotIn("secrets.", text)
        self.assertNotIn("KALSHI", text)
        self.assertNotIn("self-hosted", text)
        self.assertNotIn("/var/lib/mimir", text)
        self.assertNotIn("curl --retry", text)


if __name__ == "__main__":
    unittest.main()
