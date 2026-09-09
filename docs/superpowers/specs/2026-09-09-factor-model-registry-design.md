# Factor Model Registry — Documentation-First Design

## Objective

Create a reviewable, provider-aware factor-model reference without changing the
current scoring code or its seven-indicator behaviour. The first increment must
capture both the existing methodology and the reversal analysis used for LIT,
while preserving the repository rule that a factor cannot enter scoring before
it is validated against a baseline.

## Scope

This increment adds documentation and declarative YAML only. It does not change
`tools/score.py`, `tools/validate.py`, agent prompts, scoring weights, colour
bands, or runtime dependencies.

The registry will distinguish three states:

- `observed`: a raw field returned by a named provider or primary source;
- `derived`: a deterministic calculation from observed fields;
- `validated`: a derived factor whose test evidence meets the repository's
  contribution standard.

An available input is not automatically a valid signal. Availability,
computability, and validation status remain separate fields.

## Proposed Layout

```text
docs/factors/
├── README.md
├── available-factor-registry-v0.1.yaml
├── provider-coverage.md
└── reversal-methodology.md
examples/factors/
└── lit-reversal-analysis.yaml
```

`available-factor-registry-v0.1.yaml` is the machine-readable inventory for this
increment. `README.md` explains its contract and points to the repository's
existing methodology. `provider-coverage.md` records what Kiwoom, FMP, issuer,
exchange, and filing sources can and cannot supply. `reversal-methodology.md`
defines the bottom-assessment process. The LIT example records one reproducible
application with an explicit as-of date and data gaps.

## Factor Taxonomy

The registry groups factors by economic role rather than by vendor:

1. macro and regime;
2. valuation and quality;
3. trend and momentum;
4. reversal and bottom formation;
5. flow and liquidity;
6. ETF structure and tracking quality;
7. theme, value chain, and holdings breadth;
8. volatility, drawdown, concentration, and other risk.

Each factor entry contains a stable ID, cluster, definition, direction, horizon,
inputs, formula when derived, provider coverage, freshness requirement, missing
data behaviour, validation state, and known limitations. Provider-specific names
are mappings beneath the factor, not separate economic factors.

## Reversal Method

A bottom is not inferred from one oversold indicator. The method separates:

1. **location** — drawdown, range percentile, and distance from long moving
   averages;
2. **oversold pressure** — RSI, stochastic position, and volatility-band
   distance;
3. **seller exhaustion** — volume participation and downside-pressure change;
4. **base structure** — higher low, successful retest, and decline deceleration;
5. **confirmation** — moving-average recovery and positive breadth across major
   holdings;
6. **fundamental confirmation** — commodity price, earnings, cost curve, and
   supply response where the ETF represents a cyclical industry.

The output is a five-stage state, not a price target:
`falling`, `oversold_candidate`, `base_forming`, `reversal_confirmed`, or
`uptrend`. Missing groups reduce coverage; they are never filled with a neutral
assumption. A bottom call requires evidence from at least three independent
groups, matching the current repository methodology.

## LIT Example Contract

The worked example records ETF-level and holdings-level measurements separately.
It identifies diversified miners such as Rio Tinto rather than treating the full
weight as pure lithium exposure. It also distinguishes a long-cycle low from a
short-term pullback low and reports unsupported holdings explicitly when Kiwoom's
US feed cannot cover their home exchanges.

The example is historical evidence, not live output. It must include the as-of
date, source, formula version, coverage, and limitations so later readers do not
mistake it for a current recommendation.

## Validation and Review

Documentation checks will verify that the YAML is syntactically loadable using a
temporary development check without adding a runtime dependency, that every
factor has the required metadata, and that the example references only registered
factor IDs. No factor will be wired into `tools/score.py` in this increment.

Later implementation requires a separate design and measured `tools/validate.py`
results before changing scoring behaviour.

## Acceptance Criteria

- All proposed documentation files exist and cross-link correctly.
- Kiwoom, FMP, primary-source, and derived coverage are distinguishable.
- Momentum and reversal are modeled as separate clusters.
- The LIT method is reproducible from named inputs and formulas.
- Missing data and stale data fail loudly.
- Existing scoring output and self-checks remain unchanged.
