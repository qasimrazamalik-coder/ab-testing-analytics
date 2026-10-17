# Metric definitions

One definition per metric, used by the SQL models, the Python analysis and the report. If a number
disagrees with this page, the number is wrong.

| Metric | Role | Definition | Grain | Source column |
|---|---|---|---|---|
| `retention_7` | **Primary** | Share of users who opened the game exactly 7 days after install | user | `retention_7` |
| `retention_1` | Secondary | Share of users who opened the game the day after install | user | `retention_1` |
| `sum_gamerounds` (mean) | **Guardrail** | Mean rounds played in the first 14 days after install | user | `sum_gamerounds` |
| Sample ratio | Validity check | Users per arm vs the designed 50/50 split | arm | `version` |

## Why these roles

- **Day-7 retention is the primary metric.** The change under test (moving the first gate from level 30
  to level 40) is a bet on long-run habit, not first-day curiosity. Day-1 is too easy to move without
  moving the business outcome.
- **Day-1 retention is secondary**, reported with the same correction for multiple testing as the primary
  (Holm, see ADR-002) so that having two metrics does not inflate the false-positive rate.
- **Mean game rounds is a guardrail, not a goal.** A change that lifts retention by making the game
  shorter is not a win. The guardrail is a non-inferiority test: the lower bound of the 95% interval on
  the relative change in mean rounds must stay above -5%. Rounds are heavy-tailed, so the interval is a
  bootstrap (ADR-003).

## Conventions

- Arms: `control` = `gate_30`, `treatment` = `gate_40`. The control label is configurable in one place
  (`control_variant` in `dbt_project/dbt_project.yml`, `DEFAULTS` in `pipeline.py`).
- Differences are treatment minus control, in percentage points for proportions and relative percent
  for the guardrail.
- Significance level 0.05 for metrics (after Holm), 0.001 for the sample-ratio check.
- Every reported result carries a provenance flag, `synthetic` or `real`. The report and memo print it
  at the top. See `data_contract.md`.
