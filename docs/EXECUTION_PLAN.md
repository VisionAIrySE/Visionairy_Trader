# VisionAIry Trader: executable delivery plan

This is the current work queue. The accepted private SOT governs intent and authority. Existing status documents remain historical evidence; this plan governs the order of remaining delivery.

**Target:** An integrated proactive long-only US stock/ETF momentum assistant comparing where, when, price and scale against competing opportunities and cash, protecting exposure and learning from complete outcomes.

**Current authority:** research/internal ghost simulation and existing authorized implementation/deployment. No broker orders, funding, purchases, paid upgrades or automatic standing-risk/strategy adoption.

**First concrete result:** record a real historical exploratory experiment in the hosted database and show its simulated buys, sells, losses/nonfills and net results. Full-market/news/AI completion is not a prerequisite for a supported limited test.

## How execution proceeds

The assistant owns implementation and verification. The user is not asked to reconstruct settled decisions or choose routine implementation details. A fresh conversation reads this file, its JSON task graph and the current private receipt state, then continues the next ready task.

```powershell
python research/execution_plan.py validate
python research/execution_plan.py next --limit 3
python research/execution_plan.py status
python research/execution_plan.py record --task TASK_ID --receipt data/TASK_ID_receipt.json
python research/execution_plan.py block --task TASK_ID --reason "Specific blocker and remedy"
python research/execution_plan.py resume --task TASK_ID
```

A receipt must name the exact plan hash/task and contain one passing finding and content-hashed local evidence artifact per acceptance criterion. Dependencies must already be complete. Artifacts/receipts remain private under data/. Changed evidence invalidates completion on the next status check. A count of passing software tests alone does not satisfy integration, market-evidence or operating gates. The controller validates identity/structure; the assistant must assess the actual evidence. It does not submit jobs/orders or execute arbitrary command strings. Separate order-authorization tasks cannot be completed by this generic receipt command.

At each task: intent → listed requirements → implementation → checks and actual evidence → acceptance review → recorded completion → next ready task. If blocked, preserve the reason, retry temporary failures appropriately and continue independent authorized work. Progress updates remain required at least every 60 seconds.

## Existing groundwork to retain

- Preserved original archive and withdrawn pilot scope; 48 private hosted research/learning tables and reconciled earlier import.
- Risk, sizing, selection, comparative allocation, multi-session replay and joint ledger/partial/trailing research components exist.
- Private Render dashboard, production read-only account observations, historical/calendar GETs and nonblocking account refresh verified.
- Frozen directory coverage probe returned 19 histories, one failed request and one symbol mapping block; latest hosted app remains research-only.
- 197 research/UI plus 7 sizing checks passed at the latest deployed checkpoint; newer local retry edits have three additional passing Node checks.

## Delivery milestones

| Milestone | Required tasks | Meaning |
|---|---|---|
| FIRST_REPORT | T02 | A readable persisted exploratory historical buy/sell report, not proven future profitability. |
| JOINT_ACCOUNT | P03, P04, P05 | Reconciled shared-capital/management simulation. |
| BROAD_RESEARCH | V02, H10, H11, H12, H13, H14, H15 | Supported accepted families evaluated with held-out evidence and explicit unavailable families, not automatic adoption. |
| OPERATING_GHOST | Q01, A01, A02, A03, A04, U04 | Integrated hosted proactive ghost system. |
| CONTROLLED_LEARNING | L03 | Evidence-backed approval-gated learning workflow. |
| FORWARD_EVALUATED | Q02 | Forward paper evaluation completed with an explicit result, which may be revise/stop. |
| BROKER_PAPER | B02 | Optional separately authorized broker sandbox execution. |
| LIVE | LIVE03 | Only separately authorized production release; not part of current authority. |

## Execution rules

- Follow this task graph and evidence receipts; historical STATUS/COMPLETION documents are records, not competing work queues.
- At each task: read inputs/reuse, implement its listed steps, run meaningful checks, preserve actual evidence, review all acceptance criteria, then record completion and move to the next ready task.
- A task may finish with a valid negative experiment result; that never marks the strategy effective or the platform ready.
- Do not wait for full market/news/AI coverage before a supported explicitly exploratory buy/sell simulation; constrain each claim to its dataset and assumptions.
- Never call synthetic checks profitability evidence; never call observed/control samples representative or unseen without support.
- Do not substitute test counts, schema tables, a plan, deployment or a modeled account for integrated operating behavior.
- Experimental settings are owned implementation choices with versions; standing live risk/authority and paid commitments require specific approval.
- Give meaningful progress at least every 60 seconds. State the active task, user-visible result, evidence and any real blocker.
- If one task is blocked, record cause/remedy and continue independent authorized ready tasks. Retry transient failures with bounded backoff; preserve all attempts.
- The plan runner validates dependencies and evidence identities. It cannot manufacture statistical proof or grant trading authority.

## Model assignments must be earned

| Job | Intended approach | Gate |
|---|---|---|
| Prices, scanning math, sizing, risk, replay, cash and order state | Deterministic validated code | LLM cannot override calculations or grant authority |
| News extraction and classification | Evaluate a suitably small/fast model | Accuracy/schema/source/latency/cost benchmark |
| Ambiguous catalyst/context reasoning | Evaluate a stronger reasoning model where it adds value | Cited evidence and measured improvement justify added cost |
| Search/retrieval | Evaluate embeddings/retrieval independently | Relevant sources, versioning and retrieval quality |
| User explanations | Grounded model output from reconciled records | Numbers supplied by code; no invented forecast or advice authority |

A bounded synthetic ghost-assessment route now connects the benchmark-selected news/research models with retained hosted receipts. LLM01/LLM02 remain subject to all their evidence gates, including provider/privacy qualification and independent incremental decision-value evaluation; this example does not complete them. No model name, price or superiority is invented here. The total operating budget remains $25/month unless a specific change is approved.

## Detailed tasks

### First historical delivery

#### R01 — Finish collection retries and evidence recovery

**Depends on:** Ready to start. **Authority:** research. **Owner:** assistant.

**Reuse/current boundary:** collect_history.mjs and collection_diagnostic.py have local retry edits; three Node tests passed; not yet published.

**Steps:**
- Finish bounded backoff for network, rate-limit and server failures
- Preserve every failed attempt; stop retrying permissions or invalid requests
- Retry the failed captured request; distinguish exhausted retries from repaired mapping; persist selected-success lineage

**Deliverable:** Versioned retry collector, actual attempt ledger and loader reconciliation

**Accept only when:**
- R01.1: Temporary failure then success is retained and consumed without overwriting the failure
- R01.2: Retry budget survives resume and prevents an infinite loop; permission failures stop
- R01.3: Actual failed capture has a recorded recovery or explicit exhausted attempts, observed failure status and next remedy; no unsupported diagnosis is inferred

#### S01 — Register complete executable experiment specifications

**Depends on:** Ready to start. **Authority:** research. **Owner:** assistant.

**Reuse/current boundary:** SelectionPolicy, SetupPolicy, ReplayPolicy and 18-family readiness catalog exist.

**Steps:**
- Create versioned specs for quiet-to-active, independent breakout and resumed pullback
- Declare entry, timing, stop, target/time exits, costs, risk, holding windows, controls and required data for each
- Declare remaining accepted families separately; freeze each experiment before its outcome run

**Deliverable:** Machine-readable strategy registry with code/spec hashes and supported/pending flags

**Accept only when:**
- S01.1: Independent breakout/pullback eligibility does not require quiet-stock eligibility
- S01.2: Each runnable spec contains all buy/sell/capital and evidence conventions; missing fields fail validation
- S01.3: Exploratory findings and adoption criteria are separate; no retrospectively selected target or optimized setting is called approved

#### DB01 — Persist new captures and runs in authoritative research storage

**Depends on:** R01. **Authority:** research. **Owner:** assistant.

**Reuse/current boundary:** 48 hosted tables and prior pilot import exist; latest captures are still local.

**Steps:**
- Inspect designated hosted schema and permissions
- Map captures, calendars, attempts and source identities without inventing instrument qualifications
- Import in idempotent batches with per-row conflicts, count/checksum reconciliation and complete/failed lifecycle
- Keep originals and earlier pilot role intact

**Deliverable:** Hosted new-source/dataset import plus repeatable writer adapter and verification receipt

**Accept only when:**
- DB01.1: Newest captures and attempt/source relationships are queryable in Supabase and reconcile to originals
- DB01.2: Repeat import changes no counts; conflicting revisions fail explicitly
- DB01.3: Unknown instruments remain unqualified/staged; no public writes or client secrets

#### H01 — Run independent initial-breakout detection

**Depends on:** S01. **Authority:** research. **Owner:** assistant.

**Reuse/current boundary:** classify_setups currently activates only from quiet_to_active_candidate.

**Steps:**
- Implement completed-bar resistance/structure trigger without quiet-cohort prerequisite
- Retain all eligible/failed windows and prior-only volatility/activity inputs
- Freeze rule and identify linked opportunities without outcome-based selection

**Deliverable:** Independent breakout detector and negative/future-data acceptance cases

**Accept only when:**
- H01.1: Busy-stock breakout can qualify the breakout experiment without becoming quiet-to-active evidence
- H01.2: Future changes do not change earlier signals; gaps block affected evidence
- H01.3: Every signal has a stable opportunity, source and strategy version

#### H02 — Run independent controlled-pullback resumption

**Depends on:** H01. **Authority:** research. **Owner:** assistant.

**Reuse/current boundary:** Existing pullback classifier and stop/ATR logic are reusable.

**Steps:**
- Track prior observable impulse, completed pullback and subsequent confirmation
- Declare depth, duration, volume, invalidation and duplicate-update behavior
- Preserve failed/stalled pullbacks alongside resumptions

**Deliverable:** Independent pullback strategy with observable impulse/pullback/entry lineage

**Accept only when:**
- H02.1: Pullback and confirmation cannot be inferred from the same ambiguous bar
- H02.2: Separate breakout and resumption outcomes are compared as dependent alternatives where appropriate

#### H03 — Connect the quiet-to-active experiment without narrowing the platform

**Depends on:** S01. **Authority:** research. **Owner:** assistant.

**Reuse/current boundary:** discovery_selection.py, archive and calendar-aware diagnostics exist.

**Steps:**
- Keep measured prior-quiet activity and time-of-day relative volume
- Supply expected calendar sessions so missing days cannot be skipped
- Preserve sparse/zero baseline unknowns and no-activation controls

**Deliverable:** Quiet-to-active strategy adapter and clear unavailable-evidence states

**Accept only when:**
- H03.1: Quiet, active and unknown cohorts stay distinct
- H03.2: Zero candidates is a retained result for this definition, not a veto on unrelated experiments

#### M01 — Define honest bar-level entry/exit and cost scenarios

**Depends on:** S01. **Authority:** research. **Owner:** assistant.

**Reuse/current boundary:** managed_replay.py and risk sizing already implement most arithmetic.

**Steps:**
- Declare targets from contemporaneous structure or a frozen risk multiple, never later highs
- Model delay, opening price, spread/slippage and fee stress cases with explicit evidence labels
- Require unchanged 1% trade and 5% aggregate ceilings; do not shrink stops to force size
- Include 1-2-session and approximately week-long alternatives with censored horizons

**Deliverable:** Versioned modeled execution/target scenario inputs

**Accept only when:**
- M01.1: Modeled quotes/fills cannot be labeled observed or broker-confirmed
- M01.2: Stops win ambiguous stop/target bars; missing entry/exit evidence remains unresolved
- M01.3: Scenario capital is explicit and independent of live account funding

#### T01 — Execute and persist the first actual historical buy/sell experiment

**Depends on:** DB01, H01, M01. **Authority:** research. **Owner:** assistant.

**Reuse/current boundary:** Existing replay, decision graph, DB tables and import checks are reused.

**Steps:**
- Select a source-pinned supported cohort before reading its outcomes; label existing controls honestly
- Replay fixed breakout rules using information available at each decision
- Persist signals, proposed entries, modeled buys/sells, nonfills, exits, fees and unresolved cases
- Reconcile quantities, P&L and source identities from database queries

**Deliverable:** A completed exploratory historical run with recorded simulated orders/fills/outcomes

**Accept only when:**
- T01.1: At least one complete run reaches persisted modeled transactions or a fully explained no-entry result; report cannot be a coverage-only audit
- T01.2: Every buy/sell can be recomputed from its frozen spec, data and costs
- T01.3: No unsupported strategy, whole-market, independent-trade-count or portfolio-return claim

#### T02 — Deliver the readable buy/sell and return report

**Depends on:** T01. **Authority:** research. **Owner:** assistant.

**Reuse/current boundary:** Build the missing integration; preserve existing records.

**Steps:**
- Show hypothesis, symbol, decision/entry time, price, size, protection, exit and reason
- Show gross/net result, return denominator, costs, holding time and unresolved cases
- Separate per-case returns from the later shared-account curve; compare cash and matching benchmarks where supported

**Deliverable:** User-readable first historical results, backed by database queries

**Accept only when:**
- T02.1: Displayed example totals exactly reconcile to stored fills and costs
- T02.2: User sees actual historical examples and losses/nonfills without reading code
- T02.3: Limitations constrain conclusions, not all exploratory simulation

#### T03 — Compare entry setups and price/volume alternatives

**Depends on:** T02, H02, H03. **Authority:** research. **Owner:** assistant.

**Reuse/current boundary:** Build the missing integration; preserve existing records.

**Steps:**
- Run frozen initial-entry, confirmation and retest/resumption alternatives
- Compare price-only, price/activity, quiet/control and missed/failed opportunities using matched definitions
- Retain separate versions and all trials

**Deliverable:** Matched historical experiment comparison report

**Accept only when:**
- T03.1: No overlapping setup/scenario alternatives are counted as independent trades
- T03.2: Performance is stratified by setup, basis, timing and coverage

### Market evidence

#### D01 — Qualify instruments, symbol mappings and available entitlements

**Depends on:** Ready to start. **Authority:** research. **Owner:** assistant.

**Reuse/current boundary:** Directory snapshot, authenticated historical reads and account observations exist.

**Steps:**
- Inspect existing provider access before selecting another service
- Reconcile exchange/broker symbols, stock/ETF types, listing dates, delistings and specialized ETFs
- Record licensing, retention, quotas, price and allowed uses; label unavailable features

**Deliverable:** Instrument/provider capability registry and explicit coverage constraints

**Accept only when:**
- D01.1: No warrant/preferred/inverse/leveraged instrument silently inherits ordinary stock eligibility
- D01.2: Discovery is independent of account balance and prior winners
- D01.3: Total operating-cost projection stays within agreed $25/month or identifies a specific unapproved overage

#### D02 — Acquire and freeze sufficiently varied historical cohorts

**Depends on:** D01, R01. **Authority:** research. **Owner:** assistant.

**Reuse/current boundary:** Build the missing integration; preserve existing records.

**Steps:**
- Choose dated cohorts before outcome inspection, including quiet/active, failed and losing cases
- Obtain warm-up and complete future holding periods over multiple market conditions
- Use prospective membership when historical membership cannot be obtained; never backdate directories
- Freeze development/evaluation datasets and selection history

**Deliverable:** Coverage-qualified datasets with dated selection, history and future-exit coverage

**Accept only when:**
- D02.1: Representative claims have documented selection/coverage support
- D02.2: Failed or unavailable symbols remain in the selection record
- D02.3: Previously inspected history is never called unseen validation

#### D03 — Resolve calendar, sparse bars, revisions and corporate actions

**Depends on:** D01. **Authority:** research. **Owner:** assistant.

**Reuse/current boundary:** Clock checks and expected-session gap guards exist.

**Steps:**
- Qualify timezones, start/end bar convention, market sessions, holidays and shortened days
- Distinguish documented no-trade intervals from missing feed data; never invent zero-volume candles
- Capture splits/dividends/symbol changes/revisions and adjusted/raw conventions
- Preserve immutable revisions and failure lineage

**Deliverable:** Reusable quality adapter and explicit eligibility masks by experiment

**Accept only when:**
- D03.1: Missing entire sessions and edges are detected against the declared calendar
- D03.2: Corporate actions cannot fabricate momentum or leakage
- D03.3: A bad input blocks its affected case/family rather than all unrelated research

#### D04 — Measure execution evidence and conservative stress assumptions

**Depends on:** D01. **Authority:** research. **Owner:** assistant.

**Reuse/current boundary:** Build the missing integration; preserve existing records.

**Steps:**
- Determine available historical quote/trade evidence and live quote timestamps
- Capture actual paper spread, receipt, approval and fill latency
- Compare observed evidence with declared bar-fill assumptions and liquidity/participation stresses

**Deliverable:** Execution-quality dataset and scenario calibration report

**Accept only when:**
- D04.1: Trade prints are never presented as executable bid/ask or depth
- D04.2: Costs, partials, gaps and stale prices are visible; unsupported precision remains labeled

#### D05 — Capture market, sector, breadth and peer context

**Depends on:** D01. **Authority:** research. **Owner:** assistant.

**Reuse/current boundary:** Build the missing integration; preserve existing records.

**Steps:**
- Collect aligned benchmark/sector histories and dated memberships
- Define breadth coverage and economic peer relationships before testing
- Align all observations by actual availability

**Deliverable:** Versioned context features and missing-coverage flags

**Accept only when:**
- D05.1: Five or nineteen captured symbols are not labeled market breadth
- D05.2: Future constituent/peer information is excluded

#### D06 — Capture timestamped catalysts and news versions

**Depends on:** D01. **Authority:** research. **Owner:** assistant.

**Reuse/current boundary:** Build the missing integration; preserve existing records.

**Steps:**
- Qualify existing-access news/event sources and terms
- Preserve original availability, source, revisions, earnings proximity and duplicates
- Keep unknown news distinct from no catalyst and compare rumor/verified information explicitly

**Deliverable:** Cited, timestamped catalyst archive and event/source model

**Accept only when:**
- D06.1: Later story revisions do not enter earlier decisions
- D06.2: Recycled stories are clustered rather than counted as multiple independent catalysts

### Account and management

#### P01 — Connect chronological comparative allocation to persisted account events

**Depends on:** T01, M01. **Authority:** research. **Owner:** assistant.

**Reuse/current boundary:** Acquisition planner, PaperLedger and portfolio_replay exist.

**Steps:**
- Compare simultaneous opportunities against shared cash and risk and retaining cash
- Persist reservations, entries, marks, unsettled proceeds, costs and equity snapshots
- Apply chronological settlement and external-flow conventions; retain censored holdings

**Deliverable:** Reconciled historical account ledger and equity/drawdown curve

**Accept only when:**
- P01.1: One dollar and one risk allowance cannot fund multiple overlapping independent cases
- P01.2: Fees, settlement and unrealized P&L reconcile; incomplete valuations prevent full-return claims
- P01.3: Later exit outcomes do not change earlier allocations

#### P02 — Compare protective stops, partial profits and trailing/time exits

**Depends on:** P01. **Authority:** research. **Owner:** assistant.

**Reuse/current boundary:** management_replay.py implements partial/trailing alternatives.

**Steps:**
- Persist original stop versus predeclared structure/ATR protection
- Compare hold, partial exit, trailing and time horizons on mutually exclusive account paths
- Include stop gaps, profit giveback, fees per exit and unresolved exits

**Deliverable:** Matched position-management account comparisons

**Accept only when:**
- P02.1: Stop adjustments use prior completed evidence and take effect prospectively
- P02.2: Partial quantities and remaining basis/risk reconcile
- P02.3: Planned-risk ceilings are not claimed as guaranteed maximum losses

#### P03 — Implement controlled additions and combined protection

**Depends on:** P02. **Authority:** research. **Owner:** assistant.

**Reuse/current boundary:** Build the missing integration; preserve existing records.

**Steps:**
- Compare no add, separately protected add, combined protection and partial-profit alternatives
- Count all additions under the same trade risk ceiling
- Track total exposure, entry-to-stop planned loss and current-value giveback separately

**Deliverable:** Addition/giveback simulator and portfolio comparisons

**Accept only when:**
- P03.1: No new 1% risk allowance is granted per addition
- P03.2: Stops are not tightened merely to permit extra shares
- P03.3: Partial/nonfilled additions and combined protection remain auditable

#### P04 — Complete exposure, overnight and daily session controls

**Depends on:** P01. **Authority:** research. **Owner:** assistant.

**Reuse/current boundary:** paper_entry_pause and cumulative risk arithmetic exist.

**Steps:**
- Implement configurable concentration/correlation and specialized-ETF eligibility without adopting unapproved limits
- Qualify overnight event/session protection and maximum holding alternatives
- Persist the agreed paper-only 3% session pause including stale-equity/restart handling

**Deliverable:** Persisted portfolio/session controller and risk-policy proposals

**Accept only when:**
- P04.1: 1% per-trade including adds and 5% aggregate ceilings remain enforced
- P04.2: Paper daily pause excludes external flows, does not liquidate, and continues scanning/protection
- P04.3: Unanswered reviews, stale marks and restart cannot silently enable new exposure

#### P05 — Stress partial execution and broker/session lifecycle

**Depends on:** P03, P04, D04. **Authority:** research. **Owner:** assistant.

**Reuse/current boundary:** Build the missing integration; preserve existing records.

**Steps:**
- Model partial/rejected/nonfilled entries and exits, halts, gaps and out-of-hours protection
- Reconcile amendments, cancellation races, remaining quantities and lost confirmations
- Qualify broker settlement and account restrictions without assuming leverage

**Deliverable:** Execution/reconciliation state machine exercised with recorded/fabricated fault cases

**Accept only when:**
- P05.1: Unknown order state is reconciled before duplicate submission or risk release
- P05.2: Protective quantity tracks actual filled exposure; insufficient evidence cannot report a closed profitable trade

### Additional intelligence

#### H10 — Implement the accepted technical variants

**Depends on:** S01, D03. **Authority:** research. **Owner:** assistant.

**Reuse/current boundary:** Build the missing integration; preserve existing records.

**Steps:**
- Freeze separate compression/expansion, ADX/directional movement, Bollinger squeeze and moving-average/momentum variants
- Implement opening-range, previous-day-high, support/resistance and trendline comparisons
- Record warm-up, thresholds and correlated feature relationships

**Deliverable:** Separate technical experiment specs, feature code and prior-only checks

**Accept only when:**
- H10.1: Every named variant has its own runnable spec or explicit evidence blocker
- H10.2: Correlated indicators do not become additive invented confidence

#### H11 — Qualify and test VWAP reclaim/retest

**Depends on:** S01, D03. **Authority:** research. **Owner:** assistant.

**Reuse/current boundary:** Build the missing integration; preserve existing records.

**Steps:**
- Resolve provider VWAP semantics versus session VWAP approximation
- Freeze reclaim/retest and extension rules
- Compare against plain price/volume controls

**Deliverable:** VWAP experiment with provenance and approximation labels

**Accept only when:**
- H11.1: Supplied per-bar VWAP is not assumed to be exact cumulative session VWAP
- H11.2: All reclaimed levels were observable before entry

#### H12 — Test relative strength, breadth and economic peer lead/lag

**Depends on:** S01, D05. **Authority:** research. **Owner:** assistant.

**Reuse/current boundary:** Build the missing integration; preserve existing records.

**Steps:**
- Implement market/sector weakness-strength comparisons and breadth participation
- Freeze peer selection and lead/lag windows before outcomes
- Compare marginal value against price-only baselines

**Deliverable:** Context-family experiments and matched ablations

**Accept only when:**
- H12.1: Dated membership and aligned benchmark evidence accompany each result
- H12.2: Missing breadth/peer evidence disables that feature only

#### H13 — Test catalyst-only, technical-only and combined cases

**Depends on:** S01, D06. **Authority:** research. **Owner:** assistant.

**Reuse/current boundary:** Build the missing integration; preserve existing records.

**Steps:**
- Freeze catalyst quality, freshness and entry confirmation rules
- Keep three distinct signal bases and their entry setups
- Evaluate new/recycled stories, earnings/gap contexts and later price response

**Deliverable:** Catalyst/news experiments with cited information snapshots

**Accept only when:**
- H13.1: Catalyst-only does not inherit a mandatory technical-momentum signal
- H13.2: Unknown news is not relabeled absent; no future news enters a recommendation

#### H14 — Test reclaim and continuation versus exhaustion

**Depends on:** S01, D03. **Authority:** research. **Owner:** assistant.

**Reuse/current boundary:** Build the missing integration; preserve existing records.

**Steps:**
- Define failed-breakdown/reclaim separately from an ordinary breakout
- Freeze persistence, extension, pullback and exhaustion labels
- Include stalled continuation, reversals and false positives

**Deliverable:** Separate reclaim/persistence strategies and matched failure cases

**Accept only when:**
- H14.1: Outcome labels do not become input features at earlier decision times
- H14.2: Continuation and exhaustion claims retain sample counts and regime/time context

#### H15 — Evaluate AI-assisted intelligence and retrieval incrementally

**Depends on:** H12, H13, H14, LLM02. **Authority:** research. **Owner:** assistant.

**Reuse/current boundary:** Build the missing integration; preserve existing records.

**Steps:**
- Implement cited document ingestion, chunk/version lineage and bounded retrieval
- Freeze model/prompt/features and latency/cost budgets
- Compare simple rules against AI-assisted decisions and remove one evidence group at a time

**Deliverable:** Operational retrieval evaluation and frozen AI ablation runs

**Accept only when:**
- H15.1: External text is data, never operational instructions
- H15.2: No uncited answer or correlated story duplication supplies invented certainty
- H15.3: AI is retained only on measured decision value with visible cost and failure evidence

### Model suitability

#### LLM01 — Define model jobs and benchmark existing-access candidates

**Depends on:** Ready to start. **Authority:** research. **Owner:** assistant.

**Reuse/current boundary:** App/research code has no production LLM API client or model routing.

**Steps:**
- Inventory actual configured model access without exposing credentials
- Keep scanning math, sizing, risk, cash, order state and replay in deterministic code
- Define labeled news extraction/deduplication, catalyst reasoning, retrieval and user-explanation tasks
- Benchmark suitable existing-access candidates on task accuracy, grounding, structured output, failure behavior, latency and full cost

**Deliverable:** Model/job matrix and reproducible task-specific evaluation set

**Accept only when:**
- LLM01.1: No model is called best or suitable merely because it is newer, larger or used in this chat
- LLM01.2: Candidate access, current price, licensing, privacy and runtime support are verified before adoption
- LLM01.3: Model calls cannot set prices/risk limits, approve orders or turn external text into instructions

#### LLM02 — Implement evidence-backed routing, budgets and model provenance

**Depends on:** LLM01. **Authority:** research. **Owner:** assistant.

**Reuse/current boundary:** Research schema has document/retrieval/learning records; operating routing is not built.

**Steps:**
- Select a task-suitable lower-cost model only where quality meets predeclared requirements; escalate ambiguous cases explicitly
- Use a stronger reasoning model for tasks where measured improvement justifies cost/latency; evaluate embeddings separately
- Persist model/provider, prompt/schema version, input sources, output, latency, cost and fallback reason
- Enforce monthly budget, caching, timeouts and safe unavailable/degraded behavior

**Deliverable:** Server-side model registry/router with measured job assignments and audit records

**Accept only when:**
- LLM02.1: A cheap model cannot silently replace a failed critical reasoning result without qualification
- LLM02.2: No credential/private data enters client code or unnecessary provider calls
- LLM02.3: Actual incremental decision value is tested against the deterministic baseline; model changes need versioned evaluation

### Historical evaluation

#### V01 — Run the broader frozen experiment matrix

**Depends on:** T03, D02, D03, P02. **Authority:** research. **Owner:** assistant.

**Reuse/current boundary:** Build the missing integration; preserve existing records.

**Steps:**
- Execute supported families on development data with negative/no-entry and failure records
- Run horizon/cost/delay sensitivities and independent session/opportunity clustering
- Match cash and same-window benchmarks, capital occupancy and losses/tails

**Deliverable:** Reproducible full historical matrix with declared evidence scope

**Accept only when:**
- V01.1: Report expectancy, realized/unrealized equity, drawdown, tail losses, costs, exposure and uncertainty on valid denominators
- V01.2: Dependent scenarios are alternatives; no summing independent case returns into account ROI
- V01.3: Unsupported additional families stay pending and visible rather than being silently dropped

#### V02 — Freeze candidates and evaluate later unseen evidence

**Depends on:** V01. **Authority:** research. **Owner:** assistant.

**Reuse/current boundary:** Build the missing integration; preserve existing records.

**Steps:**
- Preserve all selection/tuning history and candidate hashes
- Register evaluation windows, comparison metrics and proposed pass/fail criteria before opening results
- Run matched later evaluation; retain failures and explain extensions

**Deliverable:** Audited held-out evaluation and explicit candidate decision

**Accept only when:**
- V02.1: Development tuning cannot see held-out outcomes
- V02.2: No statistical or profitability pass is fabricated when evidence is insufficient
- V02.3: Negative results can complete a valid experiment without marking a strategy effective

### Usable product

#### U01 — Connect authenticated application APIs to authoritative records

**Depends on:** DB01. **Authority:** research. **Owner:** assistant.

**Reuse/current boundary:** Password-protected Render app and GET-only broker data exist.

**Steps:**
- Configure least-privilege server access to the designated hosted database
- Implement bounded queries for runs, opportunities, decisions, accounts and health
- Separate historical, ghost, broker-paper and actual account observations in every response

**Deliverable:** Persistent private API with server-only credentials and provenance

**Accept only when:**
- U01.1: Restart does not lose decision/account state
- U01.2: Unauthorized reads/writes fail and no secret reaches browser code
- U01.3: Missing or stale fields are unavailable, not synthetic zeros

#### U02 — Present the first historical report in the dashboard

**Depends on:** T02, U01. **Authority:** research. **Owner:** assistant.

**Reuse/current boundary:** Build the missing integration; preserve existing records.

**Steps:**
- Show experiment selection, buy/sell examples and gain/loss in plain language
- Explain position/cash histories, realized versus unrealized and return denominators
- Show data quality and exact modeled/observed labels without technical homework

**Deliverable:** Working historical-results screen backed by stored records

**Accept only when:**
- U02.1: Screen numbers reconcile to selected run/fills/account ledger
- U02.2: Synthetic demonstrations are isolated from actual account and historical results
- U02.3: Desktop and phone workflows are readable and bounded in response time

#### U03 — Implement shared review, modify, wait, deny, expiry and feedback

**Depends on:** U01, P04. **Authority:** research. **Owner:** assistant.

**Reuse/current boundary:** Build the missing integration; preserve existing records.

**Steps:**
- Store original and revised recommendation terms with opportunity identity
- Recalculate size, price validity, fees and risk after every edit
- Require explicit final approval for any authorized order path; retain denial/no response/expiry
- Implement recommendation feedback and distinct preference proposal review

**Deliverable:** Authenticated dashboard actions and immutable shared decision history

**Accept only when:**
- U03.1: Modify alone does not approve; stale/changed/duplicate terms cannot authorize execution
- U03.2: A feedback click cannot change a standing preference or active protective order
- U03.3: Existing trading authority remains disabled

#### U04 — Expose comparative opportunity and position guidance clearly

**Depends on:** U02, U03, P02. **Authority:** research. **Owner:** assistant.

**Reuse/current boundary:** Build the missing integration; preserve existing records.

**Steps:**
- Show where/when/price/scale, competing uses of capital and reasons to retain cash
- Display current stop coverage, unrealized giveback, holding risks and next review
- Add simple pause/resume, settings, source freshness and failure explanations

**Deliverable:** Integrated decision dashboard and conversational explanation endpoint

**Accept only when:**
- U04.1: Ranking shows conditional estimates and evidence quality without invented expected ROI
- U04.2: Account, recommendation and historical screens use the same reconciled records
- U04.3: User can understand the proposed action and consequence without interpreting test counts

### Proactive operation

#### A01 — Run incremental continuous qualified discovery

**Depends on:** H01, H02, H03, U01, D01. **Authority:** research. **Owner:** assistant.

**Reuse/current boundary:** Build the missing integration; preserve existing records.

**Steps:**
- Maintain completed-bar checkpoints and incremental baselines
- Scan regular sessions continuously across declared coverage; qualify extended-hours eligibility separately
- Recover missed windows on restart without future information or duplicate opportunities

**Deliverable:** Hosted scanner with durable checkpoints, coverage and latency metrics

**Accept only when:**
- A01.1: A laptop shutdown does not stop intended hosted work
- A01.2: Every qualifying distinct recommendation is retained/delivered; updates are labeled rather than silently suppressing opportunities
- A01.3: Stale/partial feeds cannot create fresh executable recommendations

#### A02 — Deliver notifications and shared Telegram reviews

**Depends on:** A01, U03. **Authority:** research. **Owner:** assistant.

**Reuse/current boundary:** Build the missing integration; preserve existing records.

**Steps:**
- Connect the chosen notification channel with account-bound authorization
- Deliver recommendations, updates, expiry and failure notices with deduplication/retries
- Route dashboard and Telegram actions through one decision authority

**Deliverable:** Reliable notification delivery and review workflows

**Accept only when:**
- A02.1: Repeated delivery/clicks cannot duplicate decisions or authorize different terms
- A02.2: Delivery failure has visible retries/escalation and does not become user denial
- A02.3: Existing positions retain monitoring/protection while new exposure is paused

#### A03 — Monitor open exposure and event/session risk

**Depends on:** A01, P04, P05, U04. **Authority:** research. **Owner:** assistant.

**Reuse/current boundary:** Build the missing integration; preserve existing records.

**Steps:**
- Continuously reconcile account/position/protection observations
- Produce stop, profit-taking, addition and overnight reviews from current evidence
- Handle stale quotes, missed sessions and absent responses using explicit configured behavior

**Deliverable:** Persistent proactive position-management service in ghost mode

**Accept only when:**
- A03.1: No unapproved stop widening, addition or liquidation
- A03.2: Current account risk and guidance reconcile to persisted fills and protection state

#### A04 — Qualify deployment, recovery, security and operating costs

**Depends on:** U01, A01. **Authority:** research. **Owner:** assistant.

**Reuse/current boundary:** Build the missing integration; preserve existing records.

**Steps:**
- Add measured health/freshness/latency objectives, structured job attempts and cost tracking
- Test restart, provider outage, backups/restore, migration recovery, rollback and secret handling
- Verify always-on needs versus current free-service sleep within $25/month; propose any paid change explicitly

**Deliverable:** Recovery runbook, measured service qualification and release pipeline

**Accept only when:**
- A04.1: Restored state reproduces last completed research/account checkpoint without duplicate work
- A04.2: Runtime logs contain no credentials or private payloads
- A04.3: CI/build/hosted behavior match the exact released revision; no paid resource is silently added

### Learning and tuning

#### L01 — Persist complete decision and matched alternative outcomes

**Depends on:** P01, U03. **Authority:** research. **Owner:** assistant.

**Reuse/current boundary:** Build the missing integration; preserve existing records.

**Steps:**
- Store accept/modify/deny/no-response and recommendation baseline alternatives
- Link selection, timing, execution and management effects to exact versions
- Preserve negative trials, missing outcomes and rejected feedback

**Deliverable:** Queryable learning evidence with complete opportunity/decision lineage

**Accept only when:**
- L01.1: Preference fit is evaluated separately from predictive return
- L01.2: Unanswered/declined cases are not inferred losses or preferences
- L01.3: Learned evidence reconciles to the original run and user terms

#### L02 — Operate comparison, drift and improvement jobs

**Depends on:** L01, V02, H15. **Authority:** research. **Owner:** assistant.

**Reuse/current boundary:** Build the missing integration; preserve existing records.

**Steps:**
- Run bounded scheduled comparisons and drift checks with durable job records
- Generate evidence-backed candidate proposals and cost/quality changes
- Require independent matched evaluation and retain failed proposals

**Deliverable:** Operating learning/evaluation jobs and visible proposal history

**Accept only when:**
- L02.1: Schema triggers are exercised through actual writer/job workflows
- L02.2: A backtest pass cannot auto-promote a strategy or rewrite historical decisions
- L02.3: Retrieval/model/prompt changes retain versions and incremental-value evidence

#### L03 — Implement approved preference and strategy adoption

**Depends on:** L02, U03. **Authority:** research. **Owner:** assistant.

**Reuse/current boundary:** Build the missing integration; preserve existing records.

**Steps:**
- Show proposal evidence, exact revised terms and approve/modify/deny
- Keep pending/denied/unanswered proposals inactive
- Version adoption, effective time, rollback and impact monitoring

**Deliverable:** Controlled preference/strategy adoption workflow

**Accept only when:**
- L03.1: Risk limits and active protection cannot change under a preference approval
- L03.2: Approval binds final reviewed content and cannot be replayed against another version

### Forward paper readiness

#### Q01 — Run historical end-to-end reconciliation and release review

**Depends on:** V02, P03, P05, U04, A02, A03, A04, L01. **Authority:** research. **Owner:** assistant.

**Reuse/current boundary:** Build the missing integration; preserve existing records.

**Steps:**
- Replay discovery through comparison, review, modeled fills, account, management, reporting and learning records
- Inject lost messages, stale quotes, failed writes, missing bars and restarts
- Review final proposed operating settings and unresolved O01-O11 items

**Deliverable:** Evidence-backed readiness dossier and exact proposed paper configuration

**Accept only when:**
- Q01.1: Same settings/data reconcile across API, UI, DB and reports
- Q01.2: Every proposed active capability has evidence, and disabled/pending research families are visible
- Q01.3: Outstanding choices identify a concrete consequence and do not restart settled Discovery

#### Q02 — Execute hosted forward ghost evaluation

**Depends on:** Q01. **Authority:** research. **Owner:** assistant.

**Reuse/current boundary:** Build the missing integration; preserve existing records.

**Steps:**
- Freeze candidate rules and collect subsequent recommendations with simulated decisions/fills
- Evaluate approximately one month as intended, extending where independent evidence is inadequate
- Compare costs, drawdown, misses, paper pauses, timeliness and user usability with predeclared criteria

**Deliverable:** Forward ghost record and paper-readiness evaluation

**Accept only when:**
- Q02.1: Later evidence was genuinely unseen when each recommendation was made
- Q02.2: Calendar duration alone cannot manufacture sufficient sample or profitability
- Q02.3: Results identify proceed/revise/stop with reasons; no actual order transport is activated

### Optional broker paper

#### B01 — Review exact broker-paper order authority and configuration

**Depends on:** Q01. **Authority:** separate_order_authorization. **Owner:** assistant.

**Reuse/current boundary:** Build the missing integration; preserve existing records.

**Steps:**
- Present designated sandbox environment, enabled order types, protection, limits and fail-safe actions
- Obtain separate explicit authorization before creating broker paper orders
- Keep this branch disabled while internal ghost evaluation proceeds

**Deliverable:** Specific broker-paper authorization record or explicit disabled status

**Accept only when:**
- B01.1: Existing account/data access and prior go messages are not silently upgraded to order-submission authority

#### B02 — Implement and verify isolated broker-paper execution

**Depends on:** B01, P05, U03, A04. **Authority:** separate_order_authorization. **Owner:** assistant.

**Reuse/current boundary:** Build the missing integration; preserve existing records.

**Steps:**
- Implement sandbox-only adapter with environment pinning and idempotent approved intents
- Reconcile paper order lifecycle, fills, partials, stops and amendments
- Prevent production endpoints and credentials from entering sandbox execution

**Deliverable:** Authorized sandbox integration and broker-observed forward paper run

**Accept only when:**
- B02.1: Fault tests cannot submit a production order
- B02.2: Every paper order has specific authorization and reconciled broker state
- B02.3: Sandbox fills remain distinct from historical modeled fills

### Future live release

#### LIVE01 — Prepare live-release proposal without enabling trading

**Depends on:** Q02, L03. **Authority:** research. **Owner:** assistant.

**Reuse/current boundary:** Build the missing integration; preserve existing records.

**Steps:**
- Reconcile historical, forward ghost and any authorized broker-paper evidence
- Present unresolved live daily-loss, exposure, instrument and protection choices with concrete proposed terms
- Assess broker eligibility, outage/overnight protection, costs and rollback

**Deliverable:** Concrete reviewable live-release proposal with all remaining gates

**Accept only when:**
- LIVE01.1: Research/paper settings are not automatically adopted as live settings
- LIVE01.2: No funding, purchase, production order or automatic strategy adoption occurs

#### LIVE02 — Obtain explicit live-trading and funding decisions

**Depends on:** LIVE01. **Authority:** separate_live_authorization. **Owner:** assistant.

**Reuse/current boundary:** Build the missing integration; preserve existing records.

**Steps:**
- Ask for specific final production order scope only after the proposal is complete
- Treat funding/purchases as separately authorized actions
- Keep production submission disabled until the exact authorization and risk terms are recorded

**Deliverable:** Explicit live-release decision or retained disabled state

**Accept only when:**
- LIVE02.1: No test, plan status or approval file substitutes for actual explicit user authorization

#### LIVE03 — Release authorized production execution and monitor

**Depends on:** LIVE02, B02, A04. **Authority:** separate_live_authorization. **Owner:** assistant.

**Reuse/current boundary:** Build the missing integration; preserve existing records.

**Steps:**
- Only within separately authorized scope, configure isolated production execution and reconciliation
- Verify initial protection, recovery, alerts and exact limits before release
- Monitor agreed risk/performance/drift and preserve pause/rollback authority

**Deliverable:** Separately authorized production release with operating evidence

**Accept only when:**
- LIVE03.1: Production remains inaccessible when authorization, entitlement, freshness or reconciliation fails
- LIVE03.2: Live outcomes remain distinct from modeled/paper outcomes

## Accepted-scope coverage

All 56 accepted/context items A01–A55 plus A06a, all O01–O11 decisions and all 18 current hypothesis families are mapped in EXECUTION_PLAN.json. Validation fails if any mapping is missing or references an unknown task. The catalog preserves the technical subfamilies, catalysts, market context, management, execution, allocation and learning; it does not redefine the platform as only quiet-to-active detection.

## Meaning of complete

The delivery plan can be complete while many tasks remain pending. A valid experiment can finish with no edge, negative returns or insufficient evidence. A hosted application can function while a strategy fails. Operating ghost readiness, candidate effectiveness, broker-paper authority and live authority remain separate gates. No execution-plan receipt establishes future ROI.
