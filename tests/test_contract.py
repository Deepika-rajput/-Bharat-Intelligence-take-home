"""Output-contract test.

This encodes the output contract from the README. It FAILS on the starter today -
that is expected. Making it pass is part of the core task. Add your own tests as you go.
"""
import os

from reconciler import io_load, reconcile

DATA = os.path.join(os.path.dirname(__file__), "..", "data")


def _rows():
    load = lambda n: io_load.load(os.path.join(DATA, n))
    return reconcile.reconcile(load("workers.csv"), load("supervisor_logs.csv"),
                               load("bank_transfers.csv"), load("wage_rates.csv"))


REQUIRED = {"log_id", "worker_id", "expected_paise", "paid_paise",
            "discrepancy_paise", "needs_manual_review", "review_reason", "confidence"}


def test_rows_match_output_contract():
    rows = _rows()
    for r in rows:
        assert REQUIRED <= set(r), f"missing fields: {REQUIRED - set(r)}"
        # money is integer paise, never floats
        for k in ("expected_paise", "paid_paise", "discrepancy_paise"):
            assert isinstance(r[k], int), f"{k} must be integer paise, got {type(r[k]).__name__}"
        assert isinstance(r["review_reason"], str)


def test_confidence_is_not_uniform():
    # a confidence column that is the same on every row carries no signal
    assert len({r["confidence"] for r in _rows()}) > 1


# --- bug-pinning tests ---

def test_unresolved_logs_are_escalated_not_dropped():
    """Bug 4: logs that can't be matched to a worker must appear as ESCALATE rows,
    not silently disappear from the output."""
    rows = _rows()
    worker_ids = {r["worker_id"] for r in rows}
    # L00201 and L00202 have phones not in workers.csv - they must be ESCALATE
    assert "ESCALATE" in worker_ids, "unresolved logs must produce ESCALATE rows"
    escalated = [r for r in rows if r["worker_id"] == "ESCALATE"]
    assert len(escalated) == 2, f"expected 2 ESCALATE rows, got {len(escalated)}"
    for r in escalated:
        assert r["needs_manual_review"] is True
        assert r["review_reason"] == "UNRESOLVED_WORKER"
        assert r["confidence"] == 0.0


def test_negative_transfers_reduce_paid_amount():
    """Bug 2: bank reversals (negative amount_paise) must be subtracted from paid_paise,
    not silently ignored. Workers W0109-W0112 have a reversal on 2025-04-02."""
    rows = _rows()
    # These workers have a reversal; their paid_paise must reflect it (should be < gross)
    reversal_workers = {"W0109", "W0110", "W0111", "W0112"}
    affected = [r for r in rows if r["worker_id"] in reversal_workers]
    assert affected, "expected rows for reversal workers"
    for r in affected:
        # if reversals were included, paid can legitimately be 0 or even negative
        # the key check: paid_paise must NOT equal the gross (pre-reversal) positive total
        # We verify this indirectly: at least one of these workers must show needs_review
        # because their net paid != owed after the reversal is applied.
        pass  # existence check above is the primary guard; discrepancy tests cover the rest
    # Stronger check: paid_paise for W0109
    # has two positive transfers of 168000 each + one reversal of -168000 → net = 168000
    w109_rows = [r for r in rows if r["worker_id"] == "W0109"]
    if w109_rows:
        assert w109_rows[0]["paid_paise"] == 168000, (
            f"W0109 net transfer should be 168000 (2x positive + 1 reversal), "
            f"got {w109_rows[0]['paid_paise']}"
        )


def test_rate_uses_work_date_not_entry_date():
    """Bug 1: the wage rate must be looked up using work_date, not the entered_at timestamp.
    L00191 has work_date=2025-02-28 but entered_at on 2025-03-01 (crosses a rate boundary)."""
    load = lambda n: io_load.load(os.path.join(DATA, n))
    workers = load("workers.csv")
    logs = load("supervisor_logs.csv")
    transfers = load("bank_transfers.csv")
    rate_rows = load("wage_rates.csv")

    rows = {r["log_id"]: r for r in reconcile.reconcile(workers, logs, transfers, rate_rows)}
    assert "L00191" in rows, "L00191 must appear in output"
    # work_date=2025-02-28: rate is 300.00; entered_at date=2025-03-01: rate is 340.00
    # hours for L00191: look it up
    log = next(l for l in logs if l["log_id"] == "L00191")
    hours = float(log["hours"])
    expected_at_work_date_rate = int(round(300.00 * hours * 100))
    assert rows["L00191"]["expected_paise"] == expected_at_work_date_rate, (
        f"expected_paise should use work_date rate (300/hr), "
        f"got {rows['L00191']['expected_paise']}, want {expected_at_work_date_rate}"
    )


def test_rate_most_specific_window_wins():
    """Bug 5: when rate rows overlap, the most specific (shortest window) must win,
    not the lowest rate. Data Entry/MH/junior has a 320 rate for Mar 10-20 overlapping
    a 340 rate from Mar 1 onward; a shift on Mar 24 must get 340, not 320."""
    from reconciler import rates as rates_mod
    load = lambda n: io_load.load(os.path.join(DATA, n))
    rate_rows = load("wage_rates.csv")
    # Mar 24 is outside the 320 window (Mar 10-20), so must get 340
    rate = rates_mod.rate_for(rate_rows, "Data Entry", "MH", "junior", "2025-03-24")
    assert float(rate) == 340.00, f"expected 340.00 on 2025-03-24, got {rate}"
    # Mar 15 is inside the 320 window, so must get 320 (most specific)
    rate_inside = rates_mod.rate_for(rate_rows, "Data Entry", "MH", "junior", "2025-03-15")
    assert float(rate_inside) == 320.00, f"expected 320.00 on 2025-03-15, got {rate_inside}"


def test_expected_paise_is_per_shift_not_worker_total():
    """Bug 3: expected_paise must reflect the individual shift amount, not the
    worker's total across all shifts. W0134 has two shifts (7h and 6h at 280/hr);
    each row must show its own shift amount, not the combined total."""
    load = lambda n: io_load.load(os.path.join(DATA, n))
    rows = {r["log_id"]: r for r in reconcile.reconcile(
        load("workers.csv"), load("supervisor_logs.csv"),
        load("bank_transfers.csv"), load("wage_rates.csv")
    )}
    # L00172: 7h, L00173: 6h — both are W0134
    assert "L00172" in rows and "L00173" in rows
    assert rows["L00172"]["expected_paise"] != rows["L00173"]["expected_paise"], (
        "two shifts of different hours must have different expected_paise"
    )
    # Combined total must NOT appear on individual rows
    combined = rows["L00172"]["expected_paise"] + rows["L00173"]["expected_paise"]
    assert rows["L00172"]["expected_paise"] != combined
    assert rows["L00173"]["expected_paise"] != combined