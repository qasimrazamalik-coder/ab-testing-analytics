## What changed and why

<!-- One paragraph. The decision or metric this affects, not the diff. -->

## Metric or decision-rule impact

- [ ] No change to metric definitions (docs/metrics.md) or the decision rule (ADR-002)
- [ ] Changes a definition or the rule: docs and ADR updated in this PR

## Evidence

- [ ] `make verify` passes locally
- [ ] New logic has a test that fails without the change
- [ ] If SQL changed: `make dbt-build` passes and the parity test is updated
- [ ] If numbers in the README moved: `make run readme` re-run and committed

## Data

- [ ] Provenance flag on any new result is correct (`synthetic` or `real`)
