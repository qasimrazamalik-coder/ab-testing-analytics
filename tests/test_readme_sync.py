"""README results block must be generated from reports/results.json, never hand-typed."""

import json
import tempfile
import unittest
from pathlib import Path

from abtest import readme_sync

ROOT = Path(__file__).resolve().parents[1]


class ReadmeSync(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.results = ROOT / "reports" / "results.json"

    def test_missing_markers_reported(self):
        readme = self.dir / "R.md"
        readme.write_text("# no markers here\n")
        self.assertEqual(readme_sync.sync(readme, self.results), 2)

    def test_sync_then_check_is_clean(self):
        readme = self.dir / "R.md"
        readme.write_text(f"intro\n{readme_sync.START}\nold\n{readme_sync.END}\noutro\n")
        self.assertEqual(readme_sync.sync(readme, self.results), 0)
        self.assertEqual(readme_sync.sync(readme, self.results, check=True), 0)
        self.assertTrue(readme.read_text().startswith("intro\n"))
        self.assertTrue(readme.read_text().endswith("outro\n"))

    def test_stale_block_is_detected(self):
        readme = self.dir / "R.md"
        readme.write_text(f"{readme_sync.START}\nstale\n{readme_sync.END}\n")
        self.assertEqual(readme_sync.sync(readme, self.results, check=True), 1)

    def test_block_contains_the_verdict_from_results(self):
        block = readme_sync.render_block(json.loads(self.results.read_text()))
        verdict = json.loads(self.results.read_text())["verdict"]["decision"]
        self.assertIn(verdict, block)

    def test_committed_readme_is_in_sync(self):
        readme = ROOT / "README.md"
        if not readme.exists():
            self.skipTest("README.md not written yet")
        self.assertEqual(readme_sync.sync(readme, self.results, check=True), 0)


if __name__ == "__main__":
    unittest.main()
