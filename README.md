# VisionAIry Trader

Personal momentum research and ghost-trading platform.

**Status:** research prototype. No live trading, hosted scanner, Render deployment or Supabase data migration is active.

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
- 30 research/replay/storage checks and 7 sizing checks.

The completed pilot covered three convenience-sample stocks. It is not broad-market validation, a complete 32-variant implementation, or proof of profitability.

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

## Next delivery stages

1. Prepare Supabase schema, permissions and migration/import validation.
2. Establish representative discovery coverage, prior baselines and timestamp consistency.
3. Expand trigger, stop/exit, sizing and portfolio simulation with preserved trial history.
4. Build and verify the private application and Render deployment.
5. Freeze hypotheses and run forward ghost validation.

All experiments use simulated capital. Any eventual live release requires separate explicit authorization and the retained approval/audit workflow.

No open-source license grant has been made.

