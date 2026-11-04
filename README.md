# VisionAIry Trader

Personal momentum research and ghost-trading platform.

**Status:** research prototype with a deployed password-protected mechanics dashboard at https://visionairy-trader-research.onrender.com. It displays synthetic account/management experiments only. The preserved pilot remains private in Supabase. No live trading, hosted market scanner, Telegram application or demonstrated profitable strategy is running.

## Architecture

- **Render:** intended application, scanner, replay and notification runtime.
- **Supabase:** intended authoritative Postgres records and private historical archives.
- **SQLite:** existing local research store used to validate ingestion and replay; not the selected final hosted database.

Supabase project details are supplied through environment configuration; credentials and deployment-specific identifiers are not committed.

## Implemented

- GET-only Tradier historical-data retrieval; redirects rejected, credentials not persisted.
- Historical bar validation and UTC timestamp normalization checks.
- Initial price/relative-activity benchmark replay and sensitivity scenarios.
- Deduplicated, versioned SQLite research data, run lineage and consistent snapshots.
- Cost/sizing arithmetic preflight.
- 175 research/replay/storage/import/selection/decision/UI checks and 7 sizing checks.
- Nonblocking account refresh with stale-number suppression, request timing and on-demand demo computation; free-host wake-up remains a separate limitation.
- Measured hypothesis/data readiness: see docs/HYPOTHESIS_READINESS.md. The five-symbol captured archive supports diagnostics, not representative strategy validation.
- Authenticated Tradier account-data endpoint with pinned read-only GET routes. Requires a securely configured environment/token before any real account connection is claimed; unavailable values remain null, and measured account return stays unavailable without a reconciled baseline and cash flows.
- Comparative acquisition research with conditional ROI/risk metrics and shared cash/risk reservations; see docs/ACQUISITION_FUNNEL.md.
- Allocation-bound outcome replay preserves selection, quantity, cash, risk, costs and price ceilings; independent controls remain separate from portfolio returns.
- Optional joint paper-account experiments track reservations, positions, marks, partial exits, session settlement and daily pause. Management alternatives are not independent trades or adopted rules.
- Password-protected read-only mechanics dashboard: `python app/server.py`; configure `DASHBOARD_USERNAME` and `DASHBOARD_PASSWORD_SHA256` through the runtime environment. No private data or broker credentials are needed for its synthetic walkthrough.
- Intent-linked quiet-to-active research selector and coverage gates; numerical settings remain experimental.
- Private research, learning and retrieval schema with 32 database acceptance checks.
- Resumable typed imports with conflict detection and whole-table reconciliation before completion.

The earlier pilot covered three convenience-sample stocks. Its standing as evidence for the intended quiet-to-active strategy is withdrawn. It remains an infrastructure control only. See docs/INTENT_REQUIREMENTS.md for the correction and measured fit failure. A corrected representative strategy study has not yet run.

## Run checks

Python 3.11+; standard library only. Tkinter is optional for the local credential form.

```powershell
python -m unittest discover -s research -p "test_*.py" -v
python -m unittest discover -s sizing -p "test_*.py" -v
```

Acquisition and replay commands currently run from the `research` directory. See its README and `docs/STATUS.md`.

## Data and credentials

Market datasets, databases, results, backups and local environments are excluded from Git.
Use environment variables or service secret settings. Do not commit credentials or place them in issue bodies.
The sample environment file has variable names only; a publishable key is not an administrative/server credential.
No production-order API methods are implemented.

## Purpose and connected research

See [PURPOSE_ALIGNMENT.md](docs/PURPOSE_ALIGNMENT.md) for all accepted SOT items, [DECISION_MODEL.md](docs/DECISION_MODEL.md) for decision/outcome connections, and [INTENT_REQUIREMENTS.md](docs/INTENT_REQUIREMENTS.md) for cohort acceptance. Run `python research/purpose_runner.py --bundle YOUR_PRIVATE_BUNDLE.json --output data/purpose_result.json` with explicit source/clock/policy evidence. It does not acquire data or submit orders. Conditional research output cannot claim an operating assistant or validated trading edge.

## Next delivery stages

1. Establish representative discovery coverage and prior baselines.
2. Expand trigger, stop/exit, sizing and portfolio simulation with preserved trial history.
3. Connect operational document ingestion, retrieval and learning evaluation; schema support alone is not a running learning system.
4. Build and verify the private application and Render deployment.
5. Freeze hypotheses and run forward ghost validation.

All experiments use simulated capital. Any eventual live release requires separate explicit authorization and the retained approval/audit workflow.

No open-source license grant has been made.


## Preserved-archive control diagnostic

Run `python research/archive_diagnostic.py --database data/original/research_snapshot.sqlite --start 1792540800 --end 1793750400 --output data/archive_diagnostic.json` from the workspace root. It opens the existing private archive read-only, pins source/code/policy evidence, deduplicates repeated imports and retains failed/blocked completed-bar decisions. It does not infer a qualified historical universe, executable prices, target forecasts or returns. See `docs/HYPOTHESIS_READINESS.md` for the observed limits and remaining evaluation requirements. Current verification: 182 research/UI checks and 7 sizing checks.

## Existing-access historical collection

Authenticated `/api/history` and `/api/calendar` expose only bounded server-side research GETs; the production token remains in Render secrets. `research/history_collection.py` freezes a price-blind directory coverage sample; `research/collect_history.mjs` exports a bounded, resumable `collect(workspaceRoot, batchLimit)` using the existing private dashboard access file. `research/collection_diagnostic.py` preserves failures/gaps and uses explicit expected calendar sessions. Captures/results remain excluded under `data/`; they do not establish historical membership, execution prices or profitable returns. Current verification: 197 research/UI + 7 sizing = 204 software checks. See docs/HYPOTHESIS_READINESS.md for reproduction and actual evidence limits.
