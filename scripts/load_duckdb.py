"""Load the experiment CSV into DuckDB as raw.cookie_cats (the dbt source).

Usage: python scripts/load_duckdb.py [--csv data/raw/cookie_cats.csv] [--db warehouse/ab_testing.duckdb]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default="data/raw/cookie_cats.csv")
    parser.add_argument("--db", default="warehouse/ab_testing.duckdb")
    args = parser.parse_args()

    csv_path = Path(args.csv).resolve()
    if not csv_path.exists():
        raise SystemExit(f"{csv_path} not found. Run `make data` or place the real CSV there.")
    Path(args.db).parent.mkdir(parents=True, exist_ok=True)

    safe_path = str(csv_path).replace("'", "''")
    with duckdb.connect(args.db) as con:
        con.execute("create schema if not exists raw")
        con.execute(
            "create or replace table raw.cookie_cats as "
            f"select * from read_csv_auto('{safe_path}', header=true)"
        )
        rows = con.execute("select count(*) from raw.cookie_cats").fetchone()[0]
    print(f"loaded {rows:,} rows into raw.cookie_cats in {args.db}")


if __name__ == "__main__":
    main()
