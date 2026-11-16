"""axiom_audit -- look at the axioms a kernel PASS rests on. Co-authored.

  python3 -m kernel.axiom_audit [tests/data/algebra.mm] [--setmm PATH] [--json]

Nothing here makes an axiom true. It reports, per $a statement:

  class        syntax (term / wff former) | propositional | equational
               (|- A = B, no hypotheses, no condition) | conditional
  step 2       equational: the statement is turned into a numcheck formula
               and given to numcheck's polynomial-identity proof.
                 DERIVED          a polynomial identity, proved on a full grid
                 HOLDS            no variables; exact arithmetic
                 not polynomial   left for step 3
                 FAILS            the two sides differ
               propositional: a truth table over every assignment. That is a
               proof too: DERIVED, method truth_table.
  step 3       conditional, and whatever step 2 could not take: the statement
               is evaluated at sampled exact points (0, negatives, the sqrt
               and division edges). EVIDENCE ONLY: status PROPOSED.
               Where a term has no value (division by 0, sqrt below 0, a
               power that is not a numeral 0..9) it is given an arbitrary
               value, twice, under two different fill-ins. An axiom that is
               false under either is saying something about a value that
               does not exist: FAILS.
  set.mm map   the set.mm statement the axiom corresponds to, by label, with
               its text quoted from a set.mm file when --setmm is given.
                 EXACT    the same statement
                 TYPED    the same statement under set.mm's A e. CC / A e. RR
                          antecedents (algebra.mm has one sort: real numbers)
                 IMPLIED  follows from the named set.mm statement(s), which
                          are stronger or packaged differently
                 SYNTAX   a syntax statement with a set.mm counterpart
                 UNMAPPED none named
  mutation     each equational axiom with one operator or numeral changed
               must come out FAILS in step 2; the ones that do not are listed.
"""
import itertools
import json
import re
import sys
from fractions import Fraction
from pathlib import Path

from numcheck import interval as I
from numcheck.check import check_point

from .mm import check_lines

DEFAULT = Path(__file__).resolve().parents[1] / "tests" / "data" / "algebra.mm"
QUOTES = Path(__file__).resolve().parents[1] / "REFERENCES" / "setmm_quotes.json"
OPS = ("+", "-", "*", "/", "^")
SAMPLES = [Fraction(x) for x in ("-2", "-1", "-1/2", "0", "1/2", "1", "2", "9/4", "4")]
FILLS = ({"name": "A", "div0": lambda t: Fraction(0), "sqrtneg": lambda t: Fraction(0),
          "pow": lambda t, s: Fraction(0)},
         {"name": "B", "div0": lambda t: t + 7, "sqrtneg": lambda t: Fraction(-3),
          "pow": lambda t, s: Fraction(5)})

# label in algebra.mm -> (relation, set.mm labels, note)
SETMM = {
    "ax-mp": ("EXACT", ["ax-mp"], None), "ax-1": ("EXACT", ["ax-1"], None),
    "ax-2": ("EXACT", ["ax-2"], None), "ax-3": ("EXACT", ["ax-3"], None),
    "ax-simpl": ("EXACT", ["simpl"], "a theorem in set.mm, an axiom here"),
    "ax-simpr": ("EXACT", ["simpr"], "a theorem in set.mm, an axiom here"),
    "ax-conj": ("EXACT", ["pm3.2"], "a theorem in set.mm, an axiom here"),
    "eqid": ("EXACT", ["eqid"], None),
    "eqcom": ("IMPLIED", ["eqcom"], "set.mm states the two-way form"),
    "eqtr": ("EXACT", ["eqtr"], None),
    "addeq1": ("IMPLIED", ["oveq1"], "oveq1 with F := +"),
    "addeq2": ("IMPLIED", ["oveq2"], "oveq2 with F := +"),
    "subeq1": ("IMPLIED", ["oveq1"], "oveq1 with F := -"),
    "subeq2": ("IMPLIED", ["oveq2"], "oveq2 with F := -"),
    "muleq1": ("IMPLIED", ["oveq1"], "oveq1 with F := x."),
    "muleq2": ("IMPLIED", ["oveq2"], "oveq2 with F := x."),
    "diveq1": ("IMPLIED", ["oveq1"], "oveq1 with F := /"),
    "diveq2": ("IMPLIED", ["oveq2"], "oveq2 with F := /"),
    "poweq1": ("IMPLIED", ["oveq1"], "oveq1 with F := ^"),
    "sqrteq": ("IMPLIED", ["fveq2"], "fveq2 with F := sqrt"),
    "negeq": ("EXACT", ["negeq"], None),
    "leeq1": ("IMPLIED", ["breq1"], "breq1 with R := <_ ; set.mm states the two-way form"),
    "leeq2": ("IMPLIED", ["breq2"], "breq2 with R := <_ ; set.mm states the two-way form"),
    "addcom": ("TYPED", ["addcom"], None), "addass": ("TYPED", ["addass"], None),
    "add0": ("TYPED", ["addrid"], None), "addneg": ("TYPED", ["negid"], None),
    "subdef": ("TYPED", ["negsub"], "set.mm writes the equation the other way round"),
    "mulcom": ("TYPED", ["mulcom"], None), "mulass": ("TYPED", ["mulass"], None),
    "mul1": ("TYPED", ["mulrid"], None), "distr": ("TYPED", ["adddi"], None),
    "divmul": ("TYPED", ["divcan1"], "set.mm writes B =/= 0 for -. B = 0"),
    "ne01": ("IMPLIED", ["0ne1"], "set.mm writes 0 =/= 1"),
    "exp0": ("TYPED", ["exp0"], None), "exp1": ("TYPED", ["exp1"], None),
    "exp2": ("TYPED", ["sqval"], None),
    "leid": ("TYPED", ["leid"], None), "letr": ("TYPED", ["letr"], None),
    "letot": ("IMPLIED", ["letric"], "letric states A <_ B \\/ B <_ A"),
    "leasym": ("IMPLIED", ["letri3"], "letri3 states the two-way form"),
    "leadd": ("IMPLIED", ["leadd1"], "leadd1 states the two-way form"),
    "lemul": ("TYPED", ["mulge0"], None), "le01": ("EXACT", ["0le1"], None),
    "sqrtsq": ("TYPED", ["remsqsqrt"], None), "sqrtge0": ("TYPED", ["sqrtge0"], None),
    "n0": ("SYNTAX", ["cc0"], None), "tneg": ("SYNTAX", ["cneg"], None),
    "weq": ("SYNTAX", ["wceq"], None), "wle": ("SYNTAX", ["wbr", "cle"], "wbr with R := <_"),
    "wn": ("SYNTAX", ["wn"], None), "wi": ("SYNTAX", ["wi"], None), "wa": ("SYNTAX", ["wa"], None),
    "tadd": ("SYNTAX", ["co", "caddc"], "co with F := +"),
    "tsub": ("SYNTAX", ["co", "cmin"], "co with F := -"),
    "tmul": ("SYNTAX", ["co", "cmul"], "co with F := x."),
    "tdiv": ("SYNTAX", ["co", "cdiv"], "co with F := /"),
    "tpow": ("SYNTAX", ["co", "cexp"], "co with F := ^"),
    "tsqrt": ("SYNTAX", ["cfv", "csqrt"], "cfv with F := sqrt"),
}
for _n in range(1, 10):
    SETMM[f"n{_n}"] = ("SYNTAX", [f"c{_n}"], None)
for _n in range(2, 10):
    SETMM[f"df-{_n}"] = ("EXACT", [f"df-{_n}"], None)
for _n in range(3, 10):
    SETMM[f"exp{_n}"] = ("IMPLIED", ["expp1", f"df-{_n}"],
                         f"expp1 with N := {_n - 1}, and df-{_n}")


class ParseError(Exception):
    pass


class Reader:
    """Token list -> a small tree. term: ("num", n) ("var", v) ("neg", a)
    ("sqrt", a) (op, a, b).  wff: ("wvar", p) ("not", a) ("->", a, b)
    ("and", a, b) ("=", a, b) ("<=", a, b)."""

    def __init__(self, toks, term_vars, wff_vars):
        self.t, self.tv, self.wv = toks, term_vars, wff_vars

    def term(self, i):
        tok = self.t[i]
        if tok.isdigit():
            return ("num", int(tok)), i + 1
        if tok in self.tv:
            return ("var", tok), i + 1
        if tok == "-u":
            a, j = self.term(i + 1)
            return ("neg", a), j
        if tok == "(":
            if self.t[i + 1] == "sqrt":
                a, j = self.term(i + 2)
                self._close(j)
                return ("sqrt", a), j + 1
            a, j = self.term(i + 1)
            if self.t[j] not in OPS:
                raise ParseError(f"operator expected at {j}")
            b, k = self.term(j + 1)
            self._close(k)
            return (self.t[j], a, b), k + 1
        raise ParseError(f"term expected at {i}: {tok}")

    def _close(self, i):
        if i >= len(self.t) or self.t[i] != ")":
            raise ParseError(f") expected at {i}")

    def wff(self, i):
        tok = self.t[i]
        if tok == "-.":
            a, j = self.wff(i + 1)
            return ("not", a), j
        if tok in self.wv:
            return ("wvar", tok), i + 1
        if tok == "(":
            try:
                a, j = self.wff(i + 1)
                if self.t[j] in ("->", "/\\"):
                    b, k = self.wff(j + 1)
                    self._close(k)
                    return ("->" if self.t[j] == "->" else "and", a, b), k + 1
            except (ParseError, IndexError):
                pass
        a, j = self.term(i)
        if self.t[j] not in ("=", "<_"):
            raise ParseError(f"= or <_ expected at {j}")
        b, k = self.term(j + 1)
        return ("=" if self.t[j] == "=" else "<=", a, b), k

    def whole_wff(self):
        tree, j = self.wff(0)
        if j != len(self.t):
            raise ParseError("tokens left over")
        return tree


def names(tree, kind):
    if tree[0] == kind:
        return {tree[1]}
    out = set()
    for x in tree[1:]:
        if isinstance(x, tuple):
            out |= names(x, kind)
    return out


def to_python(t):
    """A term tree as a numcheck expression string."""
    k = t[0]
    if k == "num":
        return str(t[1])
    if k == "var":
        return t[1]
    if k == "neg":
        return f"(-{to_python(t[1])})"
    if k == "sqrt":
        return f"sqrt({to_python(t[1])})"
    if k == "^":
        if t[2][0] != "num":
            raise ParseError("an exponent that is not a numeral")
        return f"({to_python(t[1])}**{t[2][1]})"
    return f"({to_python(t[1])} {k} {to_python(t[2])})"


# ---- step 2 -------------------------------------------------------------------
def step2_equation(lhs, rhs):
    """numcheck on lhs = rhs at tolerance 0, variables ranging over [-3, 5]."""
    try:
        formula = f"{to_python(lhs)} = {to_python(rhs)}"
    except ParseError as e:
        return {"result": "not polynomial", "reason": str(e), "formula": None}
    vs = sorted(names(lhs, "var") | names(rhs, "var"))
    rec = check_point({"formula": formula, "tolerance": "0",
                       "values": {v: {"value": ["-3", "5"], "unit": "1"} for v in vs}})
    out = {"formula": formula, "numcheck_verdict": rec["verdict"],
           "void_reason": rec["void_reason"]}
    p = rec.get("proposal")
    if rec["verdict"] == "HOLDS":
        return {**out, "result": "HOLDS", "status": "DERIVED",
                "method": "exact arithmetic, no variables" if not vs else "interval tier"}
    if rec["verdict"] == "UNDECIDED" and p and p["status"] == "DERIVED":
        return {**out, "result": "DERIVED", "status": "DERIVED",
                "method": p["proof"]["method"], "degrees": p["proof"]["degrees"],
                "grid_size": p["proof"]["grid_size"]}
    if rec["verdict"] == "UNDECIDED" and p:
        return {**out, "result": "not polynomial", "reason": p["why_not_proved"]}
    if rec["verdict"] == "VOID":
        return {**out, "result": "not polynomial", "reason": rec["void_reason"]}
    return {**out, "result": "FAILS",
            "reason": "the two sides differ" + (
                "" if rec["verdict"] == "UNDECIDED" else f" (numcheck {rec['verdict']})"),
            "located": rec.get("located")}


def truth_table(conclusion, hyps):
    vs = sorted(set().union(names(conclusion, "wvar"), *[names(h, "wvar") for h in hyps]))
    rows = 0
    for bits in itertools.product((True, False), repeat=len(vs)):
        env = dict(zip(vs, bits))
        rows += 1
        if all(_bool(h, env) for h in hyps) and not _bool(conclusion, env):
            return {"result": "FAILS", "counterexample": env, "rows": rows}
    return {"result": "DERIVED", "status": "DERIVED", "method": "truth_table", "rows": rows,
            "variables": vs}


def _bool(w, env):
    k = w[0]
    if k == "wvar":
        return env[w[1]]
    if k == "not":
        return not _bool(w[1], env)
    if k == "->":
        return (not _bool(w[1], env)) or _bool(w[2], env)
    return _bool(w[1], env) and _bool(w[2], env)


# ---- step 3 -------------------------------------------------------------------
def _val(t, env, fill, prec=30):
    """An Interval enclosing the term's value at a point (exact unless a sqrt
    of a non-square came in)."""
    k = t[0]
    if k == "num":
        return I.Interval(t[1])
    if k == "var":
        return I.Interval(env[t[1]])
    if k == "neg":
        return -_val(t[1], env, fill)
    if k == "sqrt":
        a = _val(t[1], env, fill)
        if a.hi < 0:
            return I.Interval(fill["sqrtneg"](a.lo))
        if a.lo < 0:
            raise _Unknown()
        return I.sqrt(a, prec)
    a, b = _val(t[1], env, fill), _val(t[2], env, fill)
    if k == "+":
        return a + b
    if k == "-":
        return a - b
    if k == "*":
        return a * b
    if k == "/":
        if b.is_point and b.lo == 0:
            return I.Interval(fill["div0"](a.lo))
        if b.contains(0):
            raise _Unknown()
        return a / b
    if b.is_point and b.lo.denominator == 1 and 0 <= b.lo <= 9:      # ^ with a numeral value
        return a.powi(int(b.lo))
    return I.Interval(fill["pow"](a.lo, b.lo))


class _Unknown(Exception):
    pass


class Surd:
    """c * sqrt(n): c a non-zero Fraction, n a square-free integer > 1. Exact.
    Enough to decide the sqrt samples: products, and comparisons by squaring."""
    __slots__ = ("c", "n")

    def __init__(self, c, n):
        self.c, self.n = c, n


def exact_sqrt(x):
    """sqrt of a Fraction >= 0 as a Fraction or a Surd."""
    num = x.numerator * x.denominator            # sqrt(p / q) = sqrt(p q) / q
    out, n, d = 1, num, 2
    while d * d <= n:
        while n % (d * d) == 0:
            n //= d * d
            out *= d
        d += 1
    c = Fraction(out, x.denominator)
    return c if n == 1 else (Fraction(0) if num == 0 else Surd(c, n))


def _xmul(a, b):
    if isinstance(a, Surd) and isinstance(b, Surd):
        r = exact_sqrt(Fraction(a.n * b.n))
        return a.c * b.c * r if isinstance(r, Fraction) else Surd(a.c * b.c * r.c, r.n)
    if isinstance(a, Surd):
        return Surd(a.c * b, a.n) if b else Fraction(0)
    if isinstance(b, Surd):
        return Surd(b.c * a, b.n) if a else Fraction(0)
    return a * b


def _sign(a):
    c = a.c if isinstance(a, Surd) else a
    return (c > 0) - (c < 0)


def _square(a):
    return a.c * a.c * a.n if isinstance(a, Surd) else a * a


def _xcmp(a, b):
    """-1, 0, 1 as a < b, a = b, a > b; exact, by signs and then squares."""
    sa, sb = _sign(a), _sign(b)
    if sa != sb:
        return -1 if sa < sb else 1
    if sa == 0:
        return 0
    qa, qb = _square(a), _square(b)
    return 0 if qa == qb else ((-1 if qa < qb else 1) * sa)


def _xval(t, env, fill):
    """The term's exact value at a point: a Fraction or a Surd. Raises _Unknown
    for what this small arithmetic does not cover (a sum with a surd in it)."""
    k = t[0]
    if k == "num":
        return Fraction(t[1])
    if k == "var":
        return env[t[1]]
    if k == "neg":
        a = _xval(t[1], env, fill)
        return Surd(-a.c, a.n) if isinstance(a, Surd) else -a
    if k == "sqrt":
        a = _xval(t[1], env, fill)
        if isinstance(a, Surd):
            raise _Unknown()
        return fill["sqrtneg"](a) if a < 0 else exact_sqrt(a)
    a, b = _xval(t[1], env, fill), _xval(t[2], env, fill)
    if k == "*":
        return _xmul(a, b)
    if isinstance(a, Surd) or isinstance(b, Surd):
        raise _Unknown()
    if k == "+":
        return a + b
    if k == "-":
        return a - b
    if k == "/":
        return fill["div0"](a) if b == 0 else a / b
    if b.denominator == 1 and 0 <= b <= 9:
        return a ** int(b)
    return fill["pow"](a, b)


def _truth(w, env, fill):
    """True / False / None (not decided: an enclosure straddles)."""
    k = w[0]
    if k == "wvar":
        return env[w[1]]
    if k == "not":
        v = _truth(w[1], env, fill)
        return None if v is None else not v
    if k in ("->", "and"):
        a, b = _truth(w[1], env, fill), _truth(w[2], env, fill)
        if k == "->":
            if a is False or b is True:
                return True
            return False if (a is True and b is False) else None
        if a is False or b is False:
            return False
        return True if (a is True and b is True) else None
    try:                                    # exact first: sqrt compared by squaring
        c = _xcmp(_xval(w[1], env, fill), _xval(w[2], env, fill))
        return c == 0 if k == "=" else c <= 0
    except _Unknown:
        pass
    try:
        a, b = _val(w[1], env, fill), _val(w[2], env, fill)
    except _Unknown:
        return None
    if k == "=":
        if a.is_point and b.is_point:
            return a.lo == b.lo
        return False if (a.hi < b.lo or b.hi < a.lo) else None
    if a.hi <= b.lo:
        return True
    return False if a.lo > b.hi else None


def step3_samples(conclusion, hyps):
    tv = sorted(set().union(names(conclusion, "var"), *[names(h, "var") for h in hyps]))
    wv = sorted(set().union(names(conclusion, "wvar"), *[names(h, "wvar") for h in hyps]))
    counts = {"true": 0, "not_decided": 0, "false": 0, "hypotheses_not_met": 0}
    first_false = None
    for fill in FILLS:
        for vals in itertools.product(SAMPLES, repeat=len(tv)):
            for bits in itertools.product((True, False), repeat=len(wv)):
                env = dict(zip(tv, vals), **dict(zip(wv, bits)))
                hs = [_truth(h, env, fill) for h in hyps]
                if any(h is False for h in hs):
                    counts["hypotheses_not_met"] += 1
                    continue
                c = _truth(conclusion, env, fill)
                if c is False and all(h is True for h in hs):
                    counts["false"] += 1
                    first_false = first_false or {
                        "fill_in": fill["name"],
                        "at": {k: str(v) for k, v in env.items()}}
                elif c is True:
                    counts["true"] += 1
                else:
                    counts["not_decided"] += 1
    return {"result": "FAILS" if counts["false"] else "no counterexample",
            "status": None if counts["false"] else "PROPOSED",
            "evidence_only": True, "samples": counts, "first_counterexample": first_false,
            "sample_values": [str(x) for x in SAMPLES], "term_variables": tv,
            "fill_ins": "undefined values (x / 0, sqrt below 0, a power that is not a "
                        "numeral 0..9) are given two different arbitrary values; the "
                        "statement must hold under both"}


# ---- the audit ------------------------------------------------------------------
def _setmm_text(path):
    text = Path(path).read_text(encoding="utf-8")
    return re.sub(r"\$\(.*?\$\)", " ", text, flags=re.S)


def _quote(clean, label):
    m = re.search(r"(?<!\S)%s \$([ap]) ([^$]*)\$" % re.escape(label), clean)
    if not m:
        return None
    hyps = []
    block = clean.rfind("${", 0, m.start())
    close = clean.rfind("$}", 0, m.start())
    if block > close:                                   # essential hypotheses in its scope
        hyps = [" ".join(h.split()) for h in
                re.findall(r"\$e ([^$]*)\$\.", clean[block:m.start()])]
    return {"label": label, "kind": "$" + m.group(1), "statement": " ".join(m.group(2).split()),
            "hypotheses": hyps}


TYPING = re.compile(r"^\S+ e\. (CC|RR|NN0|NN|ZZ|RR\*)$")
RENAME = {"A": "t", "B": "r", "C": "s", "x.": "*"}


def _depth_split(toks, seps):
    """Split a token list at separators standing at parenthesis depth 0."""
    parts, cur, depth = [], [], 0
    for t in toks:
        if t == "(":
            depth += 1
        elif t == ")":
            depth -= 1
        if depth == 0 and t in seps:
            parts.append(cur)
            cur = []
        else:
            cur.append(t)
    parts.append(cur)
    return parts


def _conjuncts(toks):
    if toks and toks[0] == "(" and toks[-1] == ")":
        inner = _depth_split(toks[1:-1], ("/\\",))
        if len(inner) > 1:
            return [c for part in inner for c in _conjuncts(part)]
    return [toks]


def antecedents(toks):
    """Every antecedent along the chain ( X -> ( Y -> Z ) ), conjunctions opened."""
    out = []
    while toks and toks[0] == "(" and toks[-1] == ")":
        parts = _depth_split(toks[1:-1], ("->",))
        if len(parts) != 2:
            break
        out += _conjuncts(parts[0])
        toks = parts[1]
    return [" ".join(x) for x in out]


def _to_algebra(guard):
    """A set.mm antecedent in algebra.mm's notation: A B C -> t r s, x. -> *,
    ( sqrt ` A ) -> ( sqrt A ), X =/= Y -> -. X = Y."""
    toks = [RENAME.get(t, t) for t in guard.split() if t != "`"]
    if "=/=" in toks:
        i = toks.index("=/=")
        toks = ["-."] + toks[:i] + ["="] + toks[i + 1:]
    return " ".join(toks)


def guard_row(a_rec, quoted):
    """algebra.mm's guards beside set.mm's antecedents, for one axiom."""
    stmt = a_rec["statement"].split()[1:]
    mine = antecedents(stmt) + [h.split(" ", 1)[1] for h in a_rec["hypotheses"]]
    row = {"label": a_rec["label"], "class": a_rec["class"],
           "relation": a_rec["setmm"]["relation"], "algebra_statement": a_rec["statement"],
           "algebra_guards": mine, "setmm": [], "setmm_typing": [], "setmm_guards": [],
           "not_covered": [], "verdict": None, "reason": None}
    if not quoted or any(q is None for q in quoted):
        row.update(verdict="UNCLEAR", reason="no set.mm statement to set it beside")
        return row
    for q in quoted:
        row["setmm"].append(f"{q['label']} {q['kind']} {q['statement']}"
                            + (" given " + " ; ".join(q["hypotheses"]) if q["hypotheses"] else ""))
        if q["kind"] == "$a" and q["label"].startswith("df-"):
            continue                                 # a definition: no antecedent
        theirs = antecedents(q["statement"].split()[1:]) \
            + [h.split(" ", 1)[1] for h in q["hypotheses"]]
        for g in theirs:
            if TYPING.match(g):
                row["setmm_typing"].append(g)
            else:
                row["setmm_guards"].append(g)
                if _to_algebra(g) not in mine:
                    row["not_covered"].append({"setmm": g, "as_algebra": _to_algebra(g)})
    if row["not_covered"]:
        row.update(verdict="GUARD_WEAKER",
                   reason="a set.mm antecedent has no counterpart among algebra.mm's guards")
    else:
        row.update(verdict="GUARD_OK",
                   reason=("set.mm has typing antecedents only" if row["setmm_typing"]
                           and not row["setmm_guards"] else
                           "no antecedent in set.mm" if not row["setmm_guards"] else
                           "every set.mm antecedent is among algebra.mm's guards")
                   + ("; algebra.mm guards more" if len(mine) > len(row["setmm_guards"])
                      and row["setmm_guards"] else ""))
    return row


def classify(stmt, hyps_e):
    if stmt[0] != "|-":
        return "syntax"
    return None


def audit_axiom(a, term_vars, wff_vars, setmm=None):
    stmt = list(a.stmt)
    hyps_e = [list(e) for k, _, e in a.hyps if k == "e"]
    rec = {"label": a.label, "line": a.line, "statement": " ".join(stmt),
           "hypotheses": [" ".join(h) for h in hyps_e], "class": None,
           "kernel_status": "OBSERVED", "kernel_verdict": None,
           "step2": None, "step3": None, "verdict": None}
    rel, labels, note = SETMM.get(a.label, ("UNMAPPED", [], None))
    rec["setmm"] = {"relation": rel, "labels": labels, "note": note,
                    "quoted": None if setmm is None else [_quote(setmm, x) for x in labels]}
    if stmt[0] != "|-":
        rec.update({"class": "syntax", "verdict": "n/a (syntax)"})
        return rec
    read = lambda toks: Reader(toks[1:], term_vars, wff_vars).whole_wff()   # noqa: E731
    try:
        concl, hyps = read(stmt), [read(h) for h in hyps_e]
    except (ParseError, IndexError) as e:
        rec.update({"class": "unreadable", "verdict": "VOID", "void_reason": str(e)})
        return rec
    has_terms = bool(names(concl, "var") or any(names(h, "var") for h in hyps)) \
        or _has_relation(concl) or any(_has_relation(h) for h in hyps)
    if not has_terms:
        rec["class"] = "propositional"
        rec["step2"] = truth_table(concl, hyps)
    elif concl[0] == "=" and not hyps:
        rec["class"] = "equational"
        rec["step2"] = step2_equation(concl[1], concl[2])
    else:
        rec["class"] = "conditional"
    if rec["step2"] is None or rec["step2"]["result"] == "not polynomial":
        rec["step3"] = step3_samples(concl, hyps)
    results = [x["result"] for x in (rec["step2"], rec["step3"]) if x]
    rec["verdict"] = ("FAILS" if "FAILS" in results else
                      "DERIVED" if results[0] in ("DERIVED", "HOLDS") else
                      "PROPOSED (sampled, no counterexample)")
    return rec


def _has_relation(w):
    if w[0] in ("=", "<="):
        return True
    return any(_has_relation(x) for x in w[1:] if isinstance(x, tuple))


def _mutations(tree):
    """Every tree got by changing one operator or one numeral of a term tree."""
    k = tree[0]
    if k == "num":
        yield ("num", tree[1] + 1 if tree[1] < 9 else tree[1] - 1)
    elif k in ("+", "-", "*"):
        yield ({"+": "-", "-": "+", "*": "+"}[k], tree[1], tree[2])
    if k in OPS:
        for m in _mutations(tree[1]):
            yield (k, m, tree[2])
        if k != "^":                                    # an exponent stays a numeral
            for m in _mutations(tree[2]):
                yield (k, tree[1], m)
    elif k in ("neg", "sqrt"):
        for m in _mutations(tree[1]):
            yield (k, m)


def mutation_run(db, term_vars, wff_vars):
    rows, missed = [], []
    for a in db.assertions.values():
        if a.kind != "a" or a.stmt[0] != "|-" or any(k == "e" for k, _, _ in a.hyps):
            continue
        try:
            w = Reader(list(a.stmt[1:]), term_vars, wff_vars).whole_wff()
        except (ParseError, IndexError):
            continue
        if w[0] != "=":
            continue
        base = step2_equation(w[1], w[2])
        if base["result"] not in ("DERIVED", "HOLDS"):
            continue
        n = caught = 0
        for side in (1, 2):
            for m in _mutations(w[side]):
                lhs, rhs = (m, w[2]) if side == 1 else (w[1], m)
                r = step2_equation(lhs, rhs)
                n += 1
                if r["result"] == "FAILS":
                    caught += 1
                else:
                    missed.append({"label": a.label, "mutant": r["formula"],
                                   "result": r["result"]})
        rows.append({"label": a.label, "mutants": n, "caught": caught})
    return {"axioms_mutated": len(rows), "mutants": sum(r["mutants"] for r in rows),
            "caught": sum(r["caught"] for r in rows), "not_caught": missed, "per_axiom": rows}


def audit(db_path=DEFAULT, setmm_path=None):
    text = Path(db_path).read_text(encoding="utf-8")
    db = check_lines(text.splitlines())
    if db.file_void:
        return {"file_void": db.file_void, "axioms": []}
    term_vars = {e[1] for k, e in db.active_hyps.values() if k == "f" and e[0] == "term"}
    wff_vars = {e[1] for k, e in db.active_hyps.values() if k == "f" and e[0] == "wff"}
    setmm = _setmm_text(setmm_path) if setmm_path else None
    axioms = [audit_axiom(a, term_vars, wff_vars, setmm)
              for a in db.assertions.values() if a.kind == "a"]
    quotes_source = "the set.mm file given" if setmm else None
    if setmm is None and QUOTES.exists():          # the quotes recorded from an earlier run
        recorded = json.loads(QUOTES.read_text(encoding="utf-8"))
        quotes_source = f"{QUOTES.name}: {recorded['setmm']}"
        for a in axioms:
            a["setmm"]["quoted"] = [recorded["quotes"].get(x) for x in a["setmm"]["labels"]]
    guards = [guard_row(a, a["setmm"]["quoted"]) for a in axioms
              if a["class"] == "conditional"
              or (a["class"] != "syntax" and a["setmm"]["relation"] in ("TYPED", "IMPLIED"))]
    weaker = [g["label"] for g in guards if g["verdict"] == "GUARD_WEAKER"]
    unclear = [g["label"] for g in guards if g["verdict"] == "UNCLEAR"]
    all_ok = bool(guards) and not weaker and not unclear
    fails = [a["label"] for a in axioms if a["verdict"] == "FAILS"]
    if all_ok and not fails:
        for a in axioms:                             # truth in the model, via the map
            if a["class"] == "conditional":
                a["truth_in_model"] = {"status": "DERIVED", "via": a["setmm"]["labels"],
                                       "rests_on": "the set.mm statement(s) named, the guard "
                                                   "table row, and the sampled check"}
    consistency = {
        "status": "DERIVED" if all_ok and not fails else None,
        "argument": "a model: the real numbers, with x / 0, sqrt below 0 and non-numeral "
                    "powers given fixed values. Every axiom is true in it (equational: "
                    "polynomial identity or exact arithmetic; propositional: truth table; "
                    "conditional: the set.mm statement it maps to, guards compared in the "
                    "guard table, plus the sampled check under two fill-ins). Axioms with a "
                    "model do not contradict each other.",
        "rests_on": "the guard table and the set.mm map",
        "relative_to": "the real numbers as set.mm has them",
        "blocked_by": weaker + unclear + fails,
        "second_reader": "VOID",
        "second_reader_note": "the map and the guard table were made by one reader (this "
                              "build). The slot is for a pass by a different model or person; "
                              "it is empty."}
    count = lambda f: sum(1 for a in axioms if f(a))                       # noqa: E731
    return {"database": str(db_path), "setmm": setmm_path, "file_void": None,
            "quotes_source": quotes_source,
            "axioms": axioms, "guard_table": guards, "consistency": consistency,
            "mutation": mutation_run(db, term_vars, wff_vars),
            "summary": {
                "statements": len(axioms),
                "by_class": {c: count(lambda a: a["class"] == c)
                             for c in ("syntax", "propositional", "equational", "conditional")},
                "DERIVED": count(lambda a: a["verdict"] == "DERIVED"),
                "PROPOSED_sampled": count(lambda a: str(a["verdict"]).startswith("PROPOSED")),
                "FAILS": fails,
                "guard_rows": len(guards),
                "guard_verdicts": {v: sum(1 for g in guards if g["verdict"] == v)
                                   for v in ("GUARD_OK", "GUARD_WEAKER", "UNCLEAR")},
                "GUARD_WEAKER": weaker, "UNCLEAR": unclear,
                "seam_pass_route": "OPEN" if all_ok and not fails else "BLOCKED",
                "consistency_status": consistency["status"],
                "second_reader": "VOID",
                "samples_not_decided": sum(a["step3"]["samples"]["not_decided"]
                                           for a in axioms if a["step3"]),
                "setmm_relation": {r: count(lambda a: a["setmm"]["relation"] == r)
                                   for r in ("EXACT", "TYPED", "IMPLIED", "SYNTAX", "UNMAPPED")},
                "UNMAPPED": [a["label"] for a in axioms
                             if a["setmm"]["relation"] == "UNMAPPED"],
                "setmm_labels_not_found": [] if setmm is None else sorted(
                    {l for a in axioms for l, q in zip(a["setmm"]["labels"],
                                                       a["setmm"]["quoted"]) if q is None})},
            "human_interest": None, "ai_interest": None}


def main(argv):
    path = next((x for x in argv if not x.startswith("--") and x.endswith(".mm")
                 and (argv.index(x) == 0 or argv[argv.index(x) - 1] != "--setmm")), DEFAULT)
    setmm = argv[argv.index("--setmm") + 1] if "--setmm" in argv else None
    rep = audit(path, setmm)
    if "--json" in argv:
        print(json.dumps(rep, indent=1, default=str))
        return 1 if rep["summary"]["seam_pass_route"] == "BLOCKED" else 0
    for a in rep["axioms"]:
        s2, s3, m = a["step2"], a["step3"], a["setmm"]
        line = f"{a['label']:9s} {a['class']:13s} {a['statement']}"
        if a["hypotheses"]:
            line += "   [" + " ; ".join(a["hypotheses"]) + "]"
        print(line)
        if s2:
            print(f"          step 2: {s2['result']}"
                  + (f" ({s2.get('method')}" + (f", degrees {s2['degrees']}, grid {s2['grid_size']}"
                                                if "degrees" in s2 else "") + ")"
                     if s2.get("method") else "")
                  + (f" -- {s2['reason']}" if s2.get("reason") else ""))
        if s3:
            c = s3["samples"]
            print(f"          step 3: {s3['result']}; true {c['true']}, not decided "
                  f"{c['not_decided']}, false {c['false']}"
                  + (f"; first false: {s3['first_counterexample']}" if c["false"] else ""))
        q = "; ".join(f"{x['label']} {x['kind']} {x['statement']}"
                      + (" [" + " ; ".join(x["hypotheses"]) + "]" if x["hypotheses"] else "")
                      for x in (m["quoted"] or []) if x) if m["quoted"] else ", ".join(m["labels"])
        print(f"          set.mm: {m['relation']}" + (f" -- {q}" if q else "")
              + (f"  ({m['note']})" if m["note"] else ""))
    for g in rep["guard_table"]:
        print(f"GUARD {g['verdict']:12s} {g['label']:9s} algebra: {g['algebra_guards'] or '-'}"
              f" | set.mm: {g['setmm_guards'] or '-'} | typing: {g['setmm_typing'] or '-'}"
              + (f" | NOT COVERED: {g['not_covered']}" if g["not_covered"] else ""))
    c = rep["consistency"]
    print(f"consistency: status {c['status']}; rests on {c['rests_on']}; second reader: "
          f"{c['second_reader']}; blocked by: {c['blocked_by'] or 'nothing'}")
    mu = rep["mutation"]
    print(f"mutation: {mu['mutants']} mutants of {mu['axioms_mutated']} equational axioms, "
          f"{mu['caught']} caught; not caught: {mu['not_caught']}")
    print("SUMMARY", json.dumps(rep["summary"]))
    return 1 if rep["summary"]["seam_pass_route"] == "BLOCKED" else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
