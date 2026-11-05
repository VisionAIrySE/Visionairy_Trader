# Failed-history recovery

## Verified resolution

The download is recovered. The saved directory identifies PSA-K as Public Storage's Series K 4.75% cumulative preferred depositary shares. Tradier lookup for PSA returned the exact same description and exchange under **PSA'K**. This verifies a provider-symbol mapping, not a substitution with common stock. A company-name lookup returned no securities; an issuer-symbol lookup supplied the identity evidence.

The deployed diagnostic revealed that the original symbol receives upstream HTTP 400, a permanent request failure that was previously hidden inside an application 502. Correcting the mapping also required allowing the provider's apostrophe symbol in bounded, URL-encoded GET requests. Tests verify that arbitrary routes and injection strings remain rejected.

The one-day mapped probe returned 40 bars. The full original October 1-November 3 range returned **811 unique five-minute bars across all 24 expected trading sessions**. Calendars imply 1,872 possible regular-session slots; 1,061 are absent. Those absences are preserved and are not assumed to mean zero volume or an unchanged price. Recovery therefore resolves retrieval, not sparse-history qualification or strategy performance.

All 26 preexisting collection JSON files remain byte-for-byte unchanged. The mapped raw capture, exact directory/provider identity, original plan link, hashes and validation report are retained separately under ignored data/download_recovery. The recovery is not silently merged into the original frozen diagnostic. Explicit reconciliation remains a research-integration step.

Release 9b168a7e41aae84903d1a7274c1609126afab490 deployed the protected lookup and error diagnostics. Follow-up 3c3df2bee837800e60dd834a5ceb3868652804ff deployed the provider-symbol correction as Render dep-dbltiqbncjis738io7cg, verified live. GitHub checks passed for both releases; published file hashes matched. Local verification totals 208 research/UI, 7 sizing and 5 Node collector checks (220). Hosted health returned 200 in 120 ms; anonymous lookup returned 401. No orders or paid resources were added.

## Investigation and recovery method

The original PSA-K request returned an application 502 containing a generic Tradier failure. Two later attempts recorded generic network failures. They do not establish that all three reached the provider.

November 4, 2026 Pacific-time investigation:

- Local Python networking failed DNS resolution for both the research service and XFMS.
- The connected Node runtime reached XFMS, then the research health endpoint in 143 ms.
- Through that working runtime, AAPL returned 78 bars for November 3; PSA-K, PSA.K and PSA-PK returned application 502. The spelling probes are diagnostic only, not approved mappings or sample replacements.
- Private raw probes are retained in data/download_recovery. Original captures and frozen cohort are unchanged.

Recovery workflow:

1. Verify health and one known-good history from the same network runtime.
2. Preserve sanitized upstream HTTP status/category instead of collapsing every provider error into a retryable 502. Retry temporary errors; do not hammer permanent failures.
3. Use authenticated GET /api/lookup?q=Public%20Storage to inspect the provider's security identity records. Resolve the original directory instrument by series/type as well as issuer; never substitute the issuer's common shares.
4. Once identity is verified, freeze an explicit mapping and a new recovery request linked to the original failed request. Retrieve a short range first, then the missing full range. Preserve all prior failures and source hashes.
5. Reconcile the recovery with the collection diagnostic explicitly. Existing code refuses query revisions under the original frozen plan; do not overwrite that plan to bypass reconciliation.
6. If identity is confirmed but bars remain unavailable, retain an unavailable case with reason. Independent usable histories can still enter their supported experiments.

The lookup route and diagnostic error changes are now deployed and verified as described above. Future lookup results still require identity reconciliation before a mapping is accepted. No order or new paid resource is part of this recovery.
