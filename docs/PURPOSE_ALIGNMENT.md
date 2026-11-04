# SOT implementation and evidence map

This map covers all 55 numbered accepted items plus A06a. It preserves purpose without treating software tests or database tables as operational completion. Original private SOT wording governs; this public map omits account details.

| Purpose area | SOT items | Current evidence state | Implementation | Remaining evidence |
|---|---|---|---|---|
| discovery and delivery | A01, A33, A34, A54, A55 | component only | discovery_selection.py; purpose_pipeline.py | Measured target-cohort selection exists; broad timed market coverage and Telegram delivery are not operating. |
| approval and execution | A02, A15, A16, A38, A52 | partial schema and analysis | decision_analysis.py; db/integrated_functions.sql | Decision relationships and DB approvals exist; authenticated channel approval, broker submissions and reconciliation are unqualified. |
| complete outcome records | A03, A20, A21, A22, A23, A24, A48, A49 | component only | decision_analysis.py; managed_replay.py; research_store.py | Independent modeled cases and linked comparison records exist; complete real recommendation/decision/fill history and dashboard analysis do not. |
| experience and modification | A04, A36, A47, A50 | not operating | docs/COMPLETION_PLAN.md | Private single-user workflow, phone/desktop dashboard and conversational interaction remain unimplemented. |
| cost and provider context | A05, A06, A06a, A28, A29, A30, A53 | qualification incomplete | docs/STATUS.md | Operating budget and selected provider are constraints/context; continuing secure runtime access, coverage and measured costs are not qualified. |
| setup and holding | A07, A08, A09, A10 | component only | setup_detection.py; managed_replay.py | Breakout/pullback and hours-to-days conditional cases exist; real model evidence, overnight eligibility, warning/discretionary exit policy need qualification. |
| protective management | A11, A12, A13, A14, A17, A18, A19 | partial component | setup_detection.py; managed_replay.py; decision_analysis.py | Structure/volatility stop and cost-aware sizing/gap cases exist; live stop warning, adjustment safeguards and broker/session coverage are not qualified. |
| learning and preferences | A25, A35, A37, A43 | partial schema and analysis | db/learning_hardening.sql; decision_analysis.py | Versioning, approval guards and comparison structure exist; scheduled held-out learning and approved adoption are not operating. |
| capital and paper proof | A26, A27, A44, A45 | partial component | managed_replay.py; discovery_selection.py | Discovery ignores affordability; independent risk arithmetic honors 1%/5% ceilings. Joint portfolio, settlement, correlation, giveback and forward paper proof remain missing. |
| instrument scope | A31, A32 | partial component | universe_snapshot.py; purpose_pipeline.py | Only qualified stock/ETF identities may pass the research gate; no short-order adapter exists. Actual instrument mappings and specialized ETF policy remain open. |
| other signals and experiments | A39, A40, A41, A42 | research scope uncompleted | docs/RESEARCH_PLAN.md; decision_analysis.py | Price/volume target path exists. Catalyst-only/combined, benchmark/AI ablation, advanced families, additions and partial exits require separate implemented comparisons. |
| unattended operation | A46, A51 | not operating | docs/COMPLETION_PLAN.md | Independent hosting, overnight fresh data, health/recovery, delivery and cost measurements are not qualified. |

All O01-O11 open-decision records remain explicit; none are silently converted into approved numeric settings. O11 has an agreed paper-only 3% daily pause, while live daily-loss policy remains open.

Run `python research/purpose_audit.py` for the machine-readable item mapping and decision chain. Overall operating readiness and live eligibility remain false.

## Current practical boundary

The research path is connected and tested for the quiet-to-active price/volume experiment. Research thresholds and target hypotheses remain explicit and unvalidated. A suitable representative historical market dataset, secure continuing market-data access, qualified identity/calendar/coverage, and later unseen results are still required.

The model includes decision types for additions, partial exits, stop amendments and preference/strategy changes so their evidence cannot disappear from analysis. Those types do not mean their complete simulators, interfaces, approvals or broker operations have been implemented.

No hosting, trading service, real orders, account write, funding, paid-resource purchase, broad market scan or model promotion occurred during this alignment work.
