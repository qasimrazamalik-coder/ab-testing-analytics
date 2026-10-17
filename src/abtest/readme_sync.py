"""Keep the README results block identical to reports/results.json (no hand-typed numbers)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .report import build_context

START, END = "<!-- RESULTS:START -->", "<!-- RESULTS:END -->"


def render_block(results: dict) -> str:
    ctx = build_context(results)
    lines = [
        START,
        f"**Data: {ctx['provenance'].upper()}** ({ctx['n_users']} users, source `{ctx['source']}`)",
        "",
        f"**Decision: {ctx['decision']}** - {ctx['reason']}",
        "",
        f"| Metric | {ctx['control_label']} | {ctx['treatment_label']} "
        "| Difference | 95% interval | p (Holm) |",
        "|---|---|---|---|---|---|",
    ]
    for r in ctx["rows"]:
        lines.append(
            f"| {r['name']} | {r['control']} | {r['treatment']} | {r['diff']} | {r['ci']} | {r['p_adj']} |"
        )
    lines += [
        "",
        f"Sample ratio check {ctx['srm_status']} (p = {ctx['srm_p']}). Engagement guardrail "
        f"{ctx['guard_status']}: mean game rounds {ctx['guard_change']} (95% interval {ctx['guard_ci']}).",
        END,
    ]
    return "\n".join(lines)


def sync(readme: Path, results_path: Path, check: bool = False) -> int:
    results = json.loads(results_path.read_text())
    text = readme.read_text()
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.DOTALL)
    if not pattern.search(text):
        print(f"{readme}: results markers not found")
        return 2
    updated = pattern.sub(lambda _m: render_block(results), text)
    if check:
        if updated != text:
            print("README results block is stale: run `make readme`")
            return 1
        print("README results block is in sync")
        return 0
    readme.write_text(updated)
    print("README results block updated")
    return 0
