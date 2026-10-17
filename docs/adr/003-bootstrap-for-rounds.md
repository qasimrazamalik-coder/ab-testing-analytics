# ADR-003: Percentile bootstrap for the engagement guardrail

Status: accepted

## Context

`sum_gamerounds` is heavy-tailed: the median player plays about 16 rounds, the mean is about 52, and a
few players play hundreds. A t-test on the mean leans on the central limit theorem and on a variance
estimate that a handful of extreme users can dominate. The guardrail question is about the *relative*
change in the mean, which is a ratio of two sample means and has no tidy closed-form interval.

## Options

1. Welch t-test on the difference in means. Familiar, but gives an interval on the absolute scale and
   is sensitive to the tail.
2. Delta-method interval for the ratio. Closed form, but still rests on normality of the means.
3. **Percentile bootstrap on the relative change.** Resample users within each arm, compute
   `mean(treatment) / mean(control) - 1` each time, take the 2.5th and 97.5th percentiles.

## Decision

Option 3, 5,000 resamples, fixed seed (7) so the same input always yields the same interval.

## Consequences

- The interval is on the scale the guardrail is stated in (relative percent), with no distributional
  assumption on rounds.
- Cost is about 2.5 seconds on 90k rows. Acceptable here; at much larger scale, switch to the delta
  method or a Poisson bootstrap computed in the warehouse.
- The seed makes results deterministic but the interval still carries Monte Carlo error. Measured on
  the bundled data across 8 seeds: the lower bound moves by about 0.07 percentage points (one standard
  deviation) at 5,000 resamples, and by about 0.17 at 1,000. 1,000 was the first default; it was raised
  because a lower bound within 0.05 points of the -5% tolerance made the guardrail verdict depend on the
  seed. Do not over-read the second decimal, and raise `n_boot` when a bound sits this close to the line.
- This interval has a different character from the proportion tests, which use closed forms. That is
  intentional and noted in the report's method footer.
