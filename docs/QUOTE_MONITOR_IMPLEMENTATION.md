# Broad quote monitor implementation

The private dashboard provides authenticated start, status and stop controls for one bounded read-only quote sweep. Collection runs in a background thread; status requests do not wait for the sweep. Duplicate starts are guarded locally and by a database lease.

The monitor reads a versioned exchange-directory universe without filtering by account cash or earlier winners. A missing, future or stale directory capture cannot be assumed current. Daily directory refresh is implemented: explicit coverage tests fetch both pinned official sources, and scheduled open-market scans refresh a stale saved list. Source dates must match the market session; malformed, oversized and unexpectedly small files fail without replacing the saved universe. Closed scheduled scans do not download new directories.

Tradier bulk market-quotes requests are pinned to the documented read-only endpoint, with at most 500 explicit symbols per request. The application has no generic broker POST transport or order submission endpoint. Missing symbols, invalid numeric/timestamp evidence and unsupported mappings are tracked separately. Security names indicating warrants, rights, units, notes, debentures or preferred instruments are considered before ordinary-share wording; ETF subtypes remain pending.

Each cycle checkpoints batch counts and records its market clock. Only complete normalized state replaces the operational comparison baseline. Partial, failed and cancelled cycles retain their evidence without overwriting the last complete baseline. The checkpoint store retains immutable cycle summaries, coarse-trigger before/after evidence, issues and source hashes; the operational baseline rotates. This is not a complete historical tick archive.

The experimental detector compares quote price and reported cumulative volume between observations. It is a coarse research lead, not a completed-bar breakout, time-of-day relative volume, executable quote or qualified buy recommendation. Regular-session freshness is distinct from quote availability. Closed-market coverage does not establish a valid no-opportunity interval.

Continuous collection requires both explicit configuration guards. They default off. The proposed sweep interval is a research configuration, not a validated low-latency strategy specification. Always-on hosting, complete strategy/bar baselines, current source-grounded news, comparative risk/capital decisions and notification delivery remain separate operating requirements. No new paid hosting or data plan is implicitly authorized.

Verification covers timestamp and numeric rejection, instrument distinctions, closed-market behavior, stale directory refusal, durable partial-cycle preservation, bounded private HTTP controls and cancellation. Operational receipts and production measurements are retained privately rather than included in this public implementation note.

A running scan exposes its latest batch-checkpoint timestamp. After thirty seconds without a new checkpoint, the dashboard displays the elapsed gap and retains the stop control. Worker preparation failures are displayed alongside the preceding saved cycle, rather than making that older result appear to be a successful new run. Preflight worker status is currently process-local; completed scan receipts and batch progress use durable storage.
