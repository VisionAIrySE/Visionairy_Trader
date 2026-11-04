# Hosting and persistence

Render is the application runtime. A free password-protected research preview is deployed at https://visionairy-trader-research.onrender.com; it computes a synthetic mechanics demonstration and is not an always-on market scanner. Supabase remains the intended authoritative hosted data store. No private database or broker credentials are connected to the preview.

Structured Postgres records should hold sources/dataset versions, runs, signals, experiment parameters, simulated outcomes, summaries, approvals and audit records. Private object storage should hold compressed original datasets and older archives where cost/licensing allow.

The local SQLite research adapter is implemented and independently recoverable. It must be migrated through explicit mapping and count/checksum verification; do not imply it is already synced to Supabase.

Market timestamps use canonical UTC milliseconds in storage. Observed Tradier bars supplied epoch seconds and New York label strings; tick samples supplied milliseconds and UTC strings. Preserve source conventions and completed-bar availability.

Bounded batches, suitable time indexes, shared scenario records and cached aggregates avoid reading the entire history for each dashboard request. Performance and retention require representative load/storage measurements. A three-month research window is a proposal, not a fully populated dataset or enforced deletion rule.

Current research uses standard-library Decimal arithmetic for prices/costs. Summary numeric columns are not order-pricing inputs.

No production-order adapter, live strategy release or automatic live parameter changes are authorized.

