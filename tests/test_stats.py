"""Statistical engine tests. Expected values are computed by hand or by an independent route
(math.erfc), never by calling the function under test a second time."""

import math
import unittest

import numpy as np

from abtest import stats


def _norm_sf2(z: float) -> float:
    """Two-sided normal tail probability via erfc: independent of scipy."""
    return math.erfc(abs(z) / math.sqrt(2))


class TwoProportionTest(unittest.TestCase):
    def test_hand_computed_z_and_p(self):
        # 200/1000 vs 240/1000. Pooled p = 0.22, SE = sqrt(.22*.78*(2/1000)) = 0.018526
        # z = 0.04 / 0.018526 = 2.1591
        r = stats.two_proportion_test(200, 1000, 240, 1000)
        self.assertAlmostEqual(r.diff, 0.04, places=12)
        self.assertAlmostEqual(r.z, 2.1591, places=3)
        self.assertAlmostEqual(r.p_value, _norm_sf2(r.z), places=10)
        self.assertAlmostEqual(r.p_value, 0.0308, places=3)

    def test_interval_uses_unpooled_se(self):
        r = stats.two_proportion_test(200, 1000, 240, 1000)
        se = math.sqrt(0.2 * 0.8 / 1000 + 0.24 * 0.76 / 1000)
        self.assertAlmostEqual(r.ci_low, 0.04 - 1.959964 * se, places=5)
        self.assertAlmostEqual(r.ci_high, 0.04 + 1.959964 * se, places=5)

    def test_identical_arms_give_p_one(self):
        r = stats.two_proportion_test(300, 1000, 300, 1000)
        self.assertEqual(r.diff, 0.0)
        self.assertAlmostEqual(r.p_value, 1.0, places=12)

    def test_sign_flips_with_arm_order(self):
        a = stats.two_proportion_test(200, 1000, 240, 1000)
        b = stats.two_proportion_test(240, 1000, 200, 1000)
        self.assertAlmostEqual(a.diff, -b.diff, places=12)
        self.assertAlmostEqual(a.p_value, b.p_value, places=12)


class SRM(unittest.TestCase):
    def test_hand_computed_chi_square(self):
        # 5500 vs 4500, expected 5000 each: chi2 = 250000/5000 * 2 = 100
        r = stats.srm_check(5500, 4500)
        self.assertAlmostEqual(r.chi2, 100.0, places=9)
        self.assertFalse(r.passed)
        self.assertLess(r.p_value, 1e-20)

    def test_balanced_split_passes(self):
        self.assertTrue(stats.srm_check(5000, 5000).passed)

    def test_threshold_is_strict_alpha_not_conventional(self):
        # 5100/4900: chi2 = 4.0, p ~ 0.0455. Suspicious at 0.05 but NOT an SRM at 0.001 (ADR-001).
        r = stats.srm_check(5100, 4900)
        self.assertAlmostEqual(r.chi2, 4.0, places=9)
        self.assertGreater(r.p_value, 0.001)
        self.assertTrue(r.passed)
        # 5200/4800: chi2 = 16.0, p ~ 6e-5 -> below 0.001, must fail.
        self.assertFalse(stats.srm_check(5200, 4800).passed)

    def test_unequal_design_split(self):
        # A 70/30 design that delivers exactly 70/30 must pass.
        self.assertTrue(stats.srm_check(7000, 3000, expected_control_share=0.7).passed)

    def test_rejects_degenerate_share(self):
        with self.assertRaises(ValueError):
            stats.srm_check(10, 10, expected_control_share=1.0)


class Holm(unittest.TestCase):
    def test_textbook_example(self):
        # sorted: .01*3=.03, .03*2=.06, .04*1=.04 -> enforce monotone: .03, .06, .06
        adj = stats.holm_bonferroni({"a": 0.01, "b": 0.04, "c": 0.03})
        self.assertAlmostEqual(adj["a"], 0.03, places=12)
        self.assertAlmostEqual(adj["c"], 0.06, places=12)
        self.assertAlmostEqual(adj["b"], 0.06, places=12)

    def test_capped_at_one(self):
        adj = stats.holm_bonferroni({"a": 0.6, "b": 0.7})
        self.assertTrue(all(v <= 1.0 for v in adj.values()))

    def test_never_below_raw(self):
        raw = {"a": 0.001, "b": 0.2, "c": 0.04}
        adj = stats.holm_bonferroni(raw)
        for k in raw:
            self.assertGreaterEqual(adj[k], raw[k])


class PowerAndSampleSize(unittest.TestCase):
    def test_known_sample_size(self):
        # p 0.20 -> 0.22, alpha .05, power .80: standard formula gives ~6,500 per arm.
        n = stats.sample_size_two_proportions(0.20, 0.02)
        self.assertTrue(6300 <= n <= 6700, n)

    def test_power_roundtrip(self):
        n = stats.sample_size_two_proportions(0.20, 0.02)
        self.assertGreaterEqual(stats.power_two_proportions(0.20, 0.22, n), 0.80)
        self.assertLess(stats.power_two_proportions(0.20, 0.22, int(n * 0.9)), 0.80)

    def test_mde_roundtrip(self):
        n = 20000
        mde = stats.mde_two_proportions(0.20, n)
        self.assertAlmostEqual(stats.power_two_proportions(0.20, 0.20 + mde, n), 0.80, places=2)

    def test_monte_carlo_matches_analytic_power(self):
        """Simulate the experiment: the empirical rejection rate must match the formula."""
        rng = np.random.default_rng(123)
        p1, p2 = 0.20, 0.22
        n = stats.sample_size_two_proportions(p1, p2 - p1)
        reps, rejected = 1500, 0
        for _ in range(reps):
            xc = rng.binomial(n, p1)
            xt = rng.binomial(n, p2)
            if stats.two_proportion_test(xc, n, xt, n).p_value < 0.05:
                rejected += 1
        self.assertAlmostEqual(rejected / reps, 0.80, delta=0.04)

    def test_aa_false_positive_rate_is_nominal(self):
        rng = np.random.default_rng(321)
        n, reps, rejected = 5000, 2000, 0
        for _ in range(reps):
            xc, xt = rng.binomial(n, 0.2), rng.binomial(n, 0.2)
            if stats.two_proportion_test(xc, n, xt, n).p_value < 0.05:
                rejected += 1
        self.assertAlmostEqual(rejected / reps, 0.05, delta=0.015)


class Bootstrap(unittest.TestCase):
    def test_deterministic_for_a_seed(self):
        rng = np.random.default_rng(0)
        a, b = rng.lognormal(3, 1, 2000), rng.lognormal(3, 1, 2000)
        r1 = stats.bootstrap_relative_change(a, b, n_boot=300, seed=5)
        r2 = stats.bootstrap_relative_change(a, b, n_boot=300, seed=5)
        self.assertEqual(r1, r2)


if __name__ == "__main__":
    unittest.main()
