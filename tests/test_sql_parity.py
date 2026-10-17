"""SQL logic parity: run the dbt model and singular-test SQL on SQLite and compare to pandas.

What this proves: the SQL *logic* (casts, flags, arm assignment, aggregation, test predicates)
matches the Python analysis. What it does NOT prove: that dbt compiles the project or that
DuckDB accepts it. That is verified by `make dbt-build` on a machine with dbt-duckdb installed.
"""

import re
import sqlite3
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from abtest.data import generate_cookie_cats_like, load_and_validate

DBT = Path(__file__).resolve().parents[1] / "dbt_project"
MODELS = ["stg_cookie_cats", "fct_experiment_users", "fct_experiment_results"]


def render(sql: str) -> str:
    """Resolve the three Jinja constructs the project uses to plain SQL."""
    sql = re.sub(r"\{\{\s*source\(\s*'raw'\s*,\s*'cookie_cats'\s*\)\s*\}\}", "raw_cookie_cats", sql)
    sql = re.sub(r"\{\{\s*ref\(\s*'(\w+)'\s*\)\s*\}\}", r"\1", sql)
    var = r"\{\{\s*var\(\s*\"control_variant\"\s*,\s*\"gate_30\"\s*\)\s*\}\}"
    sql = re.sub(var, "gate_30", sql)
    if "{{" in sql or "{%" in sql:
        raise AssertionError(f"unrendered Jinja left in SQL:\n{sql}")
    return sql


def build(df: pd.DataFrame) -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    df[["userid", "version", "sum_gamerounds", "retention_1", "retention_7"]].to_sql(
        "raw_cookie_cats", con, index=False
    )
    for name in MODELS:
        layer = "staging" if name.startswith("stg") else "marts"
        sql = render((DBT / "models" / layer / f"{name}.sql").read_text())
        con.execute(f"create table {name} as {sql}")
    return con


def singular(con: sqlite3.Connection, name: str) -> int:
    sql = render((DBT / "tests" / f"{name}.sql").read_text())
    return len(con.execute(sql).fetchall())


def singular_on(df: pd.DataFrame, name: str) -> int:
    con = build(df)
    try:
        return singular(con, name)
    finally:
        con.close()


class SqlParity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(tempfile.mkdtemp()) / "d.csv"
        generate_cookie_cats_like(n_users=30000, seed=21).to_csv(path, index=False)
        cls.df = load_and_validate(path)
        cls.con = build(cls.df)

    @classmethod
    def tearDownClass(cls):
        cls.con.close()

    def test_grain_one_row_per_user(self):
        n, distinct = self.con.execute(
            "select count(*), count(distinct user_id) from fct_experiment_users"
        ).fetchone()
        self.assertEqual(n, len(self.df))
        self.assertEqual(n, distinct)

    def test_results_match_pandas(self):
        query = (
            "select arm, users, retained_d1_users, retained_d7_users, retention_d7, "
            "avg_game_rounds, zero_round_users from fct_experiment_results"
        )
        sql_rows = {r[0]: r for r in self.con.execute(query)}
        for arm, g in self.df.groupby("arm"):
            _, users, d1, d7, r7, avg_rounds, zeros = sql_rows[arm]
            self.assertEqual(users, len(g))
            self.assertEqual(d1, int(g["retention_1"].sum()))
            self.assertEqual(d7, int(g["retention_7"].sum()))
            self.assertAlmostEqual(r7, g["retention_7"].mean(), places=12)
            self.assertAlmostEqual(avg_rounds, g["sum_gamerounds"].mean(), places=9)
            self.assertEqual(zeros, int((g["sum_gamerounds"] == 0).sum()))

    def test_sql_counts_feed_the_same_test_as_python(self):
        from abtest import stats

        rows = {
            r[0]: r
            for r in self.con.execute("select arm, users, retained_d7_users from fct_experiment_results")
        }
        _, n_c, x_c = rows["control"]
        _, n_t, x_t = rows["treatment"]
        from_sql = stats.two_proportion_test(x_c, n_c, x_t, n_t)

        ctrl = self.df[self.df["arm"] == "control"]
        trt = self.df[self.df["arm"] == "treatment"]
        from_py = stats.two_proportion_test(
            int(ctrl["retention_7"].sum()), len(ctrl), int(trt["retention_7"].sum()), len(trt)
        )
        self.assertEqual(from_sql, from_py)

    def test_singular_tests_pass_on_good_data(self):
        for name in ("assert_two_arms_present", "assert_no_negative_rounds", "assert_arm_balance_coarse"):
            with self.subTest(name):
                self.assertEqual(singular(self.con, name), 0)

    def test_singular_tests_fire_on_bad_data(self):
        """A test that cannot fail checks nothing: feed each one data that must trip it."""
        one_arm = self.df.copy()
        one_arm["version"] = "gate_30"
        one_arm["arm"] = "control"
        self.assertEqual(singular_on(one_arm, "assert_two_arms_present"), 1)

        negative = self.df.copy()
        negative.loc[negative.index[:3], "sum_gamerounds"] = -5
        self.assertEqual(singular_on(negative, "assert_no_negative_rounds"), 3)

        skewed = generate_cookie_cats_like(n_users=10000, seed=22, treatment_share=0.30)
        skewed["arm"] = skewed["version"].map({"gate_30": "control", "gate_40": "treatment"})
        self.assertEqual(singular_on(skewed, "assert_arm_balance_coarse"), 1)


if __name__ == "__main__":
    unittest.main()
