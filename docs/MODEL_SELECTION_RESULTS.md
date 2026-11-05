# Model selection results — 2026-11-05

The completed XFMS comparisons support the following assignments for the momentum assistant's next research/ghost integration. A bounded synthetic ghost-assessment route is now deployed; see MODEL_RUNTIME.md and MODEL_RUNTIME_VERIFICATION.md. Continuous live discovery and current-market buy recommendations remain unconnected.

| Job | Primary model | Fallback | Prepared cases passed | Rounded mean model-call cost | Median time to first output |
|---|---|---|---|---|---|
| Source-grounded news extraction | `inclusionai/ling-3.1-flash` | None qualified on this suite | 6/6 | $0.0005 | 26.27 seconds |
| Statistical/trading research | `nvidia/nemotron-3.5-lightning` | `inclusionai/ling-3.1-flash` | 17/17 | $0.0003 | 5.33 seconds |

These are single-run XFMS automated grades on small prepared suites, including one actual project-record summary and historical announcement summaries alongside fictional cases. Expected-answer hints were removed before these completed runs. They do not establish general statistical expertise, independent accuracy, profitable strategies, production operating costs or end-to-end latency. All mandatory behavior checks passed on every listed case; the research fallback also passed 17/17. First-output timing is not full-response timing. Approximate per-1,000 costs on similar inputs are $0.50 for news and $0.30 for the research primary; production context length, reasoning tokens, providers, retries and workload can change those figures.

XFMS ranked Mercury 2.5 first for news despite an empty answer on one case: its reported perfect score covered only 5/5 answered cases. The project's local coverage gate rejects this incomplete result. The OpenRouter catalogue retrieved on this date also lists Mercury 2.5 expiration as 2026-11-08. It is not selected. It also had an unresolved fact-check failure in the research report. Nemotron 3.5 Lightning failed news checks and is selected only for research.

## Diagnosis and repair

The original paid news call lost its report when the tool transport timed out at 300 seconds. The successful replacement took about 323 seconds, demonstrating that a valid batch can exceed that tool lifetime. The client now starts the HTTP request inside a persistent Node host, returns immediately and polls through short calls; the final raw reply is saved before decoding. It never automatically retries an uncertain paid request. A separate report-review gate requires complete passing evidence and rejects dropped tasks. Four focused checks pass with `node --test app/xfms_runner.test.mjs`.

The inspected XFMS engine runs up to six candidate calls concurrently inside a case, grades that case, then proceeds to the next case sequentially. Calls can retry up to three total attempts. Thus a 17-case comparison is much larger and slower than one routine analysis. The repair preserves results but does not accelerate server execution or add durable server jobs and per-case progress. The current hosted revision was not independently matched to the inspected repository commit.

## Spending and remaining work

The replacement news comparison reports $0.1201; research reports $0.3267; completed reports total $0.4468. The original news attempt's completion/charges remain unresolved, with its quoted maximum $0.4041 still reserved. Reported completed spend plus that reserve is $0.8509 against the user's $2 combined benchmark authorization. This is not reconciled billing. Runtime model calls incur their own usage charges; routine analysis must not repeat the full qualification benchmark.

The subsequent bounded synthetic integration records provider/model/prompt versions, source-linked claims, immutable engine terms, latency/cost receipts and safe failure handling. See MODEL_RUNTIME_VERIFICATION.md for actual results and remaining limits. Live feeds/scanning, independently qualified retrieval and learning, and incremental trading value remain unfinished. No new fallback qualification or recurring benchmark spend is implied.
