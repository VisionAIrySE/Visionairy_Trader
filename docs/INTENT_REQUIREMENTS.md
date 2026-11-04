# Stock-selection correction: intent, behavior and evidence

Accepted intent comes from A54/A55 of the private Source of Truth: measure upward percentage movement and unusual participation, with a distinct previously-quiet-stock cohort. Broader accepted setup research remains separate. No ticker blacklist, price/market-cap cutoff or account-affordability restriction was agreed.

Numerical quiet/activity/price thresholds remain experimental. SelectionPolicy requires explicit versioned values; they are not silently adopted recommendation rules. This correction does not establish a profitable threshold or complete trade qualification.

| Requirement | Required behavior | Acceptance evidence |
|---|---|---|
| S01: Measure intended cohort | Prior-quiet baseline, upward price move and unusual activity are all required for quiet-to-active classification. | Synthetic quiet/burst passes; price-only and activity-only cases fail. |
| S02: Separate controls | Already-active momentum cannot represent quiet-to-active evidence. | Busy-stock fixture is a control; real AAPL/AMD/AMZN sample has zero quiet classifications under three diagnostic cutoffs. |
| S03: No convenience substitution | A fixed familiar roster cannot qualify a target-cohort study. | Convenience roster rejected; legacy acquisition/replay require explicit infrastructure-only mode. |
| S04: Account-independent discovery | Price and account affordability are absent from discovery filters. | High-price fixture still detected; execution remains unassessed. |
| S05: No ticker-name assumptions | Classification follows evidence, not familiar/unfamiliar names. | Quiet synthetic series is classified identically when labeled AAPL. This does not claim real AAPL is quiet. |
| S06: Prior information only | Baselines use complete earlier sessions; signals use completed current windows. | Future changes leave past decisions unchanged; missing bars block affected windows. |
| S07: Sparse data stay uncertain | Zero baseline is not infinite activity; absent bars are not zero volume. | Zero-baseline and missing-bar cases remain insufficient evidence. |
| S08: Absolute context | Large ratios do not replace minimum observed recent dollar activity. | Tiny-denominator fixture rejected. Dollar activity is a price-times-volume proxy, not executable liquidity. |
| S09: Preserve negative cases | Record nonactivation, missing evidence, controls and repeated-burst updates. | Per-window decisions/reasons; legacy report includes zero-signal definitions. |
| S10: Declared coverage | Partial symbol/session data cannot claim complete coverage. | Missing members/calendar slots fail readiness; current listing cannot be backdated. |
| S11: Discovery is not recommendation | Bar-pattern candidates remain unqualified for recommendations/execution. | Records retain missing quote, remaining-opportunity, protective-exit and account-risk evidence. No order method exists. |
| S12: Withdraw mis-scoped evidence | Keep originals intact but visibly ineligible as target-strategy evidence. | Legacy report role changed; additive database intent-scope error verified; original run/data not rewritten. |

## Measured fit of the existing inputs

The frozen original run's five-minute baseline sources show these prior-ten-session median daily share-volume ranges over its evaluation dates:

| Stock | Prior daily baseline range |
|---|---:|
| AAPL | 25,105,506–29,114,606.5 shares |
| AMD | 14,549,363.5–16,318,452 shares |
| AMZN | 25,846,555.5–26,816,428.5 shares |

All three are already-active under each diagnostic quiet cutoff of 50,000, 100,000 and 500,000 daily shares. These were untuned sensitivity checks, not selected strategy settings. The sample contains no quiet-cohort evidence under those definitions. Study readiness is false for universe, instrument/calendar qualification and cohort-fit reasons. This demonstrates the earlier study's mismatch, not replacement trades.

## Current completion boundary

Implemented: explicit cohort measurements/reasons, control separation, legacy guard, reporting withdrawal and coverage checks. All 77 local tests pass, including 23 added regression checks. Synthetic cases prove software behavior only.

Remaining: qualify stock/ETF identities and exchange calendars, obtain dated market membership and representative histories including quiet and failed cases, run the corrected study, and review actual candidates/outcomes. Quotes, remaining opportunity and realistic risk/exit/portfolio evaluation remain unfinished. No genuine replacement strategy result is claimed.

A current broad exchange directory was captured privately for prospective coverage. It does not establish historical membership, security-type qualification or price coverage; it does not make a corrected strategy study ready.
