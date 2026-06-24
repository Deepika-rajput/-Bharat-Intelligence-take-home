"""Core reconciliation: what each worker should have been paid vs. what they were."""

from . import identity, rates


def reconcile(workers, logs, transfers, rate_rows):
    """Return one row per supervisor log with the reconciliation verdict."""
    resolved = identity.resolve(logs, workers)       # {log_id: (worker_id, conf)}
    transfer_resolved = identity.resolve_transfers(transfers, workers)  # {utr: (worker_id, conf)}
    by_id = {w["worker_id"]: w for w in workers}

    # Accumulate paid paise per worker using name-disambiguated transfer resolution
    paid_paise = {}
    for t in transfers:
        wid, _conf = transfer_resolved[t["utr"]]
        if wid == "UNMATCHED":
            continue
        paid_paise[wid] = paid_paise.get(wid, 0) + int(t["amount_paise"])

    # Per-shift expected amounts and worker totals
    owed_total = {}
    per_log = []
    for log in logs:
        worker_id, log_conf = resolved[log["log_id"]]
        if worker_id == "ESCALATE":
            reason = "UNRESOLVED_WORKER" if log_conf == 0.0 else "AMBIGUOUS_IDENTITY"
            per_log.append({
                "log_id": log["log_id"],
                "worker_id": "ESCALATE",
                "expected_inr": 0.0,
                "log_conf": log_conf,
                "escalate_reason": reason,
            })
            continue
        worker = by_id[worker_id]
        rate_date = log["work_date"]   # Bug 1 fix: use work_date not entered_at
        amount = rates.expected_rupees(rate_rows, worker, rate_date, log["hours"])
        owed_total[worker_id] = owed_total.get(worker_id, 0.0) + amount
        per_log.append({
            "log_id": log["log_id"],
            "worker_id": worker_id,
            "work_date": log["work_date"],
            "hours": log["hours"],
            "expected_inr": amount,
            "log_conf": log_conf,
            "escalate_reason": None,
        })

    rows = []
    for s in per_log:
        wid = s["worker_id"]

        if wid == "ESCALATE":
            rows.append({
                "log_id": s["log_id"],
                "worker_id": "ESCALATE",
                "expected_paise": 0,
                "paid_paise": 0,
                "discrepancy_paise": 0,
                "needs_manual_review": True,
                "review_reason": s["escalate_reason"],
                "confidence": s["log_conf"],
            })
            continue

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

        # Confidence: lower if name-disambiguated, lower still if discrepancy flagged
        base_conf = s["log_conf"]
        if needs_review:
            confidence = round(base_conf * 0.75, 4)
        else:
            confidence = base_conf

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

    return rows
