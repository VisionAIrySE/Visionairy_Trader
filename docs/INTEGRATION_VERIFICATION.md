# Research integration verification

Verified November 3, 2026, Pacific time. Data foundation complete; trading application unfinished.

Correction: this document establishes transfer integrity only. The imported convenience pilot is withdrawn as evidence for the intended quiet-to-active strategy. Selection repair and measured scope failure appear in INTENT_REQUIREMENTS.md; no replacement strategy result is claimed.

## What was completed

Recovered the existing source into the VDT workspace without changing the originals. Regenerated the import from the preserved integrity-checked SQLite snapshot and original Decimal-string outcomes. Finished the interrupted import without deleting or resetting database records.

All 15 imported tables match expected counts and ordered checksums over their typed fields, including exact numeric values, UTC timestamps, JSON evidence, identifiers and source relationships. Row-level comparisons reject conflicting payloads rather than treating every conflict as successful. Repeated imports skip existing identities before completed-run triggers; duplicates are not added.

Finalization locks all imported tables in one transaction, recomputes every checksum, verifies each source's link count, checks instrument/interval consistency and rejects observations without provenance. Only then does it freeze the dataset and complete the exploration run. Lifecycle states are checked separately from content hashes.

The checksums use deterministic MD5 fingerprints for accidental transfer-corruption detection, not adversarial authenticity or security signatures. Original source SHA-256 identities remain preserved. Private import payloads and original datasets stay out of the public repository.

## Tests and measured performance

- 54 local automated tests passed: 47 research/import checks and 7 sizing checks.
- 21 general database acceptance checks and 11 learning acceptance checks passed. Synthetic database fixtures rolled back.
- Source SQLite snapshot: integrity check OK, no foreign-key violations.
- All 48 trader tables have RLS; security advisor returned no findings.
- Indexed AAPL one-session query: 390 rows, 0.366 ms server execution on one cached run; planning 0.495 ms. Network, UI, sustained load and whole-market scanning are unmeasured.
- Trader table/index allocation: 27,992,064 bytes, approximately 26.7 MiB. Not a storage-growth forecast or whole-project bill.

Performance notices: 56 currently unused indexes and an existing fixed 10-connection Auth allocation. Those are informational. The application has not run a representative workload, so removing integrity/FK indexes based on startup statistics would be premature. Reassess connection allocation before resizing. References: [unused index notice](https://supabase.com/docs/guides/database/database-linter?lint=0005_unused_index), [production preparation](https://supabase.com/docs/guides/deployment/going-into-prod).

## Improvements implemented during recovery

- Exact conflict detection and deterministic retry identities.
- Lower-volume dictionary-encoded import transport; decoded records receive the same typed comparisons.
- Whole-table reconciliation without retransmitting the entire dataset.
- Atomic completion that refuses incomplete or changed evidence.
- Completion records distinguishing installed schema, imported research, operational features and strategy evidence.

## Highest-value next improvements

1. Cover representative symbols, sessions and market conditions, with point-in-time membership, corporate-action checks, missing-data coverage and quiet/failed cases. Current sample size is the primary evidence limitation.
2. Evaluate realistic portfolios and management: bid/ask or disclosed conservative fill assumptions, approval latency, partial/nonfills, stops, gaps, overnight risk, settlement and costs. Standalone hypothetical orders cannot establish account performance.
3. Freeze experiments before evaluation on later unseen data; count clustered events and sessions, report uncertainty and drawdowns, and compare against simple rules and same-window benchmarks. Set release thresholds explicitly.
4. For runtime speed, maintain incremental completed bars and prior-only volume baselines, cache summaries, and use bounded indexed reads. Measure scanner-to-notification latency under representative load before adding indexes, partitions or vector ANN search.
5. Connect source-cited document ingestion and retrieval only with measured incremental value and cost. Add durable scanner checkpoints, deduplicated notification delivery, health alerts, cost accounting and tested hosted restore before unattended use.

These are implementation priorities and proposed acceptance work, not new trading parameters or evidence that a strategy is profitable.

## Publication

Thirty reviewed code/document files form the source publication, with no credential or deployment-project-reference matches in the scan. Credentials, market datasets and private import payloads are excluded. Local test results and subsequent GitHub Actions results are verified separately. Publishing source does not deploy an application or enable trading.
