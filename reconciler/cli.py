"""Command line entry point.

Usage:
    python -m reconciler reconcile     # writes output.csv and output.json
    python -m reconciler serve         # serves the triage view on :8000
"""
import csv
import json
import os
import sys

from . import io_load, reconcile

DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data"))
ROOT = os.path.join(os.path.dirname(__file__), "..")


def _load_all():
    return (
        io_load.load(os.path.join(DATA_DIR, "workers.csv")),
        io_load.load(os.path.join(DATA_DIR, "supervisor_logs.csv")),
        io_load.load(os.path.join(DATA_DIR, "bank_transfers.csv")),
        io_load.load(os.path.join(DATA_DIR, "wage_rates.csv")),
    )


def run_reconcile():
    workers, logs, transfers, rate_rows = _load_all()
    rows = reconcile.reconcile(workers, logs, transfers, rate_rows)
    with open(os.path.join(ROOT, "output.csv"), "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)
    with open(os.path.join(ROOT, "output.json"), "w") as f:
        json.dump(rows, f, indent=2)
    flagged = sum(1 for r in rows if r["needs_manual_review"])
    net = (
    sum(r["paid_paise"] for r in {r["worker_id"]: r for r in rows}.values())
    - sum(r["expected_paise"] for r in {r["worker_id"]: r for r in rows}.values())) / 100
    print(f"Reconciled {len(rows)} logs across {len({r['worker_id'] for r in rows})} workers.")
    print(f"Flagged for review: {flagged}")
    print(f"Net (paid - owed): Rs {net:,.2f}")
    print("Wrote output.csv and output.json")


def run_serve():
    import http.server
    import socketserver
    os.chdir(ROOT)
    with socketserver.TCPServer(("", 8000), http.server.SimpleHTTPRequestHandler) as httpd:
        print("Triage view on http://localhost:8000/app/  (Ctrl-C to stop)")
        httpd.serve_forever()


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    cmd = argv[0] if argv else "reconcile"
    if cmd == "serve":
        run_serve()
    else:
        run_reconcile()


if __name__ == "__main__":
    main()
