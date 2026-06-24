# Bharat Intelligence take-home


Run it

    python -m reconciler reconcile      # writes output.csv and output.json
    python -m reconciler serve          # serves the triage stub at localhost:8000/app/
    pip install -r requirements.txt && python -m pytest    # tests

What I found and what I fixed
intially i analysed the dataset (all four data files)real-world messiness (phone numbers with +91 prefixes, mixed name casing, negative bank transfers, overlapping wage rate periods) made it clear the bugs wouldn't be obvious from the code alone. 
below are the listed bugs that i encountred
Bug 1 — Rate lookup used entry timestamp instead of work date
(reconciler/reconcile.py)
The rate was being looked up using the date extracted from entered_at (when the supervisor submitted the log) rather than work_date (when the work actually happened). Eight logs have different dates for these two fields, and three of them cross a wage rate boundary — so those workers were being calculated at the wrong hourly rate. Fixed by using log["work_date"] directly for the rate lookup.

Bug 2 — Bank reversals silently dropped (reconciler/reconcile.py)
There are four negative entries in bank_transfers.csv — a correction batch dated April 2. The code had an explicit if rupees > 0 guard that skipped them entirely. This meant four workers showed more money paid than they actually received, hiding real underpayments. Fixed by removing the guard and accumulating all transfers including negatives, directly in integer paise to avoid float precision issues.

Bug 3 — expected_paise showed worker total across all shifts, not per-shift amount (reconciler/reconcile.py)
The output contract says one row per shift. But expected_paise on every row was the worker's cumulative total across all their shifts — the per-shift amount was calculated correctly inside the loop but then discarded in favour of the running total. Found this by looking at workers with multiple logs and seeing identical expected_paise values on every row that matched neither shift individually. Fixed by storing the per-shift expected_inr and using that for expected_paise in each output row, while keeping the worker total only for the discrepancy calculation.

Bug 4 — Unresolved logs silently dropped instead of escalated (reconciler/reconcile.py)
Two logs (L00201, L00202) had phone numbers with no match in the worker registry and simply disappeared from the output. The contract explicitly says to use worker_id = "ESCALATE" for unresolvable shifts. Fixed by emitting an ESCALATE row for each unmatched log with confidence = 0.0 and review_reason = "UNRESOLVED_WORKER".

Bug 5 — "Lowest rate" logic wrong on overlapping rate periods (reconciler/rates.py)
The docstring said "lowest applicable hourly rate" — a red flag worth checking. The wage_rates data has overlapping date ranges for Data Entry / MH / junior: a general 340/hr rate from March 1 onward, and a specific 320/hr rate for March 10–20 only. The lowest-rate logic picked 320 for any date where both rows were valid, including March 24 where only the 340 rate applies. This silently underpaid 33 logs — the largest single money error. Fixed with most-specific-window-wins: when multiple rate rows cover the same date, the one with the shortest effective window takes priority (a specific override supersedes a general rate). Ties broken by latest effective_from.

Second pass — Identity resolution 
Each fix has a pinned test in tests/test_contract.py that fails against the original code and passes with the fix. The test suite grew from 3 to 8 tests total.
build_phone_index used setdefault, silently keeping the first worker when two workers share a phone number. Five phone numbers are shared by 10 workers in the data, so logs and transfers for those phones were attributed to the wrong person half the time. Fixed build_phone_index to keep all candidates per phone, then resolve by name-token matching ("Tiwari Priya" → Priya Tiwari, not Reena Singh). One case (L00181, "R. Sharma") is genuinely ambiguous and correctly escalated as AMBIGUOUS_IDENTITY. Same disambiguation applied to transfers via new resolve_transfers(). Also fixed the net summary in cli.py which was deduplicating rows incorrectly. Net corrected from Rs 1,08,598 → Rs −23,764.97. Test suite now at 9 tests.

What I'd do next with more time
The confidence score is currently binary (1.0 for clean, 0.75 for flagged). A more useful signal would factor in match quality — a worker resolved by an exact phone match is more trustworthy than one resolved after stripping country codes or normalising formatting. ESCALATE rows already get 0.0; the middle tier needs more granularity.
The triage UI works as a static page but storing resolved state in memory means it resets on reload. Persisting resolved decisions (even to localStorage) would make it actually usable across a session.
