"""ladder -- rival hypotheses, typed evidence, exact posteriors. Co-authored.

Stdlib only (fractions, json). Feeds the direction ranking of branch 3.

HYPOTHESIS SET  at least two rivals; one alone is VOID (nothing to weigh it
  against). Each carries a prior and the source of that prior. A prior
  flagged normalization / superiority / convenience / unknown (or given with
  no source: unknown) is not used: the whole set gets a flat prior, and the
  flag is logged. A prior is a statement about the rivals together, so one
  flagged prior flattens all of them.

EVIDENCE  hypothesis, type, likelihood ratio (a Fraction: how many times more
  expected under the named hypotheses than under the others), provenance,
  shared_ancestry tags, and the status tag of the evidence itself.
    direct        bears on one hypothesis. May carry a check from branch 2a or
                  2b.
    shadow        the trace something left, not the thing. Must list
                  alternative_casters (what else could have left it) and
                  consistent_with (every rival it fits): it updates that
                  class of hypotheses, not one. LR capped (default 3).
    cross_domain  a pattern carried over from another domain. Must declare
                  its constraints, each matched true / false; any unmatched
                  -> no update. LR capped (default 2).
  The caps are PROPOSED defaults, logged with every run.

SHARED ANCESTRY  evidence that shares a tag with earlier evidence on the same
  hypothesis is not independent of it: only the strongest of them counts.

POSTERIOR  exact, per rival: prior x the likelihood ratios that count,
  normalised. Ceiling: a result reached by inference alone is at most
  PROPOSED. A rival moves to DERIVED only on direct evidence that raises it,
  is itself OBSERVED or DERIVED, and carries a check_ref that this module
  re-reads and confirms:
    check_ref  {branch: "2a" | "2b", file, record, sha256}
               file    a JSON report written by branch 2a or 2b
               record  2b: the record's index; 2a: the theorem label, or the
                       entry id of a "kernel prove" report
               sha256  of that record (canonical JSON; see record_sha)
    confirmed  the file is read, the record found, its sha256 equal, and its
               verdict PASS (2a) or HOLDS / BOTH_HOLD with rigorous true (2b)
    otherwise  the rival stays PROPOSED, reason CHECK_UNVERIFIED. A check that
               is only declared ("check": {...verdict...}) is never enough.

DIRECTION  per rival:
    RISING     raised by at least two evidence types with no shared ancestry
    FALLING    lowered by at least two evidence types with no shared ancestry
    STACKED    moved one way more than once, by one type only: logged, no signal
    NO_SIGNAL  otherwise (also when it is both RISING and FALLING)

LOG  every step is logged with the factor it applied; a step can be reversed
  (and is, when stronger evidence of the same ancestry arrives); replay(log)
  reproduces the posteriors from the log alone.
"""
import hashlib
import json
from fractions import Fraction
from pathlib import Path

VERSION = "infer branch5-1"
STATUS = ("OBSERVED", "DERIVED", "PROPOSED")
TYPES = ("direct", "shadow", "cross_domain")
PRIOR_FLAGS = ("normalization", "superiority", "convenience", "unknown")
DEFAULT_CAPS = {"shadow": Fraction(3), "cross_domain": Fraction(2)}
PASSING = {"2a": ("PASS",), "2b": ("HOLDS", "BOTH_HOLD")}
EVIDENCE_FIELDS = ("id", "hypothesis", "type", "lr", "provenance", "shared_ancestry", "status",
                   "alternative_casters", "consistent_with", "constraints", "check",
                   "check_ref", "note")
HYPOTHESIS_FIELDS = ("id", "statement", "prior", "prior_source", "prior_flag", "note")


class Void(Exception):
    pass


def read_json(text):
    """JSON with every number kept as written, so 0.1 is one tenth."""
    return json.loads(text, parse_float=lambda s: s)


def frac(x, what):
    if isinstance(x, bool) or x is None:
        raise Void(f"{what}: not a number")
    if isinstance(x, (int, Fraction)):
        return Fraction(x)
    if isinstance(x, str):
        try:
            return Fraction(x.strip())
        except (ValueError, ZeroDivisionError):
            raise Void(f"{what}: cannot read {x!r} as a number")
    raise Void(f"{what}: give numbers as integers or strings, not binary floats")


def record_sha(record):
    """sha256 of a report record: JSON with sorted keys and no spaces."""
    text = json.dumps(record, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def find_record(report, branch, record):
    """The record a check_ref names, and its verdict. Raises Void."""
    if branch == "2b":
        rows = report.get("records") if isinstance(report, dict) else None
        if not isinstance(rows, list) or not isinstance(record, int) \
                or isinstance(record, bool) or not 0 <= record < len(rows):
            raise Void(f"no record {record!r} in the 2b report")
        r = rows[record]
        if not isinstance(r, dict) or "deciding_tier" not in r:
            raise Void("that record is not a numcheck record")
        return r, r.get("verdict"), r.get("rigorous") is True
    rows = report.get("theorem_records") if isinstance(report, dict) else None
    if isinstance(rows, list):                         # a "kernel check" report
        for r in rows:
            if isinstance(r, dict) and r.get("label") == record:
                return r, r.get("verdict"), True
        raise Void(f"no theorem {record!r} in the 2a report")
    rows = report.get("records") if isinstance(report, dict) else None
    if isinstance(rows, list):                         # a "kernel prove" report
        for r in rows:
            if isinstance(r, dict) and "kernel_verdict" in r and r.get("id") == record:
                return r, r.get("kernel_verdict"), True
    raise Void(f"no record {record!r} in the 2a report")


def verify_check(ref, base_dir):
    """Re-read the check a piece of evidence points to. Returns
    {"state": "VERIFIED" | "CHECK_UNVERIFIED", "reason", ...}."""
    out = {"state": "CHECK_UNVERIFIED", "reason": None, "check_ref": ref}
    try:
        if not isinstance(ref, dict):
            raise Void("no check_ref: a declared check is not re-read and is not enough")
        extra = [k for k in ref if k not in ("branch", "file", "record", "sha256")]
        if extra:
            raise Void(f"check_ref has an undeclared field {extra[0]!r}")
        branch = ref.get("branch")
        if branch not in PASSING:
            raise Void("check_ref must name branch 2a or 2b")
        if not isinstance(ref.get("file"), str) or not isinstance(ref.get("sha256"), str):
            raise Void("check_ref needs file and sha256")
        path = Path(ref["file"])
        if not path.is_absolute():
            path = Path(base_dir or ".") / path
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            raise Void(f"cannot read {ref['file']}: {type(e).__name__}")
        rec, verdict, rigorous = find_record(report, branch, ref.get("record"))
        got = record_sha(rec)
        out["sha256_found"] = got
        if got != ref["sha256"].lower():
            raise Void("sha256 mismatch: the record is not the one the evidence names")
        out["verdict_read"] = verdict
        if verdict not in PASSING[branch]:
            raise Void(f"the record's verdict is {verdict}, not "
                       + " / ".join(PASSING[branch]))
        if not rigorous:
            raise Void("the 2b record is not rigorous (a --fast verdict)")
        out.update(state="VERIFIED", reason=f"re-read: {branch} {verdict}, sha256 equal")
    except Void as v:
        out["reason"] = str(v)
    except Exception as e:                       # fail closed
        out["reason"] = f"internal: {type(e).__name__}: {e}"
    return out


def _post(weights):
    total = sum(weights.values())
    return {h: w / total for h, w in weights.items()}


def _strs(d):
    return {k: str(v) for k, v in d.items()}


def strength(lr):
    return lr if lr >= 1 else 1 / lr


# ---- hypotheses ------------------------------------------------------------------
def read_hypotheses(hyps, log):
    if not isinstance(hyps, list) or len(hyps) < 2:
        raise Void("a hypothesis set needs at least two rivals; "
                   + ("none given" if not isinstance(hyps, list) or not hyps
                      else "one alone cannot be weighed"))
    ids, given, flags = [], {}, {}
    for h in hyps:
        if not isinstance(h, dict) or not isinstance(h.get("id"), str) or not h["id"].strip():
            raise Void("a hypothesis has no id")
        extra = [k for k in h if k not in HYPOTHESIS_FIELDS]
        if extra:
            raise Void(f"hypothesis {h['id']!r}: undeclared field {extra[0]!r}")
        if h["id"] in ids:
            raise Void(f"hypothesis {h['id']!r} is listed twice")
        ids.append(h["id"])
        flag = h.get("prior_flag")
        if flag is not None and flag not in PRIOR_FLAGS:
            raise Void(f"hypothesis {h['id']!r}: prior_flag {flag!r} is not one of "
                       + ", ".join(PRIOR_FLAGS))
        if h.get("prior") is None:
            flag = flag or "unknown"
        else:
            given[h["id"]] = frac(h["prior"], f"prior of {h['id']!r}")
            if given[h["id"]] <= 0:
                raise Void(f"prior of {h['id']!r} is not above 0")
            if not h.get("prior_source"):
                flag = flag or "unknown"
        if flag:
            flags[h["id"]] = flag
    n = len(ids)
    if flags:
        weights = {h: Fraction(1, n) for h in ids}
        log.append({"op": "FLAT_PRIOR", "reason": "a prior is flagged: " + ", ".join(
            f"{h} ({f})" for h, f in flags.items()), "flags": flags,
            "priors_given": _strs(given), "weights": _strs(weights)})
    else:
        total = sum(given.values())
        weights = {h: given[h] / total for h in ids}
        log.append({"op": "PRIOR", "reason": "priors as given" + (
            "" if total == 1 else f", normalised (they summed to {total})"),
            "flags": {}, "priors_given": _strs(given), "weights": _strs(weights)})
    return ids, weights, flags


# ---- evidence --------------------------------------------------------------------
def read_evidence(e, ids, caps):
    """One evidence record -> (targets, effective LR, detail). Raises Void when
    the record cannot be used; returns lr None for a declared no-update."""
    if not isinstance(e, dict):
        raise Void("evidence is not a record")
    extra = [k for k in e if k not in EVIDENCE_FIELDS]
    if extra:
        raise Void(f"undeclared field {extra[0]!r}")
    kind = e.get("type")
    if kind not in TYPES:
        raise Void(f"type {kind!r} is not one of " + ", ".join(TYPES))
    if e.get("status") not in STATUS:
        raise Void(f"status {e.get('status')!r} is not one of " + ", ".join(STATUS))
    if not e.get("provenance"):
        raise Void("no provenance")
    tags = e.get("shared_ancestry")
    if tags is None:
        tags = []
    if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
        raise Void("shared_ancestry is not a list of tags")
    lr = frac(e.get("lr"), "lr")
    if lr <= 0:
        raise Void("lr is not above 0")
    detail = {"lr_given": lr, "cap": None, "capped": False}
    if kind == "shadow":
        if not isinstance(e.get("alternative_casters"), list) or not e["alternative_casters"]:
            raise Void("a shadow must list its alternative casters")
        targets = e.get("consistent_with")
        if not isinstance(targets, list) or not targets:
            raise Void("a shadow must list the hypotheses it is consistent_with")
    else:
        if not isinstance(e.get("hypothesis"), str):
            raise Void("no hypothesis named")
        targets = [e["hypothesis"]]
    unknown = [t for t in targets if t not in ids]
    if unknown:
        raise Void(f"hypothesis {unknown[0]!r} is not in the set")
    if len(set(targets)) != len(targets):
        raise Void("a hypothesis is named twice")
    if kind == "cross_domain":
        cons = e.get("constraints")
        if not isinstance(cons, list) or not cons or not all(
                isinstance(c, dict) and isinstance(c.get("name"), str)
                and isinstance(c.get("matched"), bool) for c in cons):
            raise Void("cross_domain evidence must declare its constraints, "
                       "each with name and matched true / false")
        unmatched = [c["name"] for c in cons if not c["matched"]]
        detail["constraints_unmatched"] = unmatched
        if unmatched:
            return targets, None, {**detail, "reason": "constraint not matched: "
                                   + "; ".join(unmatched)}
    if kind in caps:
        cap = caps[kind]
        detail["cap"] = cap
        if strength(lr) > cap:
            lr = cap if lr > 1 else 1 / cap
            detail["capped"] = True
    if kind == "direct" and (e.get("check") is not None or e.get("check_ref") is not None):
        if e.get("check") is not None and not isinstance(e["check"], dict):
            raise Void("check is not a record")
        detail["claims_check"] = True
    return targets, lr, detail


def _direction(moves_up, moves_down):
    def independent(group):
        return any(a["type"] != b["type"] and not set(a["tags"]) & set(b["tags"])
                   for i, a in enumerate(group) for b in group[i + 1:])

    def stacked(group):
        return len(group) >= 2 and len({a["type"] for a in group}) == 1
    up, down = independent(moves_up), independent(moves_down)
    kinds = lambda g: ", ".join(sorted({a["type"] for a in g}))          # noqa: E731
    if up and down:
        return "NO_SIGNAL", "raised and lowered, each by independent evidence types"
    if up:
        return "RISING", "raised by independent evidence of types: " + kinds(moves_up)
    if down:
        return "FALLING", "lowered by independent evidence of types: " + kinds(moves_down)
    for group, word in ((moves_up, "raised"), (moves_down, "lowered")):
        if stacked(group):
            return "STACKED", f"{word} {len(group)} times by {group[0]['type']} " \
                              "evidence only: no signal"
    for group, word in ((moves_up, "raised"), (moves_down, "lowered")):
        if len(group) >= 2:
            return "NO_SIGNAL", f"{word} by more than one type, but they share ancestry"
    return "NO_SIGNAL", f"raised by {len(moves_up)} and lowered by {len(moves_down)} " \
                        "piece(s) of evidence"


def rank(case, base_dir=None):
    """The whole run. Returns a report; verdict RANKED or VOID. base_dir: where
    the files named by check_ref are looked for (the case file's folder)."""
    log = []
    rep = {"tool": VERSION, "verdict": "VOID", "void_reason": None, "status": None,
           "ceiling": "inference alone gives at most PROPOSED",
           "caps": None, "hypotheses": [], "ranking": [], "evidence": [], "log": log,
           "counts": None, "human_interest": None, "ai_interest": None}
    try:
        if not isinstance(case, dict):
            raise Void("case is not a record")
        caps = dict(DEFAULT_CAPS)
        given_caps = case.get("caps") or {}
        if not isinstance(given_caps, dict) or any(k not in DEFAULT_CAPS for k in given_caps):
            raise Void("caps may set shadow and cross_domain only")
        for k, v in given_caps.items():
            caps[k] = frac(v, f"cap {k}")
            if caps[k] < 1:
                raise Void(f"cap {k} is below 1")
        rep["caps"] = {"shadow": str(caps["shadow"]), "cross_domain": str(caps["cross_domain"]),
                       "status": "PROPOSED",
                       "source": {k: ("case" if k in given_caps else "default")
                                  for k in DEFAULT_CAPS},
                       "note": "the caps are PROPOSED defaults, not derived from anything"}
        log.append({"op": "CAPS", **{k: rep["caps"][k] for k in ("shadow", "cross_domain",
                                                                 "status", "source")}})
        ids, weights, flags = read_hypotheses(case.get("hypotheses"), log)
        log[-1]["posterior_after"] = _strs(_post(weights))
        evidence = case.get("evidence") or []
        if not isinstance(evidence, list):
            raise Void("evidence is not a list")
        applied = []                    # records that count now
        counts = {"APPLY": 0, "NO_UPDATE": 0, "VOID": 0, "REVERSE": 0}
        seen = set()
        for n, e in enumerate(evidence):
            eid = e.get("id") if isinstance(e, dict) and isinstance(e.get("id"), str) \
                else f"#{n}"
            row = {"id": eid, "type": e.get("type") if isinstance(e, dict) else None,
                   "outcome": None, "reason": None, "targets": None, "lr_given": None,
                   "lr_effective": None, "cap": None, "capped": None,
                   "status": e.get("status") if isinstance(e, dict) else None,
                   "provenance": e.get("provenance") if isinstance(e, dict) else None,
                   "shared_ancestry": None, "counts_now": False}
            rep["evidence"].append(row)
            try:
                if eid in seen:
                    raise Void(f"evidence id {eid!r} is used twice")
                seen.add(eid)
                targets, lr, d = read_evidence(e, ids, caps)
            except Void as v:
                row.update(outcome="VOID", reason=str(v))
                counts["VOID"] += 1
                log.append({"op": "VOID", "evidence": eid, "reason": str(v),
                            "posterior_after": _strs(_post(weights))})
                continue
            tags = list(e.get("shared_ancestry") or [])
            row.update(targets=targets, lr_given=str(d["lr_given"]),
                       cap=None if d["cap"] is None else str(d["cap"]), capped=d["capped"],
                       shared_ancestry=tags)
            if lr is None:
                row.update(outcome="NO_UPDATE", reason=d["reason"])
                counts["NO_UPDATE"] += 1
                log.append({"op": "NO_UPDATE", "evidence": eid, "reason": d["reason"],
                            "posterior_after": _strs(_post(weights))})
                continue
            row["lr_effective"] = str(lr)
            if set(targets) == set(ids):
                row.update(outcome="NO_UPDATE",
                           reason="consistent with every rival: it separates none of them")
                counts["NO_UPDATE"] += 1
                log.append({"op": "NO_UPDATE", "evidence": eid, "reason": row["reason"],
                            "posterior_after": _strs(_post(weights))})
                continue
            clash = [a for a in applied if set(a["tags"]) & set(tags)
                     and set(a["targets"]) & set(targets)]
            if clash and strength(lr) <= max(strength(a["lr"]) for a in clash):
                best = max(clash, key=lambda a: strength(a["lr"]))
                row.update(outcome="NO_UPDATE",
                           reason=f"shares ancestry {sorted(set(best['tags']) & set(tags))} "
                                  f"with {best['id']}, which is at least as strong")
                counts["NO_UPDATE"] += 1
                log.append({"op": "NO_UPDATE", "evidence": eid, "reason": row["reason"],
                            "posterior_after": _strs(_post(weights))})
                continue
            for a in clash:             # the new one is stronger: take the earlier ones back
                for h in a["targets"]:
                    weights[h] /= a["lr"]
                applied.remove(a)
                counts["REVERSE"] += 1
                a["row"]["counts_now"] = False
                a["row"]["reason"] = f"reversed: {eid} shares its ancestry and is stronger"
                log.append({"op": "REVERSE", "evidence": a["id"], "targets": a["targets"],
                            "factor": str(a["lr"]),
                            "reason": f"{eid} shares ancestry and is stronger",
                            "posterior_after": _strs(_post(weights))})
            for h in targets:
                weights[h] *= lr
            applied.append({"id": eid, "targets": targets, "lr": lr, "tags": tags,
                            "type": e["type"], "row": row, "detail": d, "status": e["status"]})
            row.update(outcome="APPLY", counts_now=True,
                       reason="capped" if d["capped"] else None)
            counts["APPLY"] += 1
            log.append({"op": "APPLY", "evidence": eid, "type": e["type"], "targets": targets,
                        "factor": str(lr), "lr_given": str(d["lr_given"]),
                        "capped": d["capped"], "posterior_after": _strs(_post(weights))})
        post = _post(weights)
        for h in case["hypotheses"]:
            hid = h["id"]
            raising = [a for a in applied if hid in a["targets"] and a["lr"] > 1]
            lowering = [a for a in applied if hid in a["targets"] and a["lr"] < 1]
            signal, why = _direction(raising, lowering)
            checks, lift = [], []
            for a in applied:
                if not (a["type"] == "direct" and hid in a["targets"]
                        and a["detail"].get("claims_check")):
                    continue
                src = next(x for x in evidence if isinstance(x, dict) and x.get("id") == a["id"])
                c = verify_check(src.get("check_ref"), base_dir)
                if c["state"] == "VERIFIED" and a["lr"] <= 1:
                    c.update(state="CHECK_UNVERIFIED",
                             reason="the evidence does not raise this hypothesis")
                elif c["state"] == "VERIFIED" and a["status"] not in ("OBSERVED", "DERIVED"):
                    c.update(state="CHECK_UNVERIFIED",
                             reason=f"the evidence itself is {a['status']}")
                checks.append({"evidence": a["id"], **c})
                if c["state"] == "VERIFIED":
                    lift.append(a["id"])
            unverified = [c for c in checks if c["state"] != "VERIFIED"]
            rep["hypotheses"].append({
                "id": hid, "statement": h.get("statement"),
                "prior_given": None if h.get("prior") is None else str(h["prior"]),
                "prior_source": h.get("prior_source"), "prior_flag": flags.get(hid),
                "prior_used": log[1]["weights"][hid],
                "posterior": str(post[hid]), "posterior_approx": float(post[hid]),
                "status": "DERIVED" if lift else "PROPOSED",
                "status_reason": ("direct evidence whose 2a / 2b check was re-read and "
                                  "confirmed: " + ", ".join(lift)) if lift
                else ("CHECK_UNVERIFIED: " + "; ".join(
                    f"{c['evidence']}: {c['reason']}" for c in unverified)) if unverified
                else "inference only: at most PROPOSED",
                "checks": checks,
                "direction": signal, "direction_reason": why,
                "raised_by": [{"evidence": a["id"], "type": a["type"]} for a in raising],
                "lowered_by": [{"evidence": a["id"], "type": a["type"]} for a in lowering]})
        rep["ranking"] = [{"id": x["id"], "posterior": x["posterior"],
                           "direction": x["direction"], "status": x["status"]}
                          for x in sorted(rep["hypotheses"],
                                          key=lambda x: -Fraction(x["posterior"]))]
        rep["counts"] = counts
        rep.update(verdict="RANKED", status="PROPOSED")
        rep["replay_matches"] = replay(log) == _strs(post)
    except Void as v:
        rep.update(verdict="VOID", void_reason=str(v), status=None)
    except Exception as e:                       # fail closed
        rep.update(verdict="VOID", void_reason=f"internal: {type(e).__name__}: {e}", status=None)
    return rep


def replay(log):
    """Posteriors from the log alone: the prior step, then every APPLY and
    REVERSE in order."""
    weights = None
    for step in log:
        if step["op"] in ("PRIOR", "FLAT_PRIOR"):
            weights = {h: Fraction(w) for h, w in step["weights"].items()}
        elif step["op"] == "APPLY":
            for h in step["targets"]:
                weights[h] *= Fraction(step["factor"])
        elif step["op"] == "REVERSE":
            for h in step["targets"]:
                weights[h] /= Fraction(step["factor"])
    return None if weights is None else _strs(_post(weights))
