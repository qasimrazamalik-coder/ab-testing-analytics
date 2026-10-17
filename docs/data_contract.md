# Data contract: `cookie_cats.csv`

The analysis refuses to run on a file that breaks this contract (`DataContractError`, CLI exit code 2).
The same rules are mirrored as dbt tests so the warehouse enforces them too.

## Schema

| Column | Type | Rule |
|---|---|---|
| `userid` | integer | Not null. Unique: one row per user. |
| `version` | string | Exactly two distinct values: `gate_30` (control) and `gate_40` (treatment). |
| `sum_gamerounds` | integer | Not null. Integer-valued. >= 0. |
| `retention_1` | boolean | Not null. `True`/`False` (also accepts `1`/`0`). |
| `retention_7` | boolean | Not null. `True`/`False` (also accepts `1`/`0`). |

Extra columns are dropped. A missing column, an empty file, a third arm or a single arm all fail.

## Where each rule is enforced

| Rule | Python (`abtest.data`) | dbt |
|---|---|---|
| unique, not null `userid` | `load_and_validate` | `unique` + `not_null` on source and models |
| exactly two arms | `load_and_validate` | `assert_two_arms_present` |
| rounds >= 0 | `load_and_validate` | `assert_no_negative_rounds` |
| arm accepted values | `load_and_validate` | `accepted_values` on `variant`, `arm` |
| 50/50 design holds | `srm_check` (chi-square, alpha 0.001) | `assert_arm_balance_coarse` (45-55% band) |

The dbt balance test is deliberately coarse: it catches gross assignment failures in the warehouse. The
statistically exact check lives in Python, where the chi-square test is available.

## Provenance

The file itself carries no provenance, so the caller declares it: `--provenance synthetic|real` is a
required flag. The value is written into `reports/results.json`, printed on the report and the memo, and
stored with the SHA-256 of the input file so a result can be tied to the exact bytes that produced it.

The bundled generator (`abtest.cli generate`) writes **synthetic** data that mimics the public Cookie Cats
schema. Replace `data/raw/cookie_cats.csv` with the real file and run with `--provenance real` to
analyse real data; nothing else changes.
