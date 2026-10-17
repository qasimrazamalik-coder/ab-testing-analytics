"""Command line entry point: python -m abtest.cli {generate,analyze,sync-readme}."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .data import DataContractError, generate_cookie_cats_like
from .pipeline import analyze_file, write_results


def _generate(args: argparse.Namespace) -> int:
    share = 0.55 if args.srm_break else 0.5
    df = generate_cookie_cats_like(n_users=args.n_users, seed=args.seed, treatment_share=share)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"wrote {len(df):,} synthetic rows to {out} (seed={args.seed}, srm_break={args.srm_break})")
    return 0


def _analyze(args: argparse.Namespace) -> int:
    from .report import render_all  # imported lazily: needs matplotlib

    try:
        results, df = analyze_file(args.input, args.provenance)
    except DataContractError as exc:
        print(f"DATA CONTRACT VIOLATION: {exc}", file=sys.stderr)
        return 2
    out_dir = Path(args.out_dir)
    write_results(results, out_dir / "results.json")
    render_all(results, df, out_dir, Path(args.img_dir))
    print(f"verdict: {results['verdict']['decision']} - {results['verdict']['reason']}")
    print(f"wrote results.json, ab_report.html, decision_memo.md to {out_dir}")
    return 0


def _sync_readme(args: argparse.Namespace) -> int:
    from .readme_sync import sync

    return sync(Path(args.readme), Path(args.results), check=args.check)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="abtest")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="write a seeded synthetic Cookie-Cats-schema CSV")
    gen.add_argument("--out", default="data/raw/cookie_cats.csv")
    gen.add_argument("--seed", type=int, default=42)
    gen.add_argument("--n-users", type=int, default=90_189)
    gen.add_argument("--srm-break", action="store_true", help="55/45 split to trigger the SRM guard")
    gen.set_defaults(func=_generate)

    ana = sub.add_parser("analyze", help="validate, analyse, decide, render report + memo")
    ana.add_argument("--input", default="data/raw/cookie_cats.csv")
    ana.add_argument("--provenance", choices=["synthetic", "real"], required=True)
    ana.add_argument("--out-dir", default="reports")
    ana.add_argument("--img-dir", default="docs/img")
    ana.set_defaults(func=_analyze)

    syn = sub.add_parser("sync-readme", help="regenerate (or --check) the README results block")
    syn.add_argument("--readme", default="README.md")
    syn.add_argument("--results", default="reports/results.json")
    syn.add_argument("--check", action="store_true")
    syn.set_defaults(func=_sync_readme)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
