# Failed-history recovery

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

The lookup route and diagnostic error changes require hosted release and readback before recovery is complete. Lookup results themselves do not confirm a mapping. No order or new paid resource is part of this recovery.
