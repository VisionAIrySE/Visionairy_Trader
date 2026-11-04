# VisionAIry Trader

Personal momentum research and ghost-trading platform.

**Status:** research prototype. The preserved pilot is imported and verified in private Supabase storage. No live trading, hosted scanner, Telegram application, dashboard or Render deployment is running.

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
- 70 research/replay/storage/import/selection checks and 7 sizing checks.
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

## Next delivery stages

1. Establish representative discovery coverage and prior baselines.
2. Expand trigger, stop/exit, sizing and portfolio simulation with preserved trial history.
3. Connect operational document ingestion, retrieval and learning evaluation; schema support alone is not a running learning system.
4. Build and verify the private application and Render deployment.
5. Freeze hypotheses and run forward ghost validation.

All experiments use simulated capital. Any eventual live release requires separate explicit authorization and the retained approval/audit workflow.

No open-source license grant has been made.

