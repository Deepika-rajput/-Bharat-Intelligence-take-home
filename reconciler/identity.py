"""Resolve each supervisor log to a worker in the registry."""
import re
from collections import defaultdict


def normalize_phone(p):
    d = re.sub(r"\D", "", p or "")
    if len(d) > 10 and d.startswith("91"):
        d = d[2:]
    return d[-10:]


def _name_tokens(name):
    """Lowercase word set, ignoring punctuation, for fuzzy name matching."""
    return set(re.sub(r"[^a-z ]", "", (name or "").lower()).split())


def build_phone_index(workers):
    """Map a normalized phone number to a list of workers.

    The registry has duplicate phone numbers for different workers (shared/
    reassigned numbers). We keep ALL workers per phone so callers can
    disambiguate by name rather than silently dropping everyone but the first.
    """
    idx = defaultdict(list)
    for w in workers:
        idx[normalize_phone(w["phone"])].append(w)
    return dict(idx)


def _pick_by_name(candidates, name_field):
    """Given a list of worker dicts and a raw name string, return
    (worker, confidence) where confidence is:
      1.0  — only one candidate (no collision)
      0.9  — unambiguous name match among multiple candidates
      0.5  — ambiguous (tie); caller should ESCALATE
      0.0  — no candidates
    """
    if not candidates:
        return None, 0.0
    if len(candidates) == 1:
        return candidates[0], 1.0
    tokens = _name_tokens(name_field)
    scores = [(len(tokens & _name_tokens(w["name"])), w) for w in candidates]
    scores.sort(key=lambda x: -x[0])
    if scores[0][0] > scores[1][0]:
        return scores[0][1], 0.9   # clear winner
    return None, 0.5               # genuine tie — escalate


def resolve(logs, workers):
    """Return {log_id: (worker_id, confidence)}.

    Resolution strategy:
      1. Normalise phone and look up in registry.
      2. If exactly one worker owns that phone → confident match (1.0).
      3. If multiple workers share the phone → disambiguate by name tokens.
         - Unambiguous winner → match with confidence 0.9.
         - Tie → ESCALATE with confidence 0.5.
      4. No match → ESCALATE with confidence 0.0.
    """
    idx = build_phone_index(workers)
    resolved = {}
    for log in logs:
        norm = normalize_phone(log["worker_phone"])
        candidates = idx.get(norm, [])
        worker, conf = _pick_by_name(candidates, log.get("worker_name", ""))
        if worker is None:
            resolved[log["log_id"]] = ("ESCALATE", conf)
        else:
            resolved[log["log_id"]] = (worker["worker_id"], conf)
    return resolved


def resolve_transfers(transfers, workers):
    """Return {utr: (worker_id, confidence)} using the same strategy as resolve()."""
    idx = build_phone_index(workers)
    resolved = {}
    for t in transfers:
        norm = normalize_phone(t["worker_phone"])
        candidates = idx.get(norm, [])
        worker, conf = _pick_by_name(candidates, t.get("worker_name", ""))
        resolved[t["utr"]] = (worker["worker_id"] if worker else "UNMATCHED", conf)
    return resolved
