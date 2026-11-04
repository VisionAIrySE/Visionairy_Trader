# Joint research mechanics and private review UI

Goal: compare where capital can work best in upward momentum, enter at justified price/scale, mitigate downside, capture gains and evaluate net outcomes. Intended positions typically span 1-2 days and may extend to approximately a week. This implementation continues SOT v0.52 and does not replace the accepted intelligence families or introduce live order authority.

## Delivered mechanics

`portfolio_ledger.py` keeps shared settled cash, reservations, positions, entry cost, marks, planned risk, realized net P&L and unsettled proceeds. Entries cannot exceed exact reservation terms or current 1%/5% ceilings. Duplicate entry and oversized exit attempts fail. A partial exit removes proportional basis and initial planned risk from the position. Realized sales release position risk, while proceeds become spendable only at an explicitly configured later session open. A missing settlement session leaves proceeds unsettled. Session calendar and settlement lag are experiment inputs, not qualified broker rules.

`portfolio_replay.py` combines point-in-time acquisition comparisons with chronological modeled entries/exits, completed-bar marks, session settlement and the paper-only daily pause. Later results do not alter earlier snapshots. Completed positions may release their symbol for a new opportunity, subject to then-current evidence, cash, risk and pause. Censored positions remain open and prevent a complete net account-return claim. This flat-account experiment requires initial equity equal to settled cash; it does not invent existing holdings or cash flows.

`management_replay.py` compares initial protection/hold with optional partial profit at an explicit multiple of initial price risk and optional trailing protection at a declared initial-risk distance below completed closes. Stop changes take effect on the next bar. Stops win ambiguous stop/target/partial bars. These are research alternatives, not standing approved management rules. Each partial/final exit incurs its own modeled fee. Full fills require the prior-bar activity cap. The ledger retains conservative original planned risk for remaining quantities rather than recycling risk because a modeled stop tightened.

`purpose_runner.py` accepts optional `portfolio_experiment` settings with `settlement_sessions` and `management_variants`. The original independent outcomes, conservative acquisition plan and allocation-bound outcomes remain intact. Alternative management runs are mutually exclusive account paths, never additional independent trades. No automatic strategy adoption occurs.

## Verification and actual data boundary

163 local checks pass: 156 research/UI plus 7 sizing. New checks exercise shared balances, delayed settlement, partial accounting, duplicate entries, oversell prevention, no mutation on invalid exit, current-equity ceilings, stale marks, latched paper pause, censorship, prior-only allocations, management alternatives and authenticated HTTP handler routes. The local environment denies outbound loopback connections; dashboard routing tests therefore send serialized HTTP requests through the actual handler using an in-memory transport. Hosted network/browser verification remains a separate release check.

The synthetic walkthrough uses two invented symbols over three declared 390-minute sessions, with a 780-trading-minute holding experiment and overnight price changes. Its path deliberately exercises momentum/profit/protection mechanics. Numerical outcomes are synthetic illustrations, not return forecasts or market findings.

A fresh read-only archive inspection found 10 sources and five symbols: AAPL, AMD, AMZN, KOPN and SPY. The original three-stock pilot remains withdrawn as strategy evidence. No representative new market cohort, genuine ROI validation or held-out/forward test was completed. Secure continuing market access, representative dated membership/history/quotes and frozen later evaluation remain needed.

## Private UI and operations

The read-only dashboard shows capital through the synthetic scenario, all considered opportunities and allocation reasons, entry/ceiling/quantity/risk, account events, management alternatives, provenance and readiness. It does not connect to private Supabase records, query a broker, run a live scanner or accept order/approval actions. Supabase remains the intended authoritative hosted store; there is no schema change or substitute hosted SQLite store.

All UI/data routes require HTTP Basic authentication over hosting TLS. The server requires an externally configured username and SHA-256 hash of a high-entropy generated password. Only generic `/health` is unauthenticated. No directory serving, arbitrary file reads, request-body ingestion or trading endpoint exists. Credentials and generated reports stay excluded from publication. Authentication fails closed when unconfigured. Durable per-user sessions, Supabase Auth enrollment and browser logout are future work; the designated project currently has zero Auth users.

Deployment uses the existing VisionAIrySE/Visionairy_Trader source repository, reviewed source-only publication, a free Render web service and no new paid resources. A free preview may sleep and is not an always-on trading runtime. Release status and remote verification must be reported separately from local checks.

Remaining mechanics: additions with cumulative protection/giveback, correlated exposure constraints, partial-fill order lifecycle, actual broker settlement/session rules, external-flow/recovery accounting, durable account/session state, operational approvals, persistent research runs and qualified intelligence/data feeds. The present ledger is an in-memory deterministic research engine with a chained event record, not a production account service.
