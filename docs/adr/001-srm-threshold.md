# ADR-001: Sample-ratio mismatch fires at p < 0.001

Status: accepted

## Context

A sample-ratio mismatch (SRM) means the arms are not the size the design promised. It signals broken
assignment, logging loss or a bot filter that treats arms differently, and when it happens no
downstream comparison can be trusted. We need a threshold for "the split is off".

## Options

1. **alpha = 0.05.** Fires on 1 in 20 healthy experiments. Each false alarm blocks a valid result and
   teaches people to override the check.
2. **alpha = 0.001.** Fires on 1 in 1,000 healthy experiments. Still catches real defects, which tend to
   be large (a few percent of traffic lost on one side, p far below 0.001).
3. **Tolerance band on the ratio** (for example 49-51%). Ignores sample size: too strict for small
   experiments, too lax for very large ones.

## Decision

Option 2. A chi-square goodness-of-fit test against the designed split, `alpha = 0.001`, a hard stop:
a failed SRM turns the verdict into `INVALID` before any metric is looked at (ADR-002).

## Consequences

- A split of 5,100 / 4,900 (p about 0.046) passes; 5,200 / 4,800 (p about 6e-5) fails. Both cases are
  pinned in `tests/test_stats.py`.
- Mild imbalance can slip through. That is accepted: SRM is a health check on assignment, not a
  precision instrument, and the coarse dbt band (45-55%) backstops gross failures in the warehouse.
- Revisit the threshold if the organisation runs so many experiments a day that 1-in-1,000 false
  alarms become a routine cost.
