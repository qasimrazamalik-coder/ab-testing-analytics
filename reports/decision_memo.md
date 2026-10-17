# Experiment decision memo: gate_30 vs gate_40

> **Synthetic data.** This memo was generated from a seeded synthetic dataset to demonstrate the
> pipeline. The numbers below are not real product results.

**Decision: DO_NOT_SHIP.** The treatment significantly lowers the primary metric.

Keep the control experience. The treatment measurably hurts the primary metric.

## Data health

- 90,189 users: 45,006 in gate_30, 45,183 in gate_40.
- Sample ratio check passed (chi-square 0.35, p = 0.556, fails below 0.001).
- Source file `cookie_cats.csv`, SHA-256 starts `dc5401c3c0a5`.

## Primary metric: Day-7 retention

| Metric | gate_30 | gate_40 | Difference | 95% interval | p | p (Holm) |
|---|---|---|---|---|---|---|
| Day-7 retention (primary) | 19.02% | 18.09% | -0.93 pp | -1.44 pp to -0.42 pp | 3.2e-04 | 6.5e-04 |
| Day-1 retention | 44.96% | 44.39% | -0.57 pp | -1.22 pp to +0.08 pp | 0.086 | 0.086 |

Effect on day-7 retention: -0.93 pp (95% interval -1.44 pp to -0.42 pp), Holm-adjusted p = 6.5e-04.
Scaled to 100,000 users that is -931 users (interval -1,438 to -424).

## Guardrail: average engagement

Mean game rounds: 52.08 (gate_30) vs 51.68 (gate_40),
a relative change of -0.76% (bootstrap 95% interval -5.25% to +4.39%).
The guardrail is NOT cleared: it passes only if the whole interval stays above the -5% tolerance.

## Sensitivity

With 45,006 users per arm, this test could reliably detect (80% power) an absolute change of
about 0.74 pp in the primary metric. Smaller real effects would usually go undetected.

## What this analysis does not cover

- It treats each user once and has no time dimension, so novelty effects cannot be assessed.
- Retention flags are binary snapshots at day 1 and day 7; longer-term retention is unknown.
- Statistical significance is not business significance; weigh the effect size against rollout cost.

Method: two-proportion z-test, Holm correction across the two retention metrics (alpha 0.05),
percentile bootstrap (5000 resamples, seed 7) for the engagement guardrail.
Full rules: `docs/adr/002-decision-rule.md`.
