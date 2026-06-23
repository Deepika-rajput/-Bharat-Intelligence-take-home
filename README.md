# Bharat Intelligence take-home

This should take around 8–12 hours, and you're welcome to use whatever AI tools you're fastest with - Claude, Cursor, Copilot, ChatGPT, all fair game. We're hiring for problem-solving and for getting code right, not for how fast you type.


The situation

Bharat Intelligence pays roughly 12,000 field workers across rural India for surveying, crop inspection, and data-entry work. This repo is the little tool we use to check that the payout pipeline paid everyone the right amount. It works out what each worker should have earned per shift (from their logged hours and the wage-rate table) and reconciles that against what the bank actually transferred.

It runs, and the numbers it produces look plausible. They're wrong, though - they don't match what finance is seeing on the ground. Nobody who wrote this is still on the team, and it's about to be used to pay people, so we need it fixed first.


Run it

    python -m reconciler reconcile      # writes output.csv and output.json
    python -m reconciler serve          # serves the triage stub at localhost:8000/app/
    pip install -r requirements.txt && python -m pytest    # tests

The data is in data/ (workers, supervisor_logs, bank_transfers, wage_rates). It's real-world messy - read it carefully before you trust anything the tool says about it.

The reconciler itself is barebones on purpose - a rough first cut someone threw together. Build on it, or if you'd rather, throw it out and write your own from scratch. Either is completely fine. What matters is where you land - correct numbers, clean code, tests behind them - not whose code it is.


Your task

1. Find and fix what's wrong. The output is wrong in more than one way. Track down each problem and fix it - rewriting whatever you need to - and add a test that would have caught it. We care most about the fixes you can prove.

2. Make the output conform to this contract - one row per shift, money in integer paise:

   log_id, worker_id, expected_paise, paid_paise, discrepancy_paise,
   needs_manual_review, review_reason, confidence

   If you can't confidently resolve a shift to a worker, set worker_id to "ESCALATE" rather than guessing. review_reason is a short fixed set of reasons, not free text. confidence should mean something - a row you weren't sure about shouldn't read the same as a clean one. tests/test_contract.py encodes this contract and fails today; making it pass is part of the job.

3. Extend it, two small things:
   - A new vendor feed lands on day 3 (we'll send curveball_logs.csv). It's a different shape from the others. Fold it in without rewriting your pipeline.
   - Turn app/ into a triage view an ops person could actually use: the rows that need review, why, the amount at risk, sorted or filterable, with a way to mark one resolved. Any stack is fine.


What to send back

The repo with your fixes and tests, and a short README section (a few paragraphs, not an essay) covering: what was broken and how you found it, anything you couldn't resolve and how you handled it, and what you'd do next with more time. Plus a 10-minute screen recording walking us through it, no edits.


How we'll look at it

In rough order: did you find the bugs and can you prove the fixes; is the money right to the paise; is the code something we'd want to inherit; does the extension fit cleanly; is the triage view actually usable. A fix with a test that pins it beats a long writeup.

Read the data before you start. If you're stuck at 2 AM, cut scope and get the core solid - a few bugs fixed and proven, with the money correct, beats a half-finished sweep.

Good luck - we're rooting for you!
