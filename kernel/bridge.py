"""bridge -- proposals.json -> the kernel. Co-authored. No proof search.

An identity candidate (lhs = rhs on a domain, written by numcheck) is turned
into a Metamath statement over a small hand-written database. If someone has
put a proof of that statement in proofs/<id>.mm, the kernel checks it.

  reader      proposals.json: {"proposals": [...]} or a list. A file that is
              not that is VOID as a whole: nothing is read past it, nothing is
              written. A malformed entry is VOID, reported, left unchanged;
              it is never skipped silently.
  id          first 16 hex digits of sha256 over [lhs, rhs, domain].
  translator  domain variables -> v0, v1, ... (sorted by name); a symbol held
              at a fixed value -> that numeral; numbers 0..9, -n, p/q; + - * /;
              ** with exponent 0..9; ** (1/2) and sqrt(); unary minus. Each
              domain bound becomes a hypothesis: |- lo <_ v and |- v <_ hi.
              Anything else is untranslatable: VOID with the reason, entry
              unchanged.
  proof file  proofs/<id>.mm: $e and $p statements and ${ $} only. It may not
              declare anything ($a $c $v $f $d): that is VOID. One $p must be
              labelled "target"; its statement must be the translated one and
              its $e hypotheses must be among the translated ones.
  check       database text + proof file text -> the kernel. Every $p in the
              file must PASS.
                PASS  -> entry status DERIVED, proof "kernel"
                FAIL  -> entry stays as it was; the located step is logged
                no file -> entry stays as it was; reason NO_PROOF
  two routes  an entry already DERIVED by polynomial_identity_by_points is
              left as it is. If a kernel proof also passes, both routes are
              recorded: two independent checks.
  write-back  proposals.json is rewritten in place. Each entry keeps an
              append-only history of status and route changes (timestamp,
              route) and an append-only list of kernel checks. Nothing is
              deleted.

A PASS rests on the database's axioms. They are given input: no verdict.
"""
import ast
import datetime
import hashlib
import json
import os
from fractions import Fraction
from pathlib import Path

from numcheck.tiers import exact_number

from .mm import check_lines

VERSION = "kernel.bridge seam-0"
STATUS = ("OBSERVED", "DERIVED", "PROPOSED")
POOL = [f"v{i}" for i in range(8)]
ALLOWED_IN_PROOF = {"${", "$}", "$e", "$p", "$=", "$.", "$(", "$)"}
DEFAULT_DB = Path(__file__).resolve().parents[1] / "tests" / "data" / "algebra.mm"
POLY = "polynomial_identity_by_points"


class BridgeVoid(Exception):
    pass


def entry_id(entry):
    key = json.dumps([entry["lhs"], entry["rhs"], entry["domain"]], sort_keys=True)
    full = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return full[:16], full


def check_entry_shape(e):
    if not isinstance(e, dict):
        raise BridgeVoid("entry is not a record")
    for k in ("lhs", "rhs"):
        if not isinstance(e.get(k), str) or not e[k].strip():
            raise BridgeVoid(f"entry has no {k}")
    d = e.get("domain")
    if not isinstance(d, dict):
        raise BridgeVoid("entry has no domain")
    for name, b in d.items():
        if not isinstance(b, dict) or "lo" not in b or "hi" not in b:
            raise BridgeVoid(f"domain of {name!r} needs lo and hi")
    if e.get("status") not in STATUS:
        raise BridgeVoid(f"entry status {e.get('status')!r} is not one of " + ", ".join(STATUS))
    if "fixed" in e and not isinstance(e["fixed"], dict):
        raise BridgeVoid("fixed is not a {symbol: value} table")


# ---- translator ---------------------------------------------------------------
def _numeral(fr, what):
    if fr.denominator != 1:
        return ["("] + _numeral(Fraction(fr.numerator), what) + ["/"] \
            + _numeral(Fraction(fr.denominator), what) + [")"]
    n = int(fr)
    if n < 0:
        return ["-u"] + _numeral(Fraction(-n), what)
    if n > 9:
        raise BridgeVoid(f"{what}: the integer {n} has no numeral in the database (0 to 9 only)")
    return [str(n)]


def _read_number(text, what):
    try:
        return Fraction(str(text).strip())
    except (ValueError, ZeroDivisionError):
        raise BridgeVoid(f"{what}: cannot read {text!r} as a number")


def _term(node, src, names, fixed):
    num = exact_number(node, src)
    if num is not None:
        return _numeral(num, "a constant")
    if isinstance(node, ast.Name):
        if node.id in names:
            return [names[node.id]]
        if node.id in fixed:
            return _numeral(_read_number(fixed[node.id], f"fixed value of {node.id!r}"),
                            f"fixed value of {node.id!r}")
        raise BridgeVoid(f"symbol {node.id!r} has neither a domain nor a fixed value")
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return ["-u"] + _term(node.operand, src, names, fixed)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd):
        return _term(node.operand, src, names, fixed)
    if isinstance(node, ast.BinOp):
        if isinstance(node.op, ast.Pow):
            k = exact_number(node.right, src)
            if k is None:
                raise BridgeVoid("an exponent that is not a literal number")
            base = _term(node.left, src, names, fixed)
            if k == Fraction(1, 2):
                return ["(", "sqrt"] + base + [")"]
            if k.denominator != 1 or not 0 <= k <= 9:
                raise BridgeVoid(f"the power {k} is not in the database (0 to 9, and 1/2)")
            return ["("] + base + ["^", str(int(k)), ")"]
        op = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/"}.get(type(node.op))
        if op is None:
            raise BridgeVoid(f"operator {type(node.op).__name__} is not in the database")
        return ["("] + _term(node.left, src, names, fixed) + [op] \
            + _term(node.right, src, names, fixed) + [")"]
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        if node.func.id == "sqrt" and len(node.args) == 1 and not node.keywords:
            return ["(", "sqrt"] + _term(node.args[0], src, names, fixed) + [")"]
        raise BridgeVoid(f"the function {node.func.id} is not in the database")
    raise BridgeVoid(f"syntax {type(node).__name__} is not translatable")


def translate(entry):
    """entry -> {"variables", "hypotheses", "statement"} as token lists. Raises BridgeVoid."""
    check_entry_shape(entry)
    domain = entry["domain"]
    if len(domain) > len(POOL):
        raise BridgeVoid(f"{len(domain)} domain variables; the database has {len(POOL)}")
    names = {n: POOL[i] for i, n in enumerate(sorted(domain))}
    fixed = entry.get("fixed") or {}
    sides = []
    for k in ("lhs", "rhs"):
        src = entry[k].strip()
        try:
            tree = ast.parse(src, mode="eval").body
        except SyntaxError as e:
            raise BridgeVoid(f"{k} does not parse: {e.msg}")
        sides.append(_term(tree, src, names, fixed))
    hyps = []
    for n in sorted(domain):
        lo = _numeral(_read_number(domain[n]["lo"], f"lower bound of {n!r}"),
                      f"lower bound of {n!r}")
        hi = _numeral(_read_number(domain[n]["hi"], f"upper bound of {n!r}"),
                      f"upper bound of {n!r}")
        hyps.append(["|-"] + lo + ["<_", names[n]])
        hyps.append(["|-", names[n], "<_"] + hi)
    return {"variables": names, "hypotheses": hyps,
            "statement": ["|-"] + sides[0] + ["="] + sides[1]}


# ---- proof check ----------------------------------------------------------------
def _proof_tokens(text):
    out, inside = [], False
    for tok in text.split():
        if tok == "$(":
            inside = True
        elif tok == "$)":
            inside = False
        elif not inside:
            out.append(tok)
    return out


def check_proof(translation, proof_text, db_text):
    """Returns {"verdict": PASS / FAIL / VOID, ...}."""
    bad = sorted({t for t in _proof_tokens(proof_text)
                  if t.startswith("$") and t not in ALLOWED_IN_PROOF})
    if bad:
        return {"verdict": "VOID", "reason": "the proof file declares or uses "
                + ", ".join(bad) + ": only $e and $p statements and ${ $} are allowed"}
    base = check_lines(db_text.splitlines())
    if base.file_void:
        return {"verdict": "VOID", "reason": f"the database is VOID: {base.file_void['reason']}"}
    n_base_lines = db_text.count("\n") + 1
    db = check_lines((db_text + "\n" + proof_text).splitlines())
    rep = db.report()
    theorems = [r for r in rep["theorem_records"] if r["line"] > n_base_lines]
    for r in theorems:
        r["line_in_proof_file"] = r["line"] - n_base_lines
    summary = {"provable_statements_in_file": len(theorems),
               "labels": [r["label"] for r in theorems],
               "steps": sum(r["steps"] or 0 for r in theorems)}
    if rep["file_void"]:
        line = rep["file_void"]["line"]
        return {"verdict": "VOID", **summary,
                "reason": f"the proof file cannot be read: {rep['file_void']['reason']}",
                "line_in_proof_file": None if line is None else line - n_base_lines}
    for r in theorems:
        if r["verdict"] == "FAIL":
            return {"verdict": "FAIL", **summary,
                    "located": {"label": r["label"], "line_in_proof_file": r["line_in_proof_file"],
                                **r["located_error"]}}
        if r["verdict"] == "VOID":
            return {"verdict": "VOID", **summary,
                    "reason": f"{r['label']}: {r['void_reason']}"}
    target = db.assertions.get("target")
    if target is None or target.kind != "p":
        return {"verdict": "VOID", **summary,
                "reason": 'the proof file has no $p labelled "target"'}
    want = tuple(translation["statement"])
    if target.stmt != want:
        return {"verdict": "FAIL", **summary,
                "located": {"label": "target", "step": None, "step_label": None,
                            "rule": "target's statement is not the translated statement",
                            "expected": " ".join(want), "got": " ".join(target.stmt)}}
    allowed = {tuple(h) for h in translation["hypotheses"]}
    used = [expr for kind, _, expr in target.hyps if kind == "e"]
    extra = [h for h in used if h not in allowed]
    if extra:
        return {"verdict": "FAIL", **summary,
                "located": {"label": "target", "step": None, "step_label": None,
                            "rule": "target assumes a hypothesis that is not a domain bound",
                            "expected": "one of: " + " ; ".join(" ".join(h) for h in sorted(allowed)),
                            "got": " ".join(extra[0])}}
    if target.dv:
        return {"verdict": "VOID", **summary, "reason": "target carries a $d condition"}
    return {"verdict": "PASS", **summary,
            "hypotheses_assumed": [" ".join(h) for h in used],
            "axioms": {"count": len(base.axioms), "status": "OBSERVED",
                       "note": "given input; no verdict. The PASS rests on them."}}


# ---- the run ----------------------------------------------------------------------
def load(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise BridgeVoid(f"cannot read {path}: {e}")
    entries = data.get("proposals") if isinstance(data, dict) else data
    if not isinstance(entries, list):
        raise BridgeVoid(f"{path} is not a proposals file: no list of proposals")
    return data, entries


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _history(entry, now, route, was, to, note):
    entry.setdefault("history", []).append(
        {"at": now, "route": route, "from": was, "to": to, "note": note})


def prove(path, proofs_dir=None, db_path=None, now=None, write=True):
    path = Path(path)
    proofs_dir = Path(proofs_dir) if proofs_dir else path.parent / "proofs"
    db_path = Path(db_path) if db_path else DEFAULT_DB
    now = now or datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    report = {"tool": VERSION, "input": str(path), "proofs_dir": str(proofs_dir),
              "database": str(db_path), "file_void": None, "written": False,
              "counts": {"PASS": 0, "FAIL": 0, "VOID": 0, "NO_PROOF": 0},
              "records": [], "human_interest": None, "ai_interest": None}
    try:
        data, entries = load(path)
        try:
            db_text = db_path.read_text(encoding="utf-8")
        except OSError as e:
            raise BridgeVoid(f"cannot read the database {db_path}: {e}")
    except BridgeVoid as e:
        report["file_void"] = str(e)
        return report
    before = json.dumps(data, sort_keys=True)
    for i, entry in enumerate(entries):
        rec = {"index": i, "id": None, "lhs": None, "rhs": None, "kernel_verdict": None,
               "reason": None, "located": None, "status_before": None, "status_after": None,
               "routes": None, "statement": None, "hypotheses": None, "proof_file": None}
        report["records"].append(rec)
        try:
            tr = translate(entry)                       # also checks the entry's shape
        except BridgeVoid as e:
            rec.update(kernel_verdict="VOID", reason=str(e))
            if isinstance(entry, dict):
                rec.update(lhs=entry.get("lhs"), rhs=entry.get("rhs"),
                           status_before=entry.get("status"), status_after=entry.get("status"))
            report["counts"]["VOID"] += 1
            continue                                     # the entry is left unchanged
        short, full = entry_id(entry)
        pfile = proofs_dir / f"{short}.mm"
        was = entry["status"]
        statement = " ".join(tr["statement"])
        hyps = [" ".join(h) for h in tr["hypotheses"]]
        rec.update(id=short, lhs=entry["lhs"], rhs=entry["rhs"], status_before=was,
                   statement=statement, hypotheses=hyps, proof_file=str(pfile))
        entry["id"] = short
        k = entry.setdefault("kernel", {})
        k.update({"id_sha256": full, "database": db_path.name, "database_sha256": _sha(db_text),
                  "variables": tr["variables"], "statement": statement, "hypotheses": hyps,
                  "proof_file": f"{proofs_dir.name}/{short}.mm",
                  "proof_label": "target"})
        k.setdefault("checks", [])
        routes = entry.setdefault("routes", [])
        if entry.get("status") == "DERIVED" and not routes:
            method = (entry.get("proof") or {}).get("method") \
                if isinstance(entry.get("proof"), dict) else entry.get("proof")
            if method:
                routes.append(method)                    # the route it already had
        if not pfile.exists():
            rec.update(reason="NO_PROOF")
            k["reason"] = "NO_PROOF"
            report["counts"]["NO_PROOF"] += 1
            res = None
        else:
            try:
                ptext = pfile.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as e:
                ptext, res = None, {"verdict": "VOID", "reason": f"cannot read {pfile}: {e}"}
            if ptext is not None:
                try:
                    res = check_proof(tr, ptext, db_text)
                except Exception as e:                   # fail closed
                    res = {"verdict": "VOID", "reason": f"internal: {type(e).__name__}: {e}"}
            rec.update(kernel_verdict=res["verdict"], reason=res.get("reason"),
                       located=res.get("located"))
            report["counts"][res["verdict"]] += 1
            k["reason"] = res.get("reason")
            mark = {"proof_sha256": None if ptext is None else _sha(ptext),
                    "database_sha256": k["database_sha256"], "verdict": res["verdict"]}
            last = k["checks"][-1] if k["checks"] else {}
            if {x: last.get(x) for x in mark} != mark:   # log a check only when it is new
                k["checks"].append({"at": now, **mark,
                                    "status": "DERIVED" if res["verdict"] in ("PASS", "FAIL")
                                    else None,
                                    **{x: res[x] for x in ("reason", "located", "steps",
                                                           "labels", "hypotheses_assumed")
                                       if x in res}})
        passed = bool(res and res["verdict"] == "PASS")
        if passed and "kernel" not in routes:
            routes.append("kernel")
            if was == "DERIVED":
                _history(entry, now, "kernel", was, "DERIVED",
                         "a second, independent route: " + " and ".join(routes))
            else:
                entry["status"] = "DERIVED"
                entry["proof"] = "kernel"
                entry["proof_attempted"] = True
                entry["why_not_proved"] = None
                _history(entry, now, "kernel", was, "DERIVED",
                         "kernel PASS against " + db_path.name)
        elif not passed and "kernel" in routes:
            # a kernel route that no longer checks does not stand
            routes.remove("kernel")
            why = "NO_PROOF" if res is None else f"kernel {res['verdict']}"
            if routes:
                _history(entry, now, "kernel", was, was,
                         f"kernel route withdrawn ({why}); still DERIVED by "
                         + " and ".join(routes))
            else:
                entry["status"] = "PROPOSED"
                entry["proof"] = None
                entry["why_not_proved"] = why
                _history(entry, now, "kernel", was, "PROPOSED",
                         f"kernel route withdrawn ({why})")
        elif res is not None and res["verdict"] != "PASS" and entry.get("proof") is None:
            entry["proof_attempted"] = True
        rec.update(status_after=entry["status"], routes=list(routes))
    if write and json.dumps(data, sort_keys=True) != before:
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
        os.replace(tmp, path)
        report["written"] = True
    return report
