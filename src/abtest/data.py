"""Data contract enforcement and a seeded synthetic generator.

The generator reproduces the *schema* of the public "Cookie Cats" mobile-game A/B test
(userid, version, sum_gamerounds, retention_1, retention_7) so the real file is a drop-in
replacement. Values it produces are synthetic and are never presented as real results.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import brentq
from scipy.special import expit

REQUIRED_COLUMNS = ("userid", "version", "sum_gamerounds", "retention_1", "retention_7")


class DataContractError(ValueError):
    """The input file violates docs/data_contract.md. Nothing downstream may run."""


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _to_bool(series: pd.Series, name: str) -> pd.Series:
    if series.dtype == bool:
        return series
    mapped = (
        series.astype(str)
        .str.strip()
        .str.lower()
        .map({"true": True, "false": False, "1": True, "0": False})
    )
    if mapped.isna().any():
        raise DataContractError(f"{name}: values must be boolean (True/False/1/0)")
    return mapped.astype(bool)


def load_and_validate(
    path: str | Path, control_label: str = "gate_30", treatment_label: str = "gate_40"
) -> pd.DataFrame:
    """Load the experiment file and enforce the data contract.

    Raises DataContractError on: missing columns, nulls, duplicate user ids, anything other
    than exactly the two expected arms, non-integer or negative round counts, non-boolean
    retention flags.
    """
    df = pd.read_csv(path)
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise DataContractError(f"missing required columns: {missing}")
    df = df.loc[:, list(REQUIRED_COLUMNS)].copy()

    if df.empty:
        raise DataContractError("file has no rows")
    if df.isna().any().any():
        raise DataContractError("null values are not allowed in any column")
    if df["userid"].duplicated().any():
        raise DataContractError("userid must be unique (one row per user)")

    arms = set(df["version"].astype(str).unique())
    if arms != {control_label, treatment_label}:
        raise DataContractError(
            f"version must contain exactly {{{control_label!r}, {treatment_label!r}}}, got {sorted(arms)}"
        )

    rounds = pd.to_numeric(df["sum_gamerounds"], errors="coerce")
    if rounds.isna().any() or (rounds % 1 != 0).any():
        raise DataContractError("sum_gamerounds must be integer-valued")
    if (rounds < 0).any():
        raise DataContractError("sum_gamerounds must be >= 0")
    df["sum_gamerounds"] = rounds.astype("int64")

    df["retention_1"] = _to_bool(df["retention_1"], "retention_1")
    df["retention_7"] = _to_bool(df["retention_7"], "retention_7")
    df["version"] = df["version"].astype(str)
    df["arm"] = np.where(df["version"] == control_label, "control", "treatment")
    return df


def _calibrate_intercept(x: np.ndarray, target: float, slope: float) -> float:
    return float(brentq(lambda a: expit(a + slope * x).mean() - target, -15.0, 15.0))


def generate_cookie_cats_like(
    n_users: int = 90_189,
    seed: int = 42,
    treatment_share: float = 0.5,
    effect_r1: float = -0.02,
    effect_r7: float = -0.05,
) -> pd.DataFrame:
    """Seeded synthetic data with the Cookie Cats schema.

    Engagement is heavy-tailed (floored lognormal). Retention is logistic in log engagement,
    with the treatment entering as a log-odds shift (`effect_r1`, `effect_r7`). Day-7 and day-1
    draws are coupled so most day-7 returners are also day-1 returners, as in real products.
    Passing `treatment_share != 0.5` while the analysis expects 50/50 produces a deliberate
    sample-ratio mismatch, used by the guardrail tests.
    """
    rng = np.random.default_rng(seed)
    user_ids = rng.choice(9_999_883, size=n_users, replace=False) + 116
    treated = rng.random(n_users) < treatment_share
    # floor(lognormal): median ~16, mean ~52, ~3.6% zero-round users, very long right tail
    rounds = np.floor(rng.lognormal(mean=np.log(16.0), sigma=1.536, size=n_users)).astype(np.int64)
    x = np.log1p(rounds)

    a1 = _calibrate_intercept(x[~treated], 0.448, 0.55)
    a7 = _calibrate_intercept(x[~treated], 0.190, 0.75)
    p1 = expit(a1 + 0.55 * x + effect_r1 * treated)
    p7 = expit(a7 + 0.75 * x + effect_r7 * treated)

    u = rng.random(n_users)
    u7 = np.where(rng.random(n_users) < 0.8, u, rng.random(n_users))
    return pd.DataFrame(
        {
            "userid": user_ids,
            "version": np.where(treated, "gate_40", "gate_30"),
            "sum_gamerounds": rounds,
            "retention_1": u < p1,
            "retention_7": u7 < p7,
        }
    )
