from pathlib import Path
import unittest


class WorkflowTest(unittest.TestCase):
    def test_workflow_is_manual_order_free_and_single_run_attempt(self):
        workflow = (Path(__file__).parent.parent / ".github/workflows/nbm-qmd-evaluation.yml").read_text()
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("schedule:", workflow)
        self.assertNotIn("pull_request:", workflow)
        self.assertNotIn("push:", workflow)
        self.assertIn("github.run_attempt == 1", workflow)
        self.assertEqual(workflow.count("--input inputs/"), 4)
        self.assertNotIn("--allow-net", workflow)
        self.assertNotIn("secrets.", workflow)
        self.assertIn("retention-days: 1", workflow)
        self.assertIn("active_trading_capability_changed:false", workflow)
        self.assertIn("automatic_production_activation:false", workflow)


if __name__ == "__main__":
    unittest.main()
