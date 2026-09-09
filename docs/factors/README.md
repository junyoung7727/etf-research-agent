# Factor Model Registry

This directory is the documentation-only registry for inputs and deterministic
features that may support ETF research. It does not change the seven indicators
implemented by `tools/score.py`.

## Files

- `available-factor-registry-v0.1.yaml`: canonical factor inventory.
- `provider-coverage.md`: provider capabilities and known gaps.
- `reversal-methodology.md`: multi-group bottom-assessment method.
- `../../examples/factors/lit-reversal-analysis.yaml`: dated worked example.

## Three distinct states

`available` means that a source can return the required fields. `computable`
means that a deterministic formula can be evaluated. `validated` means that the
feature has survived an explicit historical baseline test. These terms are not
interchangeable. Only validated factors may alter production scores.

Every observation must retain `as_of_date`, source, market scope, adjustment
policy, freshness, and missing-data status. Missing values stay null and reduce
coverage; they are never replaced with a neutral score.

The governing methodology remains [METHODOLOGY.md](../METHODOLOGY.md). Any future
runtime integration must satisfy [CONTRIBUTING.md](../../CONTRIBUTING.md), including
the repository's per-pattern validation requirement.
