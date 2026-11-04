# Hypothesis-to-data readiness

Checked November 4, 2026, Pacific time. This is an inventory and scope assessment, not strategy results or a renewed Discovery process.

## What the captured archive supports

The archive contains 10 source records and 27,276 observations across AAPL, AMD, AMZN, KOPN and SPY. It can support limited source-pinned bar diagnostics and explicitly modeled cost/management scenarios. It does not yet qualify a representative test of the intended momentum strategy. The old AAPL/AMD/AMZN convenience pilot remains withdrawn as target-strategy evidence.

| Symbol | Interval | Rows | Observed dates | Internal missing grid slots | Supplied VWAP values |
|---|---|---:|---:|---:|---:|
| AAPL | 1min | 3900 | 10 | 0 | 3900 |
| AAPL | 5min | 1872 | 24 | 0 | 1872 |
| AMD | 1min | 3900 | 10 | 0 | 3900 |
| AMD | 5min | 1872 | 24 | 0 | 1872 |
| AMZN | 1min | 3900 | 10 | 0 | 3900 |
| AMZN | 5min | 1872 | 24 | 0 | 1872 |
| KOPN | 1min | 3766 | 10 | 134 | 3766 |
| SPY | 1min | 3900 | 10 | 0 | 3900 |
| SPY | tick | 2294 | 1 | 0 | 0 |

Dates group UTC timestamps; this does not independently qualify the exchange calendar. Internal gaps exclude missing session edges and entirely absent dates. SPY trade prints span roughly one minute and are not executable bid/ask or full order-book history. Supplied VWAP fields need provider-convention qualification.

## Accepted hypotheses retained

Every family below remains within research scope. A pending item has not been discarded. All strategy-validation readiness flags are currently false.

| Hypothesis | Current use of captured evidence | Missing before a defensible strategy comparison |
|---|---|---|
| Prior quiet + upward price + unusual activity | diagnostic only: Prior-session bars and activity statistics | Representative dated quiet/control cohort; qualified calendar and baseline coverage |
| Initial upward breakout | diagnostic only: OHLC bars and implemented structural setup component | Qualified cohort, predeclared target/entry policy and historical execution assumptions |
| Controlled pullback with resumed buying | diagnostic only: OHLC/volume and implemented resumption component | Suitable independent positive/failed setups and complete follow-through |
| Time-of-day relative volume | diagnostic only: AAPL 1min: 10 observed dates; AAPL 5min: 24 observed dates; AMD 1min: 10 observed dates; AMD 5min: 24 observed dates; AMZN 1min: 10 observed dates; AMZN 5min: 24 observed dates; KOPN 1min: 10 observed dates; SPY 1min: 10 observed dates | Qualified session slots and sufficient prior complete sessions for every evaluation event |
| Compression, ADX, Bollinger, RSI/MACD and moving-average variants | data partial implementation pending: OHLC/volume can support declared bar-derived calculations | Implement/freeze each accepted experiment; avoid treating correlated indicators as independent evidence |
| Opening-range / previous-day-high breaks | data partial implementation pending: Multi-session OHLC bars for limited symbols | Qualified regular-session calendar and separate frozen trigger definitions |
| VWAP reclaim / retest | approximation only until qualified: 24982 captured VWAP values; provider convention not qualified | Qualify provider VWAP convention; bar approximations are not exact observed session VWAP |
| Strength versus market and sector | partial market control only: SPY minute history permits limited aligned market-control diagnostics | Sector histories and point-in-time memberships; representative comparison cohort |
| Market breadth / sector participation | missing required evidence: A limited captured roster does not establish market breadth | Broad contemporaneous symbol coverage and dated sector/universe membership |
| Catalyst-only and combined catalyst/technical signals | missing required evidence: No timestamped catalyst archive in captured market store | Dated original news/catalysts and actual availability times, including missing/negative cases |
| New versus recycled news and price response | missing required evidence: No historical story/version archive | Timestamped original stories, duplicates, revisions and point-in-time response rules |
| Economically related-stock lead/lag | missing required evidence: Incidental overlap of five histories | Predeclared economic relationships and sufficiently complete aligned peer histories |
| Failed breakdown / reclaim | data partial implementation pending: Limited OHLC histories | Separate frozen detection rules and qualified cohort; do not relabel breakout tests |
| Momentum persistence / continuation versus exhaustion | diagnostic only: Limited price/activity paths and setup extension measures | Predeclared outcome labels and suitable independent failures/continuations |
| 1-2-day to approximately week-long holding and protection | conditional scenarios only: Multi-session bars; initial/partial/trailing/gap replay components | Sufficient future sessions per event, explicit calendar/horizon, realistic costs; additions/giveback incomplete |
| Spread, liquidity, slippage and approval delay | conditional scenarios only: Bars plus a short SPY trade-print probe; no captured executable bid/ask history | Observed quote/depth/fill/delay evidence or explicitly modeled stress assumptions; trade prints do not prove fills |
| Compare opportunities, shared capital and retaining cash | conditional scenarios only: Acquisition comparison and joint paper-account components | Point-in-time target hypotheses, historical input adapter, suitable competing cohort; correlation/additions incomplete |
| AI/news incremental value and learning/adoption | missing required evidence: Versioned trials, decision records and learning guards exist | Frozen prediction/feature records, matched ablations and later unseen evaluation; no automatic adoption |

## Rechecked cohort fit

The preserved three-stock baseline was rechecked using the existing untuned diagnostic daily-volume cutoffs of 50,000, 100,000 and 500,000 shares. Under each cutoff, each symbol had 770 already-active classified windows and 10 unknown windows; no quiet-cohort window qualified. These repeated windows are not independent trades. The study gate remains false under all three diagnostic definitions. This is evidence of scope mismatch, not evidence against momentum or proof of an optimal quiet cutoff. KOPN has only ten observed minute-history dates and missing slots; it cannot be substituted for a complete earlier-ten-session baseline plus evaluation sample.

## Next bounded historical step

1. Freeze the supported bar-diagnostic definitions and source identities before examining new outcomes.
2. Build an explicit archive-to-runner diagnostic bundle, preserving incomplete windows and the old sample control-only label. Do not manufacture historical quotes or targets from future highs.
3. Close dated cohort, calendar, earlier-baseline, corporate-action and follow-through gaps before claiming a representative study. Add historical catalysts, sectors/peers or executable quotes only for experiments that require them.
4. Evaluate initial breakout and resumed pullback separately over explicit multi-session horizons; compare management alternatives as mutually exclusive account paths.
5. Report costs, delays, nonfills, censored outcomes, capital occupancy, drawdown and benchmark evidence. Reserve later unseen data for adoption decisions.

Live scanning, Telegram, real orders and account funding are not prerequisites for offline diagnostics. Current live account equity does not constrain research capital or discovery.

## Reproduction

Run `python research/hypothesis_readiness.py --database data/original/research_snapshot.sqlite --output data/hypothesis_readiness.json`. This opens the archive read-only and emits no signals or P&L. The generated JSON and captured market data remain private/excluded from publication.

Source manifest SHA-256: `ae275b0e40878964bad0eea6b18c0be8c492dbc4d089d1f51090d5006157f313`.
