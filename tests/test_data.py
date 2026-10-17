"""Data contract and generator tests."""

import hashlib
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from abtest.data import DataContractError, generate_cookie_cats_like, load_and_validate


def _write(df: pd.DataFrame) -> Path:
    path = Path(tempfile.mkdtemp()) / "x.csv"
    df.to_csv(path, index=False)
    return path


def _good(n: int = 200) -> pd.DataFrame:
    return generate_cookie_cats_like(n_users=n, seed=1)


class Generator(unittest.TestCase):
    def test_same_seed_same_bytes(self):
        a = _good(500).to_csv(index=False).encode()
        b = _good(500).to_csv(index=False).encode()
        self.assertEqual(hashlib.sha256(a).hexdigest(), hashlib.sha256(b).hexdigest())

    def test_different_seed_differs(self):
        a = generate_cookie_cats_like(n_users=500, seed=1)
        b = generate_cookie_cats_like(n_users=500, seed=2)
        self.assertFalse(a.equals(b))

    def test_schema_and_ranges(self):
        df = generate_cookie_cats_like(n_users=5000, seed=3)
        expected = ["userid", "version", "sum_gamerounds", "retention_1", "retention_7"]
        self.assertEqual(list(df.columns), expected)
        self.assertTrue(df["userid"].is_unique)
        self.assertTrue((df["sum_gamerounds"] >= 0).all())
        self.assertEqual(set(df["version"]), {"gate_30", "gate_40"})

    def test_calibrated_baselines(self):
        df = generate_cookie_cats_like(n_users=60000, seed=4)
        control = df[df["version"] == "gate_30"]
        self.assertAlmostEqual(control["retention_1"].mean(), 0.448, delta=0.01)
        self.assertAlmostEqual(control["retention_7"].mean(), 0.190, delta=0.01)

    def test_srm_break_changes_split(self):
        df = generate_cookie_cats_like(n_users=20000, seed=5, treatment_share=0.45)
        share_control = (df["version"] == "gate_30").mean()
        self.assertAlmostEqual(share_control, 0.55, delta=0.01)


class Contract(unittest.TestCase):
    def test_valid_file_loads_and_adds_arm(self):
        df = load_and_validate(_write(_good()))
        self.assertEqual(set(df["arm"]), {"control", "treatment"})

    def test_missing_column(self):
        with self.assertRaises(DataContractError):
            load_and_validate(_write(_good().drop(columns=["retention_7"])))

    def test_duplicate_userid(self):
        df = _good()
        df.loc[1, "userid"] = df.loc[0, "userid"]
        with self.assertRaises(DataContractError):
            load_and_validate(_write(df))

    def test_negative_rounds(self):
        df = _good()
        df.loc[0, "sum_gamerounds"] = -1
        with self.assertRaises(DataContractError):
            load_and_validate(_write(df))

    def test_fractional_rounds(self):
        df = _good().astype({"sum_gamerounds": float})
        df.loc[0, "sum_gamerounds"] = 2.5
        with self.assertRaises(DataContractError):
            load_and_validate(_write(df))

    def test_three_arms(self):
        df = _good()
        df.loc[0, "version"] = "gate_50"
        with self.assertRaises(DataContractError):
            load_and_validate(_write(df))

    def test_single_arm(self):
        df = _good()
        df["version"] = "gate_30"
        with self.assertRaises(DataContractError):
            load_and_validate(_write(df))

    def test_null_value(self):
        df = _good()
        df.loc[0, "sum_gamerounds"] = None
        with self.assertRaises(DataContractError):
            load_and_validate(_write(df))

    def test_non_boolean_retention(self):
        df = _good().astype({"retention_1": object})
        df.loc[0, "retention_1"] = "maybe"
        with self.assertRaises(DataContractError):
            load_and_validate(_write(df))

    def test_empty_file(self):
        with self.assertRaises(DataContractError):
            load_and_validate(_write(_good().iloc[0:0]))


if __name__ == "__main__":
    unittest.main()
