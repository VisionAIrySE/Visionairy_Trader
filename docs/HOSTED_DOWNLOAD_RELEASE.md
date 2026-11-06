# Hosted historical download release

Status: worker and authenticated progress-page implementation candidate; NOT deployed or downloading.

Purpose: keep historical collection running without a ChatGPT session, an open browser, or Russ's computer. Render executes the worker; the existing Supabase database preserves the queue, captured pages and progress.

## Concrete deployment

- Repository: VisionAIrySE/Visionairy_Trader.
- New service: visionairy-trader-history, background worker, Oregon, one instance.
- Compute: 0.5c-512mb (legacy Starter), published $7/month while provisioned. No new database or Redis service requested. Existing data/storage usage remains subject to provider allowances.
- Build: `pip install -r research/requirements-worker.txt && python -m unittest discover -s research -p test_durable_history_worker.py`.
- Start: `python research/durable_history_worker.py`.
- Server secrets: HISTORY_DATABASE_URL, ALPACA_API_KEY, ALPACA_API_SECRET. Never expose them to the browser or commit them.
- Import the private frozen full-session plan with `python research/enqueue_holdout.py data/momentum_study/holdout_v1/full_sessions/plan.json` in an authorized environment with the database secret. 147 batches cover all 2,345 signals.

## Behavior implemented

Each successful page and its next-page checkpoint commit together. A crash before commit leaves the page eligible for retrieval again. An expiring lease and token prevent a superseded worker from advancing the job. Temporary network errors, HTTP429 and server failures back off, with eight consecutive failures stopping that batch for review. Authentication/invalid-response errors stop immediately. Empty successful responses are preserved. Only fixed-host GET historical-bar requests are supported; there is no order submission.

## Release gates still required

1. Approve the new recurring $7/month compute charge; project rules prohibit an unapproved paid resource.
2. Publish candidate code, provision worker and configure secrets securely.
3. Verify actual database transactions, duplicate import, concurrent claims, expired lease recovery and restart after a saved page; local unit tests do not establish these integration guarantees.
4. Import frozen plan and confirm real saved pages before declaring collection running.
5. Deploy the implemented authenticated /downloads page and /api/download-status readout, with its additive assessment-store status operation. Verify it against the running worker; the candidate UI is not live yet.
6. Confirm work continues after closing chat and survives a deliberate worker restart. No live-trading changes.

No claim of operational reliability until these gates pass. Pricing verified against Render's official pricing and compute-plan references on November6,2026.

Validation: eight worker unit checks pass; JavaScript syntax passes; the research suite reports295 passed and one pre-existing generated execution-plan document mismatch (unrelated to this change). A rollback-only hosted database check verified that a superseded lease token cannot complete a reclaimed job. Full worker/database restart and network integration remain deployment checks.
