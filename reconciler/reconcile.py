"""Core reconciliation: what each worker should have been paid vs. what they were."""
from datetime import datetime, timezone, timedelta

from . import identity, rates

IST = timezone(timedelta(hours=5, minutes=30))


def reconcile(workers, logs, transfers, rate_rows):
    """Return one row per supervisor log with the reconciliation verdict."""
    resolved = identity.resolve(logs, workers)
    by_id = {w["worker_id"]: w for w in workers}

    # Bug 4 fix: emit ESCALATE rows for logs that couldn't be resolved to a worker
    escalate_rows = []
    for log in logs:
        if resolved[log["log_id"]] is None:
            escalate_rows.append({
                "log_id": log["log_id"],
                "worker_id": "ESCALATE",
                "expected_paise": 0,
                "paid_paise": 0,
                "discrepancy_paise": 0,
                "needs_manual_review": True,
                "review_reason": "UNRESOLVED_WORKER",
                "confidence": 0.0,
            })

    # Bug 1 fix: use work_date (not entered_at) for rate lookup
    # Bug 3 fix: store per-shift expected_inr so output is per-shift not worker-total
    owed_total = {}  # worker_id -> total owed across all shifts (for discrepancy calc)
    per_log = []
    for log in logs:
        worker_id = resolved[log["log_id"]]
        if worker_id is None:
            continue
        worker = by_id[worker_id]
        rate_date = log["work_date"]  # use actual work date, not entry timestamp
        amount = rates.expected_rupees(rate_rows, worker, rate_date, log["hours"])
        owed_total[worker_id] = owed_total.get(worker_id, 0.0) + amount
        per_log.append({
            "log_id": log["log_id"],
            "worker_id": worker_id,
            "work_date": log["work_date"],
            "hours": log["hours"],
            "expected_inr": amount,  # per-shift amount
        })

    # Bug 2 fix: accumulate all transfers in integer paise (including reversals/negatives)
    paid_paise = {}
    phone_index = identity.build_phone_index(workers)
    for t in transfers:
        worker = phone_index.get(identity.normalize_phone(t["worker_phone"]))
        if not worker:
            continue
        paid_paise[worker["worker_id"]] = (
            paid_paise.get(worker["worker_id"], 0) + int(t["amount_paise"])
        )

    rows = []
    for s in per_log:
        wid = s["worker_id"]
        # Bug 3 fix: expected_paise is per-shift; discrepancy uses worker totals
        shift_expected_paise = int(round(s["expected_inr"] * 100))
        worker_paid_paise = paid_paise.get(wid, 0)
        worker_owed_paise = int(round(owed_total.get(wid, 0.0) * 100))
        discrepancy_paise = worker_paid_paise - worker_owed_paise

        needs_review = discrepancy_paise != 0
        if discrepancy_paise < 0:
            review_reason = "UNDERPAID"
        elif discrepancy_paise > 0:
            review_reason = "OVERPAID"
        else:
            review_reason = ""

        confidence = 0.75 if needs_review else 1.0

        rows.append({
            "log_id": s["log_id"],
            "worker_id": wid,
            "expected_paise": shift_expected_paise,
            "paid_paise": worker_paid_paise,
            "discrepancy_paise": discrepancy_paise,
            "needs_manual_review": needs_review,
            "review_reason": review_reason,
            "confidence": confidence,
        })

    return escalate_rows + rows