from pathlib import Path
import unittest


class WorkflowTest(unittest.TestCase):
    def test_workflow_is_manual_main_only_and_preserves_failure_artifact(self) -> None:
        text = Path(".github/workflows/gfs-mos-precipitation-development.yml").read_text()
        self.assertIn("workflow_dispatch", text)
        self.assertIn("github.ref == 'refs/heads/main'", text)
        self.assertIn("continue-on-error: true", text)
        self.assertIn("if: always()", text)
        self.assertIn("retention-days: 1", text)

    def test_workflow_binds_freeze_and_exact_request_budget(self) -> None:
        text = Path(".github/workflows/gfs-mos-precipitation-development.yml").read_text()
        self.assertIn("c5f44f308db1e3d579bb4a99dd528636e0f6d2aee19a6bb10c64baf4f1863edc", text)
        self.assertIn("297e7cdf081c38212c3a1298d09921dfcb79fff9f3fa3bae6ccafc3b8ed09d12", text)
        self.assertIn("--max-requests 24", text)
        self.assertNotIn("2026-07-31&", text)


if __name__ == "__main__":
    unittest.main()
