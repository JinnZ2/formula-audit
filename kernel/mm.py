"""mm -- read a Metamath .mm database and verify its proofs.

Co-authored. Stdlib only. Written from the Metamath language specification
(the Metamath book, chapter 4, and its appendix on compressed proofs), not
from an existing verifier.

The language, as implemented here
  $c ... $.            constants (outermost scope only)
  $v ... $.            variables (scoped)
  ${ ... $}            scope: variables, hypotheses and $d end with it
  L $f C x $.          floating hypothesis: variable x has typecode C
  L $e C s ... $.      essential hypothesis
  $d x y ... $.        the listed variables are pairwise disjoint
  L $a C s ... $.      axiom
  L $p C s ... $= proof $.     provable statement
  $( ... $)            comment

An assertion ($a or $p) carries a frame: its mandatory hypotheses (every
active $e, and the active $f of each variable in the statement or in those
$e), in the order they appear in the database, and the active $d pairs
between its mandatory variables.

A proof is a sequence of labels worked on a stack. A hypothesis label
pushes its expression. An assertion label with n mandatory hypotheses takes
the top n entries: the entries facing $f hypotheses give a substitution
(typecodes must agree), the entries facing $e hypotheses must equal those
hypotheses under the substitution, and for each $d pair of the assertion
the two substituted expressions must share no variable and every pair of
variables across them must be under an active $d of the theorem being
proved. The substituted statement is pushed. At the end the stack must hold
exactly the theorem's statement.

Verdicts
  PASS  every step checked and the stack ends as the statement
  FAIL  a step did not check: step number, label, expected, got
  VOID  not checked: incomplete proof ("?"), a compressed proof that does
        not decode, an internal error; at file level: an unknown keyword,
        an include, or a malformed statement. Reading stops there, and
        nothing after it is given any verdict.
Status: PASS / FAIL are DERIVED. Axioms are given input: OBSERVED, with no
verdict. VOID has no status.
"""
import hashlib
import time

KEYWORDS = {"$c", "$v", "$f", "$e", "$d", "$a", "$p", "$.", "$=", "$(", "$)",
            "${", "$}", "$[", "$]"}
VERSION = "kernel branch2a-0"


class FileVoid(Exception):
    """The database cannot be read past this point."""

    def __init__(self, reason, line=None):
        super().__init__(reason)
        self.reason, self.line = reason, line


class ProofFail(Exception):
    def __init__(self, rule, step=None, label=None, expected=None, got=None):
        super().__init__(rule)
        self.rule, self.step, self.label = rule, step, label
        self.expected, self.got = expected, got


class ProofVoid(Exception):
    pass


def _text(expr):
    return None if expr is None else (expr if isinstance(expr, str) else " ".join(expr))


class Frame:
    __slots__ = ("v", "hyps", "d")

    def __init__(self):
        self.v, self.hyps, self.d = [], [], set()


class Assertion:
    __slots__ = ("label", "kind", "stmt", "hyps", "dv", "line")

    def __init__(self, label, kind, stmt, hyps, dv, line):
        self.label, self.kind, self.stmt, self.hyps, self.dv, self.line = \
            label, kind, stmt, hyps, dv, line


class Database:
    def __init__(self):
        self.constants = set()
        self.active_v = set()
        self.f_of = {}              # active variable -> (typecode, label)
        self.active_hyps = {}       # active hypothesis label -> (kind, expr)
        self.frames = [Frame()]
        self.assertions = {}        # label -> Assertion
        self.labels = set()
        self.axioms = []            # records
        self.theorems = []          # records
        self.verdict_of = {}        # theorem label -> verdict
        self.file_void = None
        self.stopped = None
        self.line = 0
        self.statements_read = 0
        self.used_of = {}           # provable label -> labels of assertions it cites
        self.hashing = False        # sha256 of the lines read, kept per $p (snapshots)
        self._hash = None
        self.digest_at = {}         # provable label -> (lines read, sha256 of those lines)
        self.carry = None           # a loaded snapshot: prefix theorems are not re-verified

    # ---- tokens -------------------------------------------------------
    def _raw(self, lines):
        if self.hashing:
            self._hash = hashlib.sha256()
        for n, line in enumerate(lines, 1):
            self.line = n
            if self._hash is not None:
                self._hash.update(line.encode("utf-8"))
            for tok in line.split():
                yield tok

    def _tokens(self, lines):
        raw = self._raw(lines)
        for tok in raw:
            if tok == "$(":
                start = self.line
                for inner in raw:
                    if inner == "$)":
                        break
                    if inner == "$(":
                        raise FileVoid("comment opened inside a comment", self.line)
                else:
                    raise FileVoid("comment not closed", start)
                continue
            if tok[0] == "$" and tok not in KEYWORDS:
                raise FileVoid(f"unknown keyword {tok}", self.line)
            if tok in ("$[", "$]"):
                raise FileVoid("include statements are not supported", self.line)
            if tok == "$)":
                raise FileVoid("comment closed but not opened", self.line)
            yield tok

    def _until(self, toks, enders):
        out = []
        for tok in toks:
            if tok in enders:
                return out, tok
            if tok[0] == "$":
                raise FileVoid(f"{tok} inside a statement", self.line)
            out.append(tok)
        raise FileVoid("file ends inside a statement", self.line)

    # ---- statements ----------------------------------------------------
    def _check_expr(self, expr, what):
        if not expr:
            raise FileVoid(f"{what}: empty statement", self.line)
        if expr[0] not in self.constants:
            raise FileVoid(f"{what}: first symbol {expr[0]} is not a constant", self.line)
        for s in expr[1:]:
            if s in self.active_v:
                if s not in self.f_of:
                    raise FileVoid(f"{what}: variable {s} has no active $f", self.line)
            elif s not in self.constants:
                raise FileVoid(f"{what}: symbol {s} is not declared", self.line)

    def _new_label(self, label):
        if label in self.labels:
            raise FileVoid(f"label {label} used twice", self.line)
        if label in self.constants or label in self.active_v:
            raise FileVoid(f"label {label} is also a math symbol", self.line)
        self.labels.add(label)

    def _make_assertion(self, label, kind, stmt, line):
        mand = {s for s in stmt if s in self.active_v}
        for fr in self.frames:
            for k, _, expr in fr.hyps:
                if k == "e":
                    mand.update(s for s in expr if s in self.active_v)
        hyps = [h for fr in self.frames for h in fr.hyps if h[0] == "e" or h[2][1] in mand]
        dv = {p for fr in self.frames for p in fr.d if p[0] in mand and p[1] in mand}
        return Assertion(label, kind, stmt, hyps, dv, line)

    def read(self, lines, limit=None, until=None, seconds=None):
        """Read and verify. lines: an iterable of text lines."""
        t0 = time.perf_counter()
        try:
            toks = self._tokens(lines)
            for tok in toks:
                self.statements_read += 1
                if tok == "$c":
                    syms, _ = self._until(toks, ("$.",))
                    if len(self.frames) > 1:
                        raise FileVoid("$c inside a scope", self.line)
                    for s in syms:
                        if s in self.constants or s in self.active_v or s in self.labels:
                            raise FileVoid(f"constant {s} already declared", self.line)
                        self.constants.add(s)
                elif tok == "$v":
                    syms, _ = self._until(toks, ("$.",))
                    for s in syms:
                        if s in self.constants or s in self.active_v or s in self.labels:
                            raise FileVoid(f"variable {s} already declared", self.line)
                        self.active_v.add(s)
                        self.frames[-1].v.append(s)
                elif tok == "$d":
                    syms, _ = self._until(toks, ("$.",))
                    if len(set(syms)) != len(syms) or len(syms) < 2:
                        raise FileVoid("$d needs two or more different variables", self.line)
                    for s in syms:
                        if s not in self.active_v:
                            raise FileVoid(f"$d: {s} is not an active variable", self.line)
                    for i, a in enumerate(syms):
                        for b in syms[i + 1:]:
                            self.frames[-1].d.add((a, b) if a < b else (b, a))
                elif tok == "${":
                    self.frames.append(Frame())
                elif tok == "$}":
                    if len(self.frames) == 1:
                        raise FileVoid("$} with no open scope", self.line)
                    fr = self.frames.pop()
                    for k, lab, expr in fr.hyps:
                        del self.active_hyps[lab]
                        if k == "f":
                            del self.f_of[expr[1]]
                    for s in fr.v:
                        self.active_v.discard(s)
                elif tok[0] == "$":
                    raise FileVoid(f"{tok} where a statement should start", self.line)
                else:
                    label = tok
                    kw = next(toks, None)
                    line = self.line
                    if kw not in ("$f", "$e", "$a", "$p"):
                        raise FileVoid(f"label {label} is not followed by $f $e $a or $p",
                                       self.line)
                    self._new_label(label)
                    if kw == "$f":
                        expr, _ = self._until(toks, ("$.",))
                        if len(expr) != 2 or expr[0] not in self.constants \
                                or expr[1] not in self.active_v:
                            raise FileVoid(f"$f {label}: needs a constant and an active variable",
                                           self.line)
                        if expr[1] in self.f_of:
                            raise FileVoid(f"$f {label}: {expr[1]} already has an active $f",
                                           self.line)
                        expr = tuple(expr)
                        self.f_of[expr[1]] = (expr[0], label)
                        self.frames[-1].hyps.append(("f", label, expr))
                        self.active_hyps[label] = ("f", expr)
                    elif kw == "$e":
                        expr, _ = self._until(toks, ("$.",))
                        self._check_expr(expr, f"$e {label}")
                        expr = tuple(expr)
                        self.frames[-1].hyps.append(("e", label, expr))
                        self.active_hyps[label] = ("e", expr)
                    elif kw == "$a":
                        expr, _ = self._until(toks, ("$.",))
                        self._check_expr(expr, f"$a {label}")
                        self.assertions[label] = self._make_assertion(label, "a", tuple(expr),
                                                                      line)
                        self.axioms.append({"label": label, "line": line, "verdict": None,
                                            "status": "OBSERVED",
                                            "note": "axiom: given input, not verified"})
                    else:
                        expr, _ = self._until(toks, ("$=",))
                        self._check_expr(expr, f"$p {label}")
                        try:
                            proof, _ = self._until(toks, ("$.",))
                        except FileVoid as e:
                            self._record(label, line, "VOID", void_reason=e.reason)
                            raise
                        a = self._make_assertion(label, "p", tuple(expr), line)
                        if self.carry is not None and len(self.theorems) < self.carry["index"]:
                            self._carry(a, proof)
                        else:
                            self._verify(a, proof)
                        self.assertions[label] = a
                        if self._hash is not None:
                            self.digest_at[label] = (self.line, self._hash.copy().hexdigest())
                        if limit is not None and len(self.theorems) >= limit:
                            self.stopped = f"limit of {limit} provable statements reached"
                            break
                        if until is not None and label == until:
                            self.stopped = f"label {until} reached"
                            break
                        if seconds is not None and time.perf_counter() - t0 >= seconds:
                            self.stopped = f"time budget of {seconds} s reached"
                            break
            else:
                if len(self.frames) != 1:
                    raise FileVoid("file ends with a scope still open", self.line)
        except FileVoid as e:
            self.file_void = {"reason": e.reason, "line": e.line}
        except Exception as e:             # fail closed
            self.file_void = {"reason": f"internal: {type(e).__name__}: {e}", "line": self.line}
        if self.file_void is not None and self.carry is not None and \
                len(self.theorems) <= self.carry["index"]:
            # the snapshot was never confirmed in place: nothing carried stands
            for r in self.theorems:
                if not r["verified_here"]:
                    r.update(verdict="VOID", status=None, located_error=None,
                             void_reason="carried from a snapshot that did not match in place")
                    self.verdict_of[r["label"]] = "VOID"
        return self

    # ---- proofs ---------------------------------------------------------
    def _record(self, label, line, verdict, fmt=None, steps=None, fail=None, void_reason=None,
                rests=(), carried=None, located=None):
        self.verdict_of[label] = verdict
        if fail is not None:
            located = {"step": fail.step, "step_label": fail.label, "rule": fail.rule,
                       "expected": _text(fail.expected), "got": _text(fail.got)}
        self.theorems.append({
            "label": label, "line": line, "verdict": verdict,
            "status": "DERIVED" if verdict in ("PASS", "FAIL") else None,
            "proof_format": fmt, "steps": steps,
            "located_error": located,
            "void_reason": void_reason,
            "rests_on_non_pass": sorted(rests),
            "verified_here": carried is None,
            "carried_from_snapshot": carried,
            "human_interest": None, "ai_interest": None})

    def _decode(self, a, proof):
        """Compressed proof -> list of steps: a label, ("ref", k) or ("save",)."""
        try:
            close = proof.index(")")
        except ValueError:
            raise ProofVoid("compressed proof: label list not closed")
        labels = proof[1:close]
        mand = [h[1] for h in a.hyps]
        m, n_lab = len(mand), len(labels)
        steps, n = [], 0
        for ch in "".join(proof[close + 1:]):
            if "A" <= ch <= "T":
                n = n * 20 + (ord(ch) - 64)
                if n <= m:
                    steps.append(mand[n - 1])
                elif n <= m + n_lab:
                    steps.append(labels[n - m - 1])
                else:
                    steps.append(("ref", n - m - n_lab - 1))
                n = 0
            elif "U" <= ch <= "Y":
                n = n * 5 + (ord(ch) - 84)
            elif ch == "Z":
                if n:
                    raise ProofVoid("compressed proof: Z inside a number")
                steps.append(("save",))
            elif ch == "?":
                raise ProofVoid("incomplete proof: ? step")
            else:
                raise ProofVoid(f"compressed proof: character {ch!r}")
        if n:
            raise ProofVoid("compressed proof: ends inside a number")
        return steps

    def _carry(self, a, proof):
        """A theorem inside a snapshot's prefix: not re-verified. Its verdict is the
        snapshot's (PASS unless the snapshot lists it as not PASS). The labels it
        cites are read from the proof text, not from checked steps."""
        c = self.carry
        fmt = "compressed" if proof and proof[0] == "(" else "normal"
        if fmt == "compressed":
            cited = proof[1:proof.index(")")] if ")" in proof else []
        else:
            cited = proof
        used = {t for t in cited if t in self.assertions}
        self.used_of[a.label] = used
        np = c["non_pass"].get(a.label)
        verdict = "PASS" if np is None else np["verdict"]
        rests = {u for u in used if self.verdict_of.get(u, "PASS") != "PASS"}
        self._record(a.label, a.line, verdict, fmt, None, rests=rests, carried=c["label"],
                     located=None if np is None else np.get("located_error"),
                     void_reason=None if np is None else np.get("void_reason"))
        if len(self.theorems) == c["index"]:
            if a.label != c["label"] or a.stmt != tuple(c["statement"].split()):
                raise FileVoid(f"snapshot {c['label']}: the statement at its position "
                               f"is {a.label} {_text(a.stmt)}", self.line)

    def axioms_used(self, label):
        """Every $a reached from `label` through the assertions its proof cites,
        and theirs, transitively. Includes syntax axioms (typecodes other than |-)."""
        seen, out, todo = set(), set(), [label]
        while todo:
            x = todo.pop()
            if x in seen:
                continue
            seen.add(x)
            b = self.assertions.get(x)
            if b is None:
                continue
            if b.kind == "a":
                out.add(x)
            else:
                todo.extend(self.used_of.get(x, ()))
        return sorted(out)

    def _verify(self, a, proof):
        fmt = "compressed" if proof and proof[0] == "(" else "normal"
        used, count = set(), 0
        self.used_of[a.label] = used
        try:
            if not proof:
                raise ProofVoid("empty proof")
            if fmt == "compressed":
                steps = self._decode(a, proof)
            else:
                if "?" in proof:
                    raise ProofVoid("incomplete proof: ? step")
                steps = proof
            cur_dv = set().union(*[fr.d for fr in self.frames])
            active_v, hyps, asserts = self.active_v, self.active_hyps, self.assertions
            stack, saved = [], []
            for st in steps:
                if st.__class__ is tuple:
                    if st[0] == "save":
                        if not stack:
                            raise ProofVoid("compressed proof: Z with nothing to save")
                        saved.append(stack[-1])
                        continue
                    count += 1
                    if st[1] >= len(saved):
                        raise ProofFail("reference to a saved step that does not exist", count,
                                        None, f"at most {len(saved)} saved", f"number {st[1] + 1}")
                    stack.append(saved[st[1]])
                    continue
                count += 1
                h = hyps.get(st)
                if h is not None:
                    stack.append(h[1])
                    continue
                b = asserts.get(st)
                if b is None:
                    raise ProofFail("label is not an active hypothesis or an earlier assertion",
                                    count, st, "a usable label", st)
                used.add(st)
                n = len(b.hyps)
                if len(stack) < n:
                    raise ProofFail("not enough entries on the stack", count, st,
                                    f"{n} entries", f"{len(stack)} entries")
                base = len(stack) - n
                subst = {}
                for i, (k, lab, expr) in enumerate(b.hyps):
                    if k == "f":
                        entry = stack[base + i]
                        if not entry or entry[0] != expr[0]:
                            raise ProofFail(f"typecode for {expr[1]} (hypothesis {lab})", count,
                                            st, expr[0] + " ...", entry)
                        subst[expr[1]] = entry[1:]
                for i, (k, lab, expr) in enumerate(b.hyps):
                    if k == "e":
                        want = self._apply(expr, subst)
                        if want != stack[base + i]:
                            raise ProofFail(f"essential hypothesis {lab}", count, st, want,
                                            stack[base + i])
                for x, y in b.dv:
                    xs = [s for s in subst[x] if s in active_v]
                    ys = [s for s in subst[y] if s in active_v]
                    for p in xs:
                        for q in ys:
                            if p == q:
                                raise ProofFail(f"disjoint variables {x} {y}", count, st,
                                                "no shared variable", f"{p} in both")
                            if ((p, q) if p < q else (q, p)) not in cur_dv:
                                raise ProofFail(f"disjoint variables {x} {y}", count, st,
                                                f"$d {p} {q} in effect", "no such $d")
                del stack[base:]
                stack.append(self._apply(b.stmt, subst))
            if len(stack) != 1:
                raise ProofFail("the proof must leave exactly one entry", count, None,
                                "1 entry", f"{len(stack)} entries")
            if stack[0] != a.stmt:
                raise ProofFail("the proved expression is not the statement", count, None,
                                a.stmt, stack[0])
            rests = {u for u in used if self.verdict_of.get(u, "PASS") != "PASS"}
            self._record(a.label, a.line, "PASS", fmt, count, rests=rests)
        except ProofFail as f:
            self._record(a.label, a.line, "FAIL", fmt, count, fail=f)
        except ProofVoid as v:
            self._record(a.label, a.line, "VOID", fmt, count, void_reason=str(v))
        except Exception as e:             # fail closed
            self._record(a.label, a.line, "VOID", fmt, count,
                         void_reason=f"internal: {type(e).__name__}: {e}")

    @staticmethod
    def _apply(expr, subst):
        out = []
        for s in expr:
            r = subst.get(s)
            if r is None:
                out.append(s)
            else:
                out.extend(r)
        return tuple(out)

    # ---- report ---------------------------------------------------------
    def report(self, path=None, seconds=None):
        counts = {v: sum(1 for r in self.theorems if r["verdict"] == v)
                  for v in ("PASS", "FAIL", "VOID")}
        return {"tool": VERSION, "input": path,
                "counts": counts,
                "file_void": self.file_void,
                "whole_file_read": self.file_void is None and self.stopped is None,
                "stopped": self.stopped,
                "lines_read": self.line, "statements_read": self.statements_read,
                "constants": len(self.constants),
                "axioms": {"count": len(self.axioms), "status": "OBSERVED",
                           "note": "given input; no verdict"},
                "provable_statements": len(self.theorems),
                "pass_resting_on_non_pass": sum(1 for r in self.theorems
                                                if r["verdict"] == "PASS"
                                                and r["rests_on_non_pass"]),
                "verified_here": sum(1 for r in self.theorems if r["verified_here"]),
                "carried_from_snapshot": sum(1 for r in self.theorems
                                             if not r["verified_here"]),
                "snapshot": None if self.carry is None else {
                    "theorem": self.carry["label"], "index": self.carry["index"],
                    "prefix_sha256": self.carry["prefix_sha256"], "state": "MATCHED"},
                "compressed": sum(1 for r in self.theorems
                                  if r["proof_format"] == "compressed"),
                "proof_steps": sum(r["steps"] or 0 for r in self.theorems),
                "seconds": seconds,
                "axiom_records": self.axioms, "theorem_records": self.theorems,
                "human_interest": None, "ai_interest": None}


def check_lines(lines, **kw):
    return Database().read(lines, **kw)


def prefix_sha256(path, lines):
    """sha256 of the first `lines` lines of the file, bytes as stored. None if the
    file has fewer lines."""
    h = hashlib.sha256()
    n = 0
    with open(path, encoding="utf-8", errors="strict", newline="") as f:
        for line in f:
            if n == lines:
                break
            h.update(line.encode("utf-8"))
            n += 1
    return h.hexdigest() if n == lines else None


def check_file(path, **kw):
    return run_file(path, **kw)[0]


def run_file(path, hashing=False, snapshot=None, **kw):
    """snapshot: a snapshot record (kernel/snapshot.py). Its prefix is re-read and
    hashed first; a different hash or kernel version makes the run VOID, with
    nothing verified. Otherwise the prefix's theorems are carried, not verified."""
    t0 = time.perf_counter()
    db = Database()
    db.hashing = hashing
    try:
        if snapshot is not None:
            why = None
            if snapshot.get("kernel_version") != VERSION:
                why = (f"snapshot {snapshot.get('theorem')}: kernel version "
                       f"{snapshot.get('kernel_version')!r}, this kernel is {VERSION!r}")
            elif snapshot.get("verdict") != "PASS":
                why = f"snapshot {snapshot.get('theorem')}: its verdict is not PASS"
            elif prefix_sha256(path, snapshot["prefix_lines"]) != snapshot["prefix_sha256"]:
                why = (f"snapshot {snapshot['theorem']}: the first "
                       f"{snapshot['prefix_lines']} lines do not hash to the stored sha256")
            if why is not None:
                db.file_void = {"reason": why, "line": None}
                rep = db.report(str(path), time.perf_counter() - t0)
                rep["snapshot"] = {"theorem": snapshot.get("theorem"), "state": "VOID",
                                   "reason": why}
                return rep, db
            db.carry = {"label": snapshot["theorem"], "index": snapshot["theorem_index"],
                        "statement": snapshot["statement"],
                        "prefix_sha256": snapshot["prefix_sha256"],
                        "non_pass": snapshot.get("prefix_non_pass", {})}
        with open(path, encoding="utf-8", errors="strict", newline="") as f:
            db.read(f, **kw)
    except UnicodeDecodeError as e:
        db.file_void = {"reason": f"not UTF-8 / ASCII text: {e.reason}", "line": None}
    return db.report(str(path), time.perf_counter() - t0), db
