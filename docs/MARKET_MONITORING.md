# Continuous market discovery: implementation boundary

The platform must find eligible opportunities throughout its supported stock/ETF universe, compare them with competing uses of capital and cash, monitor positions, and retain evidence for evaluation. A model call or a small fixed watchlist is not this capability. The hosted model example is synthetic. A bounded broad quote monitor is implemented; continuous operating discovery and notifications still require qualification and activation.

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

## Broad quote monitor implementation - November 5, 2026

`research/market_monitor.py` collects the refreshed exchange-listing universe in bounded batches of up to 500 using Tradier's documented read-only POST market-quotes endpoint. Source response hashes, timestamp validation, missing symbols, unsupported mappings, instrument qualification, market clock and batch progress are explicit. Daily cumulative volume is not represented as same-time-of-day relative volume. An experimental 2% price rise with additional reported volume between observations is a coarse research lead only; it does not implement the full approved strategy universe or authorize a buy.

The private dashboard exposes authenticated bounded start/status/stop controls. Each scan runs outside the HTTP request thread and checkpoints progress durably. A ten-minute cross-instance lease prevents concurrent full scans; interrupted leases become explicit failures. Completed normalized state rotates for the next comparison; immutable cycle summaries, lead before/after evidence, issues and source hashes remain retained. Partial/cancelled cycles never replace the last complete baseline. This is operational snapshot state and a decision audit, not a complete historical tick archive.

The refreshed November 5 directory contains 13,244 listings; it is not a statement that all are eligible common shares, mapped, tradable or observed. Supported metadata, timestamp and symbol gaps remain visible. A postmarket coverage probe can measure access and data shape but cannot establish regular-session freshness, valid no-opportunity intervals, strategy detection performance, or profits.

Storage uses the existing authenticated assessment-store function and private namespaced job rows. No browser receives broker/model/storage credentials. The existing model budget reservation and saved ghost assessment remain in place. No order submission path is added.

Continuous collection has two explicit configuration guards, SCANNER_AUTORUN and SCANNER_HOSTING_APPROVED. Both default off. The proposed loop is a five-minute quote sweep, not a market event stream or low-latency breakout detector. Render's current free instance is not accepted as reliable always-on hosting. A paid compute commitment requires the user's approval, separate from the $25 total operating ceiling.

Local verification after the classification/freshness correction: 223 research/dashboard tests plus 7 sizing checks; JavaScript syntax check passed. Hosted full-universe receipts must be recorded separately before coverage is claimed.

Hosted first-probe receipt: cycle `6c6484a6-78ee-4ef1-859e-9405b99bcf9b`, 27 batches, 62 seconds, 12,598 usable observations / 13,244 listings; 523 absent, 13 invalid, 110 mapping gaps. Postmarket freshness and entry eligibility remained false. The classification fix supersedes that cycle's security-type breakdown. Cancellation and cross-instance duplicate-cycle rejection were verified against the real private endpoints. The existing completed ghost model example remained available; no extra model calls were started by coverage collection.

Before unattended activation, automate and verify the daily listing refresh. A stale or future directory capture now fails explicitly instead of becoming assumed current coverage. The proposed $7/month 0.5c-512mb compute instance is a reviewed hosting option (https://render.com/pricing), not an authorized purchase or a declaration that the end-to-end assistant is ready.

Final corrected-release verification: commit a009fe4d6d1d3d8585dab4d461368c02ea45637a is live as dep-dbmfdu6c6qcc73eeseng. Repeat cycle 4c8d6af3-1f8f-455e-b8be-5a61e9ed5856 completed in 60 seconds, reused the durable baseline and independently repeated all numeric quote-coverage counts. Its completed baseline (813,920 compressed characters) was read back and matched the cycle. Corrected instrument-status counts: {'etf_subtype_pending': 5780, 'security_type_pending': 269, 'special_security_not_ordinary_qualified': 942, 'directory_and_broker_common_share_indicated': 5607}. These are indicated/pending classifications, not trading eligibility. 223 research/dashboard and 7 sizing tests passed. The saved ghost assessment remained complete.
