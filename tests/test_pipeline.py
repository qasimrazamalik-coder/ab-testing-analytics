"""Decision rule and end-to-end pipeline tests."""

import json
import tempfile
import unittest
from pathlib import Path

from abtest import pipeline
from abtest.data import generate_cookie_cats_like, load_and_validate

OK_GUARD = {"passed": True}
BAD_GUARD = {"passed": False}


def _primary(p_adj: float, diff: float) -> dict:
    return {"p_adjusted": p_adj, "diff": diff}


class DecisionRule(unittest.TestCase):
    def d(self, srm, primary, guard):
        return pipeline.decide(srm, primary, guard, 0.05)["decision"]

    def test_srm_failure_overrides_everything(self):
        self.assertEqual(self.d(False, _primary(0.0001, 0.05), OK_GUARD), "INVALID")

    def test_not_significant_is_inconclusive(self):
        self.assertEqual(self.d(True, _primary(0.20, 0.01), OK_GUARD), "INCONCLUSIVE")

    def test_boundary_p_equal_alpha_is_inconclusive(self):
        self.assertEqual(self.d(True, _primary(0.05, 0.01), OK_GUARD), "INCONCLUSIVE")

    def test_significant_loss_is_do_not_ship(self):
        self.assertEqual(self.d(True, _primary(0.01, -0.01), OK_GUARD), "DO_NOT_SHIP")

    def test_win_with_failed_guardrail_is_hold(self):
        self.assertEqual(self.d(True, _primary(0.01, 0.01), BAD_GUARD), "HOLD")

    def test_win_with_guardrail_is_ship(self):
        self.assertEqual(self.d(True, _primary(0.01, 0.01), OK_GUARD), "SHIP")

    def test_loss_beats_guardrail_check(self):
        self.assertEqual(self.d(True, _primary(0.01, -0.01), BAD_GUARD), "DO_NOT_SHIP")


class EndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = Path(tempfile.mkdtemp())
        generate_cookie_cats_like(n_users=40000, seed=11).to_csv(cls.dir / "d.csv", index=False)
        cls.df = load_and_validate(cls.dir / "d.csv")
        cls.res = pipeline.analyze(cls.df, "synthetic", "abc", "d.csv", n_boot=200)

    def test_results_have_expected_sections(self):
        for key in ("data", "config", "srm", "metrics", "primary_metric", "guardrail", "power", "verdict"):
            self.assertIn(key, self.res)

    def test_provenance_is_recorded(self):
        self.assertEqual(self.res["data"]["provenance"], "synthetic")

    def test_rejects_unknown_provenance(self):
        with self.assertRaises(ValueError):
            pipeline.analyze(self.df, "made-up", "abc", "d.csv")

    def test_deterministic(self):
        again = pipeline.analyze(self.df, "synthetic", "abc", "d.csv", n_boot=200)
        self.assertEqual(json.dumps(again, sort_keys=True), json.dumps(self.res, sort_keys=True))

    def test_srm_broken_data_is_invalid(self):
        broken = generate_cookie_cats_like(n_users=40000, seed=11, treatment_share=0.45)
        path = self.dir / "b.csv"
        broken.to_csv(path, index=False)
        res = pipeline.analyze(load_and_validate(path), "synthetic", "x", "b.csv", n_boot=100)
        self.assertEqual(res["verdict"]["decision"], "INVALID")

    def test_null_effect_is_not_shipped(self):
        flat = generate_cookie_cats_like(n_users=40000, seed=12, effect_r1=0.0, effect_r7=0.0)
        path = self.dir / "f.csv"
        flat.to_csv(path, index=False)
        res = pipeline.analyze(load_and_validate(path), "synthetic", "x", "f.csv", n_boot=100)
        self.assertNotEqual(res["verdict"]["decision"], "SHIP")

    def test_write_results_roundtrip(self):
        out = self.dir / "r.json"
        pipeline.write_results(self.res, out)
        self.assertEqual(json.loads(out.read_text())["verdict"], self.res["verdict"])


if __name__ == "__main__":
    unittest.main()
