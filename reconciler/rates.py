"""Wage-rate lookup and expected-pay calculation."""


def rate_for(rate_rows, role, state, seniority, date_str):
    """Most-specific applicable hourly rate for a (role, state, seniority) on a date.

    When multiple rate rows cover the same date, the one with the shortest
    effective window wins (most specific overrides general). Ties broken by
    latest effective_from (most recent rate row).
    """
    best = None
    best_window = None
    best_from = None
    for r in rate_rows:
        if (r["role"], r["state"], r["seniority"]) != (role, state, seniority):
            continue
        eff_to = r["effective_to"] or "9999-12-31"
        if r["effective_from"] <= date_str <= eff_to:
            window = (
                (eff_to if r["effective_to"] else "9999-12-31"),
                -(len(r["effective_from"])),  # dummy; we compare window size below
            )
            # compute window size in days for comparison
            from datetime import date
            d_from = date.fromisoformat(r["effective_from"])
            d_to = date.fromisoformat(eff_to)
            window_days = (d_to - d_from).days
            if (
                best is None
                or window_days < best_window
                or (window_days == best_window and r["effective_from"] > best_from)
            ):
                best = r["hourly_rate_inr"]
                best_window = window_days
                best_from = r["effective_from"]
    return best


def expected_rupees(rate_rows, worker, date_str, hours):
    rate = rate_for(rate_rows, worker["role"], worker["state"], worker["seniority"], date_str)
    if rate is None:
        return 0.0
    return round(float(rate) * float(hours), 2)