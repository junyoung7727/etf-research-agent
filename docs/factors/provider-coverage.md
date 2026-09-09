# Provider Coverage for the Factor Registry

Coverage describes obtainable data, not signal validity. Issuer, exchange, and
regulatory sources remain primary and override vendor data when scopes match.

| Dataset | Kiwoom OpenAPI | FMP | Primary-source fallback | Main factor uses |
|---|---|---|---|---|
| US/KR OHLCV | Yes | Yes | Exchange | returns, trend, reversal, volatility |
| Intraday bars/trades/order book | Yes | Limited | Exchange | intraday reversal, liquidity |
| KR investor-type net flow | Yes | No | KRX | retail/foreign/institution flow |
| KR short, credit, lending, program flow | Yes | No | KRX | crowding and forced-selling risk |
| Company statements and TTM ratios | Limited quote fields | Yes | Filings | value, quality, leverage |
| US ETF holdings and weights | Limited | Yes | Issuer | concentration, breadth, purity |
| Korean ETF holdings | No reliable structured feed | Empty/unsupported | Issuer | breadth, value-chain exposure |
| ETF AUM, fee, inception | Limited | Yes | Issuer | product structure |
| Treasury curve | Limited by market endpoint | Yes | Treasury/FRED | macro and discount-rate regime |
| FX and Korean market indicators | Yes | Limited | BOK/KRX | currency and domestic regime |
| Commodity spot/contract curve | No complete lithium series | No complete lithium series | Exchange/producer filings | miner-cycle confirmation |
| ETF creations/redemptions | Not established | Not established | Issuer/exchange | true fund-flow confirmation |

## Normalisation rules

- Use adjusted daily prices for return, moving-average, range, and drawdown
  calculations; retain raw prices separately for audit.
- Never compare partial-session volume with a full-day average without elapsed-time
  normalisation.
- Map symbols, exchange, currency, and timezone before joining providers.
- A vendor response with an empty holdings array means unsupported until confirmed;
  it does not mean the ETF has no holdings.
- Financial observations use the filing/publication date, not the fiscal period end,
  for point-in-time joins.
- Provider errors and stale observations become explicit coverage gaps.

## Current hard gaps

Kiwoom's US market feed cannot supply home-market candles for every Australian or
Chinese lithium holding. FMP coverage varies by exchange. A lithium-miner breadth
calculation must therefore publish both covered weight and excluded tickers.
Neither vendor provides a complete, authoritative lithium spot and forward curve;
that input requires a separately documented primary or specialist source.
