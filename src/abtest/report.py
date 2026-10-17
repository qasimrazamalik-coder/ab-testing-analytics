"""Render charts, the single-file HTML report and the decision memo from a results dict.

Every number shown to a reader is formatted from `results` - nothing is typed by hand.
Chart colours are the validated categorical slots 1 (blue, control) and 2 (orange, treatment).
"""

from __future__ import annotations

import base64
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape  # noqa: E402

SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
C_CONTROL, C_TREAT = "#2a78d6", "#eb6834"
TEMPLATES = Path(__file__).parent / "templates"

METRIC_LABELS = {"retention_1": "Day-1 retention", "retention_7": "Day-7 retention"}

RECOMMENDATION = {
    "SHIP": "Roll out the treatment. Keep monitoring day-7 retention after launch.",
    "DO_NOT_SHIP": "Keep the control experience. The treatment measurably hurts the primary metric.",
    "HOLD": "Do not roll out yet. Investigate the engagement guardrail before deciding.",
    "INCONCLUSIVE": "No decision from this data. Either keep the control or extend the test; "
    "the minimum detectable effect below says what a longer test could resolve.",
    "INVALID": "Discard this analysis. Fix experiment assignment, then re-run the test.",
}


def fmt_pct(x: float, digits: int = 2) -> str:
    return f"{x * 100:.{digits}f}%"


def fmt_pp(x: float, digits: int = 2) -> str:
    return f"{x * 100:+.{digits}f} pp"


def fmt_p(p: float) -> str:
    return f"{p:.1e}" if p < 0.001 else f"{p:.3f}"


def _style(ax: plt.Axes) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=9, length=0)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def _title(ax: plt.Axes, title: str, subtitle: str) -> None:
    ax.set_title(title, loc="left", color=INK, fontsize=11, fontweight="bold", pad=22)
    ax.text(0, 1.03, subtitle, transform=ax.transAxes, color=INK2, fontsize=8.5, va="bottom")


def _new_fig(width: float, height: float, ncols: int = 1):
    fig, axes = plt.subplots(1, ncols, figsize=(width, height), dpi=160)
    fig.patch.set_facecolor(SURFACE)
    for ax in np.atleast_1d(axes):
        _style(ax)
    return fig, axes


def _arm_names(results: dict) -> tuple[str, str]:
    d = results["data"]
    return d["control_label"], d["treatment_label"]


def chart_retention(results: dict, path: Path) -> None:
    n_c, n_t = results["data"]["n_control"], results["data"]["n_treatment"]
    ctrl, treat = _arm_names(results)
    fig, ax = _new_fig(7.2, 4.3)
    x = np.arange(2)
    width = 0.30
    for offset, arm, color, n, key in (
        (-0.16, ctrl, C_CONTROL, n_c, "p_control"),
        (0.16, treat, C_TREAT, n_t, "p_treatment"),
    ):
        rates = np.array([results["metrics"][m][key] for m in METRIC_LABELS])
        errs = 1.96 * np.sqrt(rates * (1 - rates) / n)
        ax.bar(x + offset, rates, width, color=color, label=f"{arm} (n={n:,})", zorder=3)
        ax.errorbar(x + offset, rates, yerr=errs, fmt="none", ecolor=INK2, elinewidth=1.2,
                    capsize=3, zorder=4)
        for xi, r, e in zip(x + offset, rates, errs, strict=True):
            ax.text(xi, r + e + 0.012, fmt_pct(r), ha="center", color=INK, fontsize=9)
    ax.set_xticks(x, list(METRIC_LABELS.values()))
    ax.set_ylim(0, 0.56)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    ax.legend(frameon=False, loc="upper right", fontsize=9, labelcolor=INK2)
    _title(ax, "Retention by variant", "Share of users who came back. Whiskers: 95% interval per arm.")
    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)


def chart_effects(results: dict, path: Path) -> None:
    fig, axes = _new_fig(9.0, 3.0, ncols=3)
    panels = [
        ("Day-7 retention (primary)", results["metrics"]["retention_7"], 100, "pp", None),
        ("Day-1 retention", results["metrics"]["retention_1"], 100, "pp", None),
    ]
    g = results["guardrail"]
    specs = [
        (p[0], p[1]["diff"], p[1]["ci_low"], p[1]["ci_high"], "pp", None) for p in panels
    ] + [("Mean game rounds (guardrail)", g["rel_change"], g["ci_low"], g["ci_high"], "%",
          g["tolerance"])]
    for ax, (title, est, lo, hi, unit, tol) in zip(axes, specs, strict=True):
        ax.yaxis.grid(False)
        ax.xaxis.grid(True, color=GRID, linewidth=0.8)
        ax.axvline(0, color=INK2, linewidth=1.0, linestyle=(0, (4, 3)), zorder=2)
        ax.plot([lo * 100, hi * 100], [0, 0], color=INK, linewidth=2, zorder=3, solid_capstyle="round")
        ax.plot([est * 100], [0], marker="o", markersize=9, color=INK, markeredgecolor=SURFACE,
                markeredgewidth=2, zorder=4)
        if tol is not None:
            ax.axvline(tol * 100, color=C_TREAT, linewidth=1.5, zorder=2)
            ax.text(tol * 100, 0.32, "tolerance", color=INK2, fontsize=8, ha="center")
        span = max(abs(lo), abs(hi), abs(tol or 0)) * 100 * 1.35
        ax.set_xlim(-span, span)
        ax.set_ylim(-0.5, 0.5)
        ax.set_yticks([])
        ax.set_xlabel(f"effect ({unit})", color=INK2, fontsize=8.5)
        ax.text(est * 100, -0.3, f"{est * 100:+.2f}", ha="center", color=INK, fontsize=9,
                bbox={"facecolor": SURFACE, "edgecolor": "none", "pad": 1.5}, zorder=5)
        ax.set_title(title, loc="left", color=INK, fontsize=9.5, fontweight="bold")
    fig.suptitle("Effect of treatment vs control (point estimate and 95% interval)",
                 x=0.01, y=0.98, ha="left", color=INK, fontsize=11, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.94), h_pad=0.5)
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)


def chart_rounds(results: dict, df: pd.DataFrame, path: Path) -> None:
    ctrl, treat = _arm_names(results)
    fig, ax = _new_fig(7.2, 4.0)
    max_rounds = int(df["sum_gamerounds"].max())
    grid = np.unique(np.round(np.logspace(0, np.log10(max(max_rounds, 10)), 300)).astype(int))
    for arm, color, label in (("control", C_CONTROL, ctrl), ("treatment", C_TREAT, treat)):
        rounds = np.sort(df.loc[df["arm"] == arm, "sum_gamerounds"].to_numpy())
        share_at_least = 1 - np.searchsorted(rounds, grid, side="left") / len(rounds)
        ax.plot(grid, share_at_least, color=color, linewidth=2,
                label=f"{label} (median {int(np.median(rounds))} rounds)")
    ax.set_xscale("log")
    ax.set_xlim(1, max(max_rounds, 10))
    ax.set_ylim(0, 1.0)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:,.0f}")
    ax.set_xlabel("N rounds (log scale)", color=INK2, fontsize=9)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    ax.legend(frameon=False, loc="upper right", fontsize=9, labelcolor=INK2)
    _title(ax, "Engagement is heavy-tailed", "Share of users who played at least N rounds")
    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)


def chart_srm(results: dict, path: Path) -> None:
    ctrl, treat = _arm_names(results)
    srm = results["srm"]
    total = srm["n_control"] + srm["n_treatment"]
    expected = total * srm["expected_control_share"]
    fig, ax = _new_fig(7.2, 3.6)
    for xi, (arm, color, n) in enumerate(
        ((ctrl, C_CONTROL, srm["n_control"]), (treat, C_TREAT, srm["n_treatment"]))
    ):
        ax.bar(xi, n, 0.38, color=color, label=f"{arm}", zorder=3)
        ax.text(xi, n + total * 0.01, f"{n:,}", ha="center", color=INK, fontsize=9.5)
    ax.axhline(expected, color=INK2, linewidth=1.2, linestyle=(0, (4, 3)), zorder=4)
    ax.text(1.45, expected + total * 0.012, f"expected {expected:,.0f}", color=INK2, fontsize=8.5,
            va="bottom", ha="center")
    ax.set_xticks([0, 1], [ctrl, treat])
    ax.set_xlim(-0.6, 1.9)
    ax.set_ylim(0, total * 0.62)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:,.0f}")
    ax.legend(frameon=False, loc="upper left", fontsize=9, labelcolor=INK2)
    status = "PASS" if srm["passed"] else "FAIL"
    _title(ax, f"Sample ratio check: {status}",
           f"chi-square {srm['chi2']:.2f}, p = {fmt_p(srm['p_value'])} (fails below {srm['alpha']})")
    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)


def _data_uri(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def build_context(results: dict) -> dict:
    data, srm, g, power = results["data"], results["srm"], results["guardrail"], results["power"]
    prim_name = results["primary_metric"]
    prim = results["metrics"][prim_name]
    per_100k = lambda v: f"{v * 100_000:+,.0f}"  # noqa: E731
    rows = []
    for name, m in results["metrics"].items():
        rows.append({
            "name": METRIC_LABELS[name] + (" (primary)" if name == prim_name else ""),
            "control": fmt_pct(m["p_control"]),
            "treatment": fmt_pct(m["p_treatment"]),
            "diff": fmt_pp(m["diff"]),
            "ci": f"{fmt_pp(m['ci_low'])} to {fmt_pp(m['ci_high'])}",
            "p_raw": fmt_p(m["p_value"]),
            "p_adj": fmt_p(m["p_adjusted"]),
        })
    verdict = results["verdict"]
    return {
        "provenance": data["provenance"],
        "decision": verdict["decision"],
        "reason": verdict["reason"],
        "recommendation": RECOMMENDATION[verdict["decision"]],
        "control_label": data["control_label"],
        "treatment_label": data["treatment_label"],
        "n_users": f"{data['n_users']:,}",
        "n_control": f"{data['n_control']:,}",
        "n_treatment": f"{data['n_treatment']:,}",
        "sha_short": data["sha256"][:12],
        "source": data["source"],
        "srm_status": "passed" if srm["passed"] else "FAILED",
        "srm_p": fmt_p(srm["p_value"]),
        "srm_chi2": f"{srm['chi2']:.2f}",
        "srm_alpha": str(srm["alpha"]),
        "rows": rows,
        "primary_label": METRIC_LABELS[prim_name],
        "primary_diff": fmt_pp(prim["diff"]),
        "primary_ci": f"{fmt_pp(prim['ci_low'])} to {fmt_pp(prim['ci_high'])}",
        "primary_p_adj": fmt_p(prim["p_adjusted"]),
        "impact_per_100k": per_100k(prim["diff"]),
        "impact_ci_per_100k": f"{per_100k(prim['ci_low'])} to {per_100k(prim['ci_high'])}",
        "guard_change": f"{g['rel_change'] * 100:+.2f}%",
        "guard_ci": f"{g['ci_low'] * 100:+.2f}% to {g['ci_high'] * 100:+.2f}%",
        "guard_tol": f"{g['tolerance'] * 100:.0f}%",
        "guard_status": "cleared" if g["passed"] else "NOT cleared",
        "guard_control_mean": f"{g['control_mean']:.2f}",
        "guard_treatment_mean": f"{g['treatment_mean']:.2f}",
        "mde": fmt_pp(power["mde_abs_80pct_power"]).replace("+", ""),
        "n_per_arm": f"{power['n_per_arm']:,}",
        "alpha": str(results["config"]["alpha"]),
        "n_boot": str(results["config"]["n_boot"]),
        "seed": str(results["config"]["seed"]),
    }


def render_all(results: dict, df: pd.DataFrame, out_dir: Path, img_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    img_dir.mkdir(parents=True, exist_ok=True)
    charts = {
        "retention": img_dir / "retention.png",
        "effects": img_dir / "effects.png",
        "rounds": img_dir / "rounds.png",
        "srm": img_dir / "srm.png",
    }
    chart_retention(results, charts["retention"])
    chart_effects(results, charts["effects"])
    chart_rounds(results, df, charts["rounds"])
    chart_srm(results, charts["srm"])

    env = Environment(loader=FileSystemLoader(TEMPLATES), undefined=StrictUndefined,
                      autoescape=select_autoescape(["html"]), keep_trailing_newline=True)
    ctx = build_context(results)
    html = env.get_template("report.html.j2").render(
        **ctx, images={k: _data_uri(p) for k, p in charts.items()})
    (out_dir / "ab_report.html").write_text(html)
    (out_dir / "decision_memo.md").write_text(env.get_template("memo.md.j2").render(**ctx))

