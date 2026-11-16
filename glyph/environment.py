"""environment -- what the operator reads. Co-authored.

The environment is a list of references to records written by the other
branches: {branch, file, record, sha256, at, rate?, rate_unit?}. "at" is when
the record was made; "rate" is how fast that record drifts out of date. Each one is RE-READ: the file
is opened, the record found, its sha256 compared. A reference that does not
check makes the environment VOID; nothing is taken on trust.

  branch 1   unitaudit --json report      record = index
  branch 2a  kernel check / prove report  record = theorem label / entry id
  branch 2b  numcheck --json report       record = index
  branch 4   wordslots --json report      record = index
  branch 5   infer --json report          record = hypothesis id

Features read from those records (what a tool can need):
  shared_dims          two branch-1 PASS records with the same dimension
  mixed_region         a branch-2b record whose verdict is MIXED
  conjugate_exponents  two exponents p, q with p * q = 1 in the formulas of
                       branch-1 / 2b records (sqrt counts as 1/2)
  void_slots           a branch-4 record with a slot left VOID
"""
import ast
import json
from fractions import Fraction
from pathlib import Path

from infer.ladder import Void, find_record, record_sha
from numcheck.tiers import exact_number
from unitaudit.check import split_sides

BRANCHES = ("1", "2a", "2b", "4", "5")
FEATURES = ("shared_dims", "mixed_region", "conjugate_exponents", "void_slots")


def read_record(report, branch, record):
    if branch in ("2a", "2b"):
        return find_record(report, branch, record)[0]
    if branch == "5":
        for h in (report.get("hypotheses") or []) if isinstance(report, dict) else []:
            if isinstance(h, dict) and h.get("id") == record:
                return h
        raise Void(f"no hypothesis {record!r} in the branch 5 report")
    rows = report.get("records") if isinstance(report, dict) else None
    if not isinstance(rows, list) or not isinstance(record, int) or isinstance(record, bool) \
            or not 0 <= record < len(rows) or not isinstance(rows[record], dict):
        raise Void(f"no record {record!r} in the branch {branch} report")
    r = rows[record]
    if (branch == "1" and "dims" not in r) or (branch == "4" and "word" not in r):
        raise Void(f"that record is not a branch {branch} record")
    return r


def read_ref(ref, base_dir):
    """One reference -> its record. Raises Void with the reason."""
    if not isinstance(ref, dict):
        raise Void("a reference is not a record")
    extra = [k for k in ref if k not in ("branch", "file", "record", "sha256", "at", "rate",
                                         "rate_unit")]
    if extra:
        raise Void(f"undeclared field {extra[0]!r}")
    if ref.get("branch") not in BRANCHES:
        raise Void(f"branch {ref.get('branch')!r} is not one of " + ", ".join(BRANCHES))
    if not isinstance(ref.get("file"), str) or not isinstance(ref.get("sha256"), str):
        raise Void("needs file and sha256")
    path = Path(ref["file"])
    if not path.is_absolute():
        path = Path(base_dir or ".") / path
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Void(f"cannot read {ref['file']}: {type(e).__name__}")
    rec = read_record(report, ref["branch"], ref.get("record"))
    if record_sha(rec) != ref["sha256"].lower():
        raise Void("sha256 mismatch: the record is not the one the reference names")
    return rec


def _exponents(formula):
    """[(exponent, base text)] for every literal power and sqrt in a formula."""
    out = []
    try:
        sides = split_sides(formula)
    except Exception:
        return out
    for src in sides:
        src = src.strip()
        try:
            tree = ast.parse(src, mode="eval")
        except SyntaxError:
            continue
        for n in ast.walk(tree):
            if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Pow):
                k = exact_number(n.right, src)
                if k is not None:
                    out.append((k, ast.get_source_segment(src, n.left)))
            elif isinstance(n, ast.Call) and isinstance(n.func, ast.Name) \
                    and n.func.id == "sqrt" and len(n.args) == 1:
                out.append((Fraction(1, 2), ast.get_source_segment(src, n.args[0])))
    return out


def read_environment(refs, base_dir):
    """Returns {"records": [...], "features": {name: [instance]}, "newest": t}.
    Raises Void naming the reference that does not check."""
    if not isinstance(refs, list) or not refs:
        raise Void("environment: no references")
    rows = []
    for i, ref in enumerate(refs):
        try:
            rec = read_ref(ref, base_dir)
        except Void as v:
            raise Void(f"environment reference {i}: {v}")
        at = ref.get("at")
        if isinstance(at, bool) or not isinstance(at, (int, str)):
            raise Void(f"environment reference {i}: no time 'at'")
        try:
            at = Fraction(at)
        except (ValueError, ZeroDivisionError):
            raise Void(f"environment reference {i}: cannot read 'at'")
        rate = ref.get("rate")
        if rate is not None:
            if isinstance(rate, (bool, float)):
                raise Void(f"environment reference {i}: rate is not an exact number")
            try:
                rate = Fraction(rate)
            except (ValueError, ZeroDivisionError, TypeError):
                raise Void(f"environment reference {i}: cannot read 'rate'")
        rows.append({"index": i, "branch": ref["branch"], "file": ref["file"],
                     "record": ref["record"], "sha256": ref["sha256"].lower(), "at": at,
                     "rate": rate, "rate_unit": ref.get("rate_unit"), "data": rec})
    feats = {f: [] for f in FEATURES}
    ones = [r for r in rows if r["branch"] == "1" and r["data"].get("verdict") == "PASS"]
    for i, a in enumerate(ones):
        for b in ones[i + 1:]:
            da = (a["data"].get("dims") or {}).get("lhs") or {}
            db = (b["data"].get("dims") or {}).get("lhs") or {}
            if da.get("text") and da.get("text") == db.get("text") \
                    and a["data"].get("formula") != b["data"].get("formula"):
                feats["shared_dims"].append({"sources": [a, b], "dimension": da["text"]})
    for r in rows:
        if r["branch"] == "2b" and r["data"].get("verdict") == "MIXED" \
                and r["data"].get("kind") == "point":
            feats["mixed_region"].append({"sources": [r]})
        if r["branch"] == "4" and any(s.get("slot_state") == "VOID"
                                      for s in (r["data"].get("slots") or [])):
            feats["void_slots"].append({"sources": [r]})
    exps = [(k, base, r) for r in rows if r["branch"] in ("1", "2b")
            and isinstance(r["data"].get("formula"), str)
            for k, base in _exponents(r["data"]["formula"])]
    seen = set()
    for i, (p, base, ra) in enumerate(exps):
        for q, _, rb in exps[i + 1:]:
            key = (ra["sha256"], rb["sha256"], p, q)
            if p * q == 1 and p != q and key not in seen:
                seen.add(key)
                srcs = [ra] if ra is rb else [ra, rb]
                feats["conjugate_exponents"].append(
                    {"sources": srcs, "p": p, "q": q, "base": base})
    return {"records": rows, "features": feats, "newest": max(r["at"] for r in rows)}
