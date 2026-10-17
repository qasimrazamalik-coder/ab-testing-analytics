"""Experiment analysis pipeline: validated data in, results dict (and decision) out."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from . import stats
from .data import load_and_validate, sha256_file

PRIMARY_METRIC = "retention_7"
SECONDARY_METRICS = ("retention_1",)
GUARDRAIL_COLUMN = "sum_gamerounds"

DEFAULTS = {
    "alpha": 0.05,
    "srm_alpha": 0.001,
    "expected_control_share": 0.5,
    "guardrail_tolerance": -0.05,  # max tolerated relative drop in mean game rounds
    "n_boot": 5000,
    "seed": 7,
    "control_label": "gate_30",
    "treatment_label": "gate_40",
}


def decide(srm_passed: bool, primary: dict, guardrail: dict, alpha: float) -> dict:
    """Decision rule documented in docs/adr/002-decision-rule.md. Order matters."""
    if not srm_passed:
        return {
            "decision": "INVALID",
            "reason": "Sample ratio mismatch: assignment is broken, so no result can be trusted.",
        }
    if primary["p_adjusted"] >= alpha:
        return {
            "decision": "INCONCLUSIVE",
            "reason": "The primary metric shows no statistically significant difference.",
        }
    if primary["diff"] < 0:
        return {
            "decision": "DO_NOT_SHIP",
            "reason": "The treatment significantly lowers the primary metric.",
        }
    if not guardrail["passed"]:
        return {
            "decision": "HOLD",
            "reason": "The primary metric improves but the engagement guardrail is not cleared.",
        }
    return {
        "decision": "SHIP",
        "reason": "The primary metric improves significantly and the guardrail holds.",
    }


def analyze(
    df: pd.DataFrame, provenance: str, data_sha256: str, source: str, **overrides
) -> dict:
    """Run the full analysis on a validated frame. Pure function: no I/O, no clock, no randomness
    beyond the seeded bootstrap, so identical input gives identical output."""
    if provenance not in {"synthetic", "real"}:
        raise ValueError("provenance must be 'synthetic' or 'real'")
    cfg = {**DEFAULTS, **overrides}
    control = df[df["arm"] == "control"]
    treatment = df[df["arm"] == "treatment"]

    srm = stats.srm_check(
        len(control), len(treatment), cfg["expected_control_share"], cfg["srm_alpha"]
    )

    raw = {}
    for metric in (PRIMARY_METRIC, *SECONDARY_METRICS):
        test = stats.two_proportion_test(
            int(control[metric].sum()),
            len(control),
            int(treatment[metric].sum()),
            len(treatment),
            cfg["alpha"],
        )
        raw[metric] = test.to_dict()
    adjusted = stats.holm_bonferroni({m: r["p_value"] for m, r in raw.items()})
    metrics = {m: {**r, "p_adjusted": adjusted[m]} for m, r in raw.items()}

    boot = stats.bootstrap_relative_change(
        control[GUARDRAIL_COLUMN].to_numpy(),
        treatment[GUARDRAIL_COLUMN].to_numpy(),
        n_boot=cfg["n_boot"],
        alpha=cfg["alpha"],
        seed=cfg["seed"],
    )
    guardrail = {
        "metric": "mean sum_gamerounds",
        **boot,
        "tolerance": cfg["guardrail_tolerance"],
        # non-inferiority: the whole CI must stay above the tolerated drop
        "passed": bool(boot["ci_low"] >= cfg["guardrail_tolerance"]),
    }

    per_arm = min(len(control), len(treatment))
    baseline = metrics[PRIMARY_METRIC]["p_control"]
    power = {
        "primary_metric": PRIMARY_METRIC,
        "baseline": baseline,
        "n_per_arm": per_arm,
        "mde_abs_80pct_power": stats.mde_two_proportions(baseline, per_arm, cfg["alpha"]),
    }

    return {
        "data": {
            "source": source,
            "provenance": provenance,
            "sha256": data_sha256,
            "n_users": int(len(df)),
            "n_control": int(len(control)),
            "n_treatment": int(len(treatment)),
            "control_label": cfg["control_label"],
            "treatment_label": cfg["treatment_label"],
        },
        "config": {k: cfg[k] for k in ("alpha", "srm_alpha", "guardrail_tolerance", "n_boot", "seed")},
        "srm": srm.to_dict(),
        "metrics": metrics,
        "primary_metric": PRIMARY_METRIC,
        "guardrail": guardrail,
        "power": power,
        "verdict": decide(srm.passed, metrics[PRIMARY_METRIC], guardrail, cfg["alpha"]),
    }


def analyze_file(path: str | Path, provenance: str, **overrides) -> tuple[dict, pd.DataFrame]:
    cfg = {**DEFAULTS, **overrides}
    df = load_and_validate(path, cfg["control_label"], cfg["treatment_label"])
    results = analyze(df, provenance, sha256_file(path), Path(path).name, **overrides)
    return results, df


def write_results(results: dict, out_path: str | Path) -> None:
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")
