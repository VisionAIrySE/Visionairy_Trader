VisionAIry Historical Replay Starter — November 3, 2026
STATUS: LOCAL PROTOTYPE. NOT DEPLOYED. NO MARKET RESULTS YET.

WHAT THIS PACKAGE DOES
1. Local masked-token form fetches one symbol's historical one-minute regular-session data from Tradier.
2. Writes data and a quality report, without writing the token.
3. Command-line replay screens one price-only benchmark (five-minute change >=2%) chronologically, with 0/60/120-second entry-delay scenarios and 5/15/60-minute exit marks.
4. Models configurable spread, per-side commission, whole shares and a prior-bar volume-participation cap.
5. Rejects duplicate/unordered/invalid bars and discloses missing entries/holding intervals.
16 automated behavioral checks pass. Tests use fabricated data, not market performance.

WHAT IT DOES NOT DO
No real or sandbox orders; no funding; no account access endpoints.
No complete universe, 32-family implementation, RVOL baseline, news, stops/targets/add-ons, simulated portfolio settlement, live scanner, dashboard, Telegram or Render deployment.
No exact historical bid/ask execution or inferred order-book depth.
No profitability conclusion.
A one-symbol sample qualifies access/schema only; SPY is an access sample, not a recommendation or the proposed discovery universe.

WINDOWS SAMPLE CHECK
Python 3.11 or later with Tkinter is required.
1. Download and extract the entire ZIP.
2. Double-click Open_Historical_Data_Check.cmd.
3. The local form opens. Enter your production Tradier API token in its masked field; do not put it in chat.
4. Review symbol/date fields and click Fetch historical sample.
5. Successful output is written in the sample folder: SYMBOL.json and SYMBOL.quality.json.
The token is cleared from the form and held transiently in process memory during the request; not saved. Individual Tradier tokens themselves grant full broker access, but this program implements only a fixed market-data GET request and rejects redirects.
Default dates are a qualification example, not a guaranteed retention promise. Start/end follow the provider's convention, which still requires validation.
Account data entitlement is not established until the sample request succeeds.
No secrets required to run the tests.

VALIDATION
From this extracted directory:
python -m unittest -v

COMMAND-LINE ACCESS CHECK (ALTERNATIVE)
python replay.py fetch --symbol SPY --start "2026-10-21 09:30" --end "2026-11-03 16:00" --out sample.json --ask-token
The token prompt is hidden; no persistent environment configuration is required.
Alternatively configure TRADIER_PRODUCTION_TOKEN securely in your runtime.
Do not pass tokens as command-line arguments.

REPLAY AFTER TIME LABEL VALIDATION
python replay.py replay --input sample/SPY.json --symbol SPY --out replay.json --bar-start-confirmed
Only use --bar-start-confirmed after confirming that timestamp labels denote minute starts. The flag is an explicit assertion, not automatic verification.
Completed signal bars become available at start+60s. Entry delays round forward to the next bar open; no fractional-minute execution inferred.
Hold outcomes are exit marks under assumed spreads, not stop/target strategy trades.
Budget default $100 is a diagnostic purchase scenario, not an actual account balance; whole-share-unaffordable cases are retained.
Volume cap is an assumed 1% of previous bar volume. This prevents using future entry-bar volume for sizing but does not prove fills.
Round-trip fees default $0.35 per side for illustration. Fixed subscription/hosting, regulatory fees, slippage and price impact are excluded.
No current data or token was accessed during development.

AUTHENTICATED QUALIFICATION REMAINING
Verify returned dates, omissions, corrections, timestamps, corporate actions and data rights.
Acquire prior warm-up observations for same-time-of-day baselines.
Establish point-in-time symbol universe and history, including failures.
Measure exact quote/depth availability; label bar-only results approximate.
Then expand detectors/management and freeze a reproducible trial ledger.

