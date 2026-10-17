"""Statistical primitives for a two-arm experiment. Depends only on numpy and scipy."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import numpy as np
from scipy import stats
from scipy.optimize import brentq


@dataclass(frozen=True)
class ProportionTest:
    p_control: float
    p_treatment: float
    diff: float
    rel_lift: float | None
    z: float
    p_value: float
    ci_low: float
    ci_high: float

    def to_dict(self) -> dict:
        return asdict(self)


def two_proportion_test(
    x_control: int, n_control: int, x_treatment: int, n_treatment: int, alpha: float = 0.05
) -> ProportionTest:
    """Two-sided two-proportion z-test.

    The p-value uses the pooled standard error (the correct one under H0). The confidence
    interval for the difference uses the unpooled standard error (the correct one when
    reporting the size of the effect).
    """
    if n_control <= 0 or n_treatment <= 0:
        raise ValueError("both arms need at least one user")
    if not (0 <= x_control <= n_control and 0 <= x_treatment <= n_treatment):
        raise ValueError("successes must be between 0 and the arm size")

    p_c = x_control / n_control
    p_t = x_treatment / n_treatment
    diff = p_t - p_c

    pooled = (x_control + x_treatment) / (n_control + n_treatment)
    se_pooled = math.sqrt(pooled * (1 - pooled) * (1 / n_control + 1 / n_treatment))
    if se_pooled == 0:  # nobody (or everybody) converted in both arms
        z, p_value = 0.0, 1.0
    else:
        z = diff / se_pooled
        p_value = float(2 * stats.norm.sf(abs(z)))

    se_unpooled = math.sqrt(p_c * (1 - p_c) / n_control + p_t * (1 - p_t) / n_treatment)
    z_crit = float(stats.norm.ppf(1 - alpha / 2))
    return ProportionTest(
        p_control=p_c,
        p_treatment=p_t,
        diff=diff,
        rel_lift=(diff / p_c) if p_c > 0 else None,
        z=z,
        p_value=p_value,
        ci_low=diff - z_crit * se_unpooled,
        ci_high=diff + z_crit * se_unpooled,
    )


@dataclass(frozen=True)
class SRMResult:
    n_control: int
    n_treatment: int
    expected_control_share: float
    chi2: float
    p_value: float
    alpha: float
    passed: bool

    def to_dict(self) -> dict:
        return asdict(self)


def srm_check(
    n_control: int,
    n_treatment: int,
    expected_control_share: float = 0.5,
    alpha: float = 0.001,
) -> SRMResult:
    """Sample Ratio Mismatch: chi-square goodness of fit of the arm sizes vs the design split.

    A strict alpha (0.001) is the industry convention: SRM is a health check on assignment,
    so we only want to fire when something is clearly broken.
    """
    if not 0 < expected_control_share < 1:
        raise ValueError("expected_control_share must be strictly between 0 and 1")
    total = n_control + n_treatment
    expected = [total * expected_control_share, total * (1 - expected_control_share)]
    chi2, p_value = stats.chisquare([n_control, n_treatment], f_exp=expected)
    return SRMResult(
        n_control=int(n_control),
        n_treatment=int(n_treatment),
        expected_control_share=expected_control_share,
        chi2=float(chi2),
        p_value=float(p_value),
        alpha=alpha,
        passed=bool(p_value >= alpha),
    )


def holm_bonferroni(p_values: dict[str, float]) -> dict[str, float]:
    """Holm step-down adjusted p-values (controls family-wise error rate)."""
    m = len(p_values)
    ordered = sorted(p_values.items(), key=lambda kv: kv[1])
    adjusted: dict[str, float] = {}
    running_max = 0.0
    for rank, (name, p) in enumerate(ordered):
        running_max = max(running_max, min(1.0, (m - rank) * p))
        adjusted[name] = running_max
    return {name: adjusted[name] for name in p_values}


def bootstrap_relative_change(
    control: np.ndarray,
    treatment: np.ndarray,
    n_boot: int = 1000,
    alpha: float = 0.05,
    seed: int = 7,
) -> dict:
    """Percentile-bootstrap CI for the relative change in the mean (treatment / control - 1).

    Used for heavy-tailed engagement counts, where a t-interval on the mean is fragile.
    """
    c = np.asarray(control, dtype=float)
    t = np.asarray(treatment, dtype=float)
    if c.size == 0 or t.size == 0:
        raise ValueError("both arms need data")
    if c.mean() == 0:
        raise ValueError("control mean is zero; relative change is undefined")
    rng = np.random.default_rng(seed)
    rel = np.empty(n_boot)
    for i in range(n_boot):
        c_mean = c[rng.integers(0, c.size, c.size)].mean()
        t_mean = t[rng.integers(0, t.size, t.size)].mean()
        rel[i] = t_mean / c_mean - 1.0
    lo, hi = np.percentile(rel, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return {
        "control_mean": float(c.mean()),
        "treatment_mean": float(t.mean()),
        "rel_change": float(t.mean() / c.mean() - 1.0),
        "ci_low": float(lo),
        "ci_high": float(hi),
        "n_boot": n_boot,
    }


def power_two_proportions(p1: float, p2: float, n_per_arm: int, alpha: float = 0.05) -> float:
    """Analytic power of the two-sided two-proportion z-test (normal approximation)."""
    delta = abs(p2 - p1)
    pbar = (p1 + p2) / 2
    se0 = math.sqrt(2 * pbar * (1 - pbar) / n_per_arm)
    se1 = math.sqrt((p1 * (1 - p1) + p2 * (1 - p2)) / n_per_arm)
    z = stats.norm.ppf(1 - alpha / 2)
    return float(stats.norm.cdf((delta - z * se0) / se1) + stats.norm.cdf((-delta - z * se0) / se1))


def sample_size_two_proportions(
    p_base: float, mde_abs: float, alpha: float = 0.05, power: float = 0.8
) -> int:
    """Users needed per arm to detect an absolute lift of `mde_abs` over `p_base`."""
    p1, p2 = p_base, p_base + mde_abs
    if not (0 < p1 < 1 and 0 < p2 < 1):
        raise ValueError("baseline and baseline + mde must both lie in (0, 1)")
    pbar = (p1 + p2) / 2
    z_a = stats.norm.ppf(1 - alpha / 2)
    z_b = stats.norm.ppf(power)
    numerator = (
        z_a * math.sqrt(2 * pbar * (1 - pbar)) + z_b * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))
    ) ** 2
    return int(math.ceil(numerator / mde_abs**2))


def mde_two_proportions(
    p_base: float, n_per_arm: int, alpha: float = 0.05, power: float = 0.8
) -> float:
    """Smallest absolute lift detectable with the given power at this sample size."""
    upper = 1 - p_base - 1e-6
    if upper <= 1e-6:
        raise ValueError("baseline too close to 1 to compute an MDE")

    def gap(delta: float) -> float:
        return power_two_proportions(p_base, p_base + delta, n_per_arm, alpha) - power

    return float(brentq(gap, 1e-6, upper))
