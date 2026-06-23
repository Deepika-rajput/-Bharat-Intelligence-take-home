"""Smoke tests - these pass on the starter as-is. Keep them green."""
import os

from reconciler import io_load, reconcile

DATA = os.path.join(os.path.dirname(__file__), "..", "data")


def _load():
    return (
        io_load.load(os.path.join(DATA, "workers.csv")),
        io_load.load(os.path.join(DATA, "supervisor_logs.csv")),
        io_load.load(os.path.join(DATA, "bank_transfers.csv")),
        io_load.load(os.path.join(DATA, "wage_rates.csv")),
    )


def test_reconcile_runs_and_returns_rows():
    rows = reconcile.reconcile(*_load())
    assert isinstance(rows, list) and rows
    assert all("log_id" in r for r in rows)
