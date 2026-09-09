# Reversal and Bottom-Formation Methodology

Momentum asks whether price is continuing. Reversal asks whether prior selling is
exhausted and a new base is being confirmed. A large drawdown or one oversold
oscillator is not a bottom call.

## Independent evidence groups

1. **Location:** trailing drawdown, range percentile, distance from the 200-day
   average, and distance from the trailing low.
2. **Oversold pressure:** RSI(14), stochastic %K(14), and 20-day Bollinger z-score.
3. **Seller exhaustion:** current/20-day volume, up-day/down-day volume ratio, and
   downside-volume deceleration. High volume on a decline is not independently
   bullish; this repository previously found that claim non-discriminating.
4. **Base structure:** a retest low above the prior comparison-window low, falling
   downside slope, and no fresh closing low.
5. **Confirmation:** close above the 20-day average, RSI above 50, positive 20-day
   return, and improving breadth among major holdings.
6. **Fundamental confirmation:** for cyclicals, realised commodity price, operating
   earnings, cost-curve position, and announced supply growth.

## Five stages

| Stage | Meaning | Minimum interpretation |
|---|---|---|
| `falling` | New lows or broad deterioration continue | No bottom evidence |
| `oversold_candidate` | Location/oscillators are stretched | Candidate, not reversal |
| `base_forming` | Selling slows and a higher low appears | Bottom attempt |
| `reversal_confirmed` | Trend and breadth confirm the base | Confirmed reversal |
| `uptrend` | Medium-term trend and participation are positive | Reversal phase completed |

No stage may be assigned from a single group. `base_forming` requires evidence from
at least three groups, including base structure. `reversal_confirmed` additionally
requires confirmation. Coverage below 60% suspends the stage.

## Reference formulas

```text
drawdown_252       = close / max(high, 252 sessions) - 1
range_percentile   = (close - min(low, N)) / (max(high, N) - min(low, N))
bollinger_z_20     = (close - mean(close, 20)) / population_std(close, 20)
volume_ratio_20    = current_volume / mean(volume, 20)
up_down_volume_20  = mean(volume on up days) / mean(volume on down days)
higher_low_10_20   = min(low, recent 10) > min(low, preceding 20)
breadth_20_60      = covered weight with MA20 > MA60 / covered weight
```

RSI must declare its smoothing convention. Stochastic must declare whether it is raw
%K or smoothed. Comparison windows cannot be changed after viewing the outcome.

## ETF and cyclical-sector rules

Assess the ETF chart, theme layer, and constituents separately. Holdings breadth is
weight-aware and reports covered weight. Diversified miners are not counted as pure
lithium exposure merely because their company owns lithium assets. For commodity
producers, low P/E can mark peak earnings; prefer P/B, EV/EBITDA, cost position, and
through-cycle cash generation.

The final statement must distinguish a long-cycle low from a short-term pullback low,
state what remains unconfirmed, and avoid price targets or buy/sell language.
