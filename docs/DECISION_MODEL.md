# Decisions, evidence and outcome analysis

Purpose: identify worthwhile fresh upward moves, preserve the owner's control of risk/actions, and learn which decisions improved or damaged outcomes. A price trigger alone is not the product.

## One connected research path

Qualified dated universe and calendar -> complete source-pinned observations -> measured price/activity discovery -> separate initial breakout or pullback resumption -> timestamped conditional target/cost/risk check -> risk-sized independent replay -> hours-to-days exits -> linked outcome evidence.

`purpose_runner.py` executes this path from an explicit bundle. `purpose_pipeline.py` refuses mismatched/partial/convenience data before outcome calculations. Every modeled case connects to a discovery root and exact policy/evidence versions. The current implemented experiment is the quiet-to-active price/volume cohort; other accepted cohorts are retained in the requirements audit as unimplemented work, not silently removed from the platform.

## Decisions that the model must retain

| Decision | Evidence/terms to retain | Comparison needed | Current boundary |
|---|---|---|---|
| Observe or track a move | Prior baseline, raw price movement, unusual activity, timing, coverage and uncertainty | Fresh detection vs missing/late/false detection | Target selector tested; representative real coverage missing |
| Enter, wait, modify, decline or leave unanswered | Breakout or resumed pullback; original/revised entry, size, stop; exact decision time | Same opportunity under predeclared decision/timing alternatives | Setup components and graph tested; authenticated interactive review missing |
| Size exposure | Current cash/equity convention, stop distance, costs, existing trade and aggregate planned risk | Risk-sized vs predeclared comparable alternatives | Independent-case 1%/5% arithmetic tested; shared portfolio/settlement/correlation not complete |
| Keep or change protection | Existing stop, volatility/structure, warning, proposed terms, approval and confirmation | Original stop unchanged vs approved adjustment | Initial stop/gap model and graph tested; operational warnings/amendments not built |
| Add to winner | Separate add terms, cumulative trade risk, total exposure and giveback | No add vs independent/combined protection or partial profit | Decision type present; addition simulation/protection/giveback comparisons missing |
| Take partial profit | Quantity, remaining exposure and exit/protection terms | Partial exit vs unchanged position under common capital convention | Decision type present; quantity/portfolio management simulator missing |
| Hold overnight, reduce or exit | Session/catalyst risks, fresh data, protective-order coverage and explicit response | Overnight policy alternatives including gaps and foregone opportunity | Explicit overnight research and gap cases tested; real eligibility/no-response policy unresolved |
| Exit | Trigger, decision, approval, executable observations, partial/missing fills and resulting position | Original exit rule vs decision timing/execution/management alternatives | Conditional full-fill stop/target/time cases tested; actual broker lifecycle unqualified |
| Pause new exposure | Session equity baseline, external flows, fresh valuation and existing protection | 3% paper pause vs predefined comparison | Paper-only predicate tested; persistent joint portfolio/session controller missing |
| Give feedback or propose preference | Explicit feedback, proposal, revisions, approval and version | Preference fit separately from strategy performance | Graph and DB guards exist; user workflow/learning jobs missing |
| Adopt a strategy change | Exact candidate, earlier selection history, independent comparisons, human approval | Frozen later unseen/held-out evidence with costs/uncertainty | DB proof guards exist; operational learning/adoption missing |

All decision records have a stable opportunity ID, parent decision IDs, decision/evidence timestamps, canonical exact terms and evidence, policy version, evidence mode and chained content hashes. Duplicate identical records do not create duplicate actions. Records do not grant order authority. Cross-channel authorization, durable concurrency and broker confirmation remain separate unfinished requirements.

## Conditional opportunity, not an invented forecast

The remaining-opportunity component requires a dated, source-identified target hypothesis in the intended holding window. It checks current bid/ask age, spread, proposed stop and assumed friction. Targets cannot come from later highs. Changed stop/target terms invalidate the earlier assessment. Delayed entry must still clear its cost/risk test.

A favorable reward/risk calculation is conditional on the supplied hypothesis. It is not an estimated win probability, positive expectancy, validated target model, user approval or an executable recommendation. Those claims remain false in pipeline output.

## Interpreting performance

The joined result now also exposes `acquisition_outcomes`: conditional cases bounded by the comparative plan's reservations. Exact setup/assessment and reservation hashes link these outcomes to selected terms. Nonselected cases retain their reasons without modeled allocated profits; delayed entries cannot increase reserved quantity, cash or planned risk and must respect entry ceilings and fee-aware minimum reward/risk. Original `outcomes` remain independent controls. Neither output is a settled account equity curve. See docs/ACQUISITION_FUNNEL.md for the 144-check local checkpoint and remaining management/market-evidence gaps.

Predeclare and pin four comparable paths: recommendation baseline; user decision/timing/terms; execution effects; management effects. Match opportunity, currency, time interval, capital convention, decision graph and strategy versions. Censored evidence blocks arithmetic. Declined, unanswered, expired and unaffordable recommendations remain distinct; they are not inferred preference changes or observed trade losses.

Differences between these paths are ordered conditional comparisons, not independent causal effects. Keep modeled versus observed evidence visible. Do not pool alternative entry/management scenarios as independent trades, infer portfolio returns from independent cases, or adopt preferences/strategies from this arithmetic.

## Evidence from this implementation

All 117 local checks pass: 110 research checks plus 7 sizing checks. The added 40 checks cover the joined path, setup distinctions, remaining-opportunity timestamps/costs/horizon, cumulative risk, gaps/exit uncertainty, decision lineage, comparison identity and paper-only daily pause behavior.

The joined positive fixture is synthetic: one initial breakout and one pullback continuation, each held for 120 trading minutes, with 11 linked decision records. Its conditional P&Ls are $0.80 and $0.00 under fixture assumptions, not market results. Separate cases demonstrate stale/missing/future evidence rejection, a stalled pullback, exhausted entry opportunity, missing horizon/exit activity, stop-first ambiguous bars and overnight losses exceeding planned risk.

The earlier real three-stock convenience sample remains withdrawn as target-strategy evidence. No new suitable real-market study, validated target model, joint portfolio result or operating assistant is claimed.
