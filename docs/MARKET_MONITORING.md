# Continuous market discovery: implementation boundary

The platform must find eligible opportunities throughout its supported stock/ETF universe, compare them with competing uses of capital and cash, monitor positions, and retain evidence for evaluation. A model call or a small fixed watchlist is not this capability. The current hosted model example is synthetic; continuous discovery and notifications remain unconnected.

## Intended acquisition and decision path

1. Maintain a versioned instrument universe and explicit venue/session/data coverage. Do not filter discovery by current cash or by previously successful stocks. Retain unknown asset classifications and unsupported symbols.
2. Obtain sufficiently broad market observations for discovery. Narrow to active candidates for more detailed streaming only after discovery; a symbol-list stream alone cannot establish full-universe coverage.
3. Build validated point-in-time observations and completed bars, retaining corrections, gaps, arrival time and source identity. Trade/volume events and bid/ask quotes have distinct meanings. Mark stale or missing inputs unavailable.
4. Apply versioned deterministic setup criteria: independent breakouts, resumed pullbacks and quiet-to-active candidates are separately tracked. Do not silently change thresholds or adopt experiments from favorable results.
5. Join current source-grounded news, relevant decision-time research and confirmed preferences. Models interpret the evidence; code controls prices, sizing, spendable cash, risk and eligibility. No model can grant order authority.
6. Compare eligible opportunities and cash. Retain blocked candidates and reasons. A valid no-candidate result must be distinguished from a failed feed or incomplete coverage.
7. Persist the decision and deliver an authorized notification with actionable terms, supporting evidence, uncertainty and expiry. Delivery failure is not user rejection. Keep monitoring positions and relevant updates afterward.

## Existing-access facts verified on 2026-11-05

Tradier documents streaming quotes, trades, summaries and time-and-sales for an explicitly supplied symbol list. Its stream `filter` selects event types, not custom strategy rules. It allows one market stream at a time and discourages requesting an entire exchange. Market streaming requires the live environment, not sandbox. Live market observations can be used for ghost research without enabling orders.

Sources: [Streaming](https://docs.tradier.com/brokerage-api/streaming), [Create market session](https://docs.tradier.com/streaming/create-market-session), [WebSocket market data](https://docs.tradier.com/streaming/websocket-market-data-streaming).

Current account-specific streaming entitlements, sustainable broad discovery coverage, a verified live news source, retention/licensing terms and end-to-end feed latency have not yet been established. Existing authenticated account/historical reads do not prove those capabilities. Another market-wide discovery source may be necessary; no new provider or purchase is selected here.

The existing Render dashboard uses the free web-service plan. It is not qualified for uninterrupted trading-session monitoring. A continuous scanner requires an appropriate hosted runtime with durable checkpoints, recovery and health/lag reporting. No hosting upgrade or paid data subscription was made for the model integration.

## Operating acceptance before claiming live discovery

- Show the supported universe, actual observed coverage, source freshness and unsupported instruments; validate current entitlements and applicable quotas.
- Exercise the existing detectors incrementally against recorded point-in-time input, including a real qualifying event, a valid no-match interval and a disconnected/stale-feed interval.
- Demonstrate reconnect/backfill and restart recovery without future-data leakage or duplicate opportunities.
- Reconcile candidates, code-owned allocation/risk decisions, source-grounded model assessment and retained decision records.
- Verify authorized notification delivery, expiry, update identity and failed delivery handling separately from trading authority.
- Measure latency distributions, data/hosting/model costs and budget feasibility; keep any unapproved paid commitment explicit.

Until these checks pass, the product must say that live discovery is not operating. Embeddings/retrieval quality, learning adoption, strategy profitability and real-order authorization remain separate gates.
