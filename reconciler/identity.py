"""Resolve each supervisor log to a worker in the registry."""
import re


def normalize_phone(p):
    d = re.sub(r"\D", "", p or "")
    if len(d) > 10 and d.startswith("91"):
        d = d[2:]
    return d[-10:]


def build_phone_index(workers):
    """Map a normalized phone number to a worker."""
    idx = {}
    for w in workers:
        idx.setdefault(normalize_phone(w["phone"]), w)
    return idx


def resolve(logs, workers):
    """Return {log_id: worker_id}. We look the worker up by phone number,
    using the registry as the source of truth for who owns a number."""
    idx = build_phone_index(workers)
    resolved = {}
    for log in logs:
        w = idx.get(normalize_phone(log["worker_phone"]))
        resolved[log["log_id"]] = w["worker_id"] if w else None
    return resolved
