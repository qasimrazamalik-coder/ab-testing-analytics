# ADR-002: Decision rule and multiple-testing correction

Status: accepted

## Context

The experiment reports two retention metrics and one guardrail. Looking at several metrics and
shipping when any of them is significant inflates the false-positive rate. Teams also tend to decide
after seeing the numbers. The rule has to be fixed in advance, in code, and produce one of a small
number of actions.

## Decision

Evaluate in this order and stop at the first match:

| Step | Condition | Verdict |
|---|---|---|
| 1 | SRM check fails (ADR-001) | `INVALID` |
| 2 | Primary metric, Holm-adjusted p >= 0.05 | `INCONCLUSIVE` |
| 3 | Primary metric difference < 0 (significant loss) | `DO_NOT_SHIP` |
| 4 | Guardrail not cleared | `HOLD` |
| 5 | otherwise | `SHIP` |

- **Holm-Bonferroni** across the two retention metrics. It controls the family-wise error rate like
  Bonferroni but is uniformly more powerful. Day-7 retention is the primary metric; day-1 is reported
  with the same correction but cannot trigger a ship on its own.
- **The guardrail is a non-inferiority test**, not a significance test: it passes when the lower bound
  of the 95% interval on the relative change in mean rounds is at least -5%. An interval that is too
  wide to rule out a worse drop than that is a fail, which is the conservative reading.
- The order puts validity before evidence, evidence before harm, and harm before upside.

## Consequences

- Every verdict is reproducible from `results.json` and covered by unit tests, including the boundary
  `p == alpha` (inconclusive) and the case where a loss and a failed guardrail occur together
  (`DO_NOT_SHIP` wins).
- Pre-registering the rule means a disappointing result cannot be reframed by switching metric.
- The rule is not sequential: it assumes one look at a fixed sample size. Peeking would need a different
  method (alpha spending or always-valid p-values) and a new ADR.
- Changing the order or any threshold is a decision-rule change and requires updating this ADR in the
  same pull request.
