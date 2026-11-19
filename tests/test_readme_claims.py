"""README claim register: concrete examples in README.md, bound to behaviour.

Status: a register of README sentences that state a concrete, runnable result,
each paired with a check of what the code does. It fails if a quoted sentence
leaves the README (the prose changed: update the register) or if the code no
longer does what the sentence says (the code or the prose is wrong). Not
established: that every concrete example in the README is registered. Run

    python3 tests/test_readme_claims.py --hunt

to list README lines that look like concrete examples and are not covered by
any registered quote. Those lines are UNCHECKED, not wrong. The hunt's
selection rule is a heuristic (PROPOSED); it can miss examples and flag prose.
Co-authored. Stdlib only.
"""
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from numcheck import check_point, read_json  # noqa: E402
from unitaudit import check_formula  # noqa: E402
from glyph import read_environment  # noqa: E402
from infer import rank, record_sha  # noqa: E402
from numcheck import check_all  # noqa: E402
from kernel.bridge import prove  # noqa: E402
from tests.test_glyph import World  # noqa: E402  (real branch 1 / 2b / 4 reports)

README = ROOT / "README.md"


def norm(text):
    """Collapse whitespace so wrapped README lines match a one-line quote."""
    return re.sub(r"\s+", " ", text).strip()


def val(value, unit="1"):
    return {"value": value, "unit": unit, "status": None}


def point(formula, tolerance, **values):
    return check_point({"formula": formula, "tolerance": tolerance, "values": values})


def units(formula, **symbols):
    return check_formula({"formula": formula, "symbols": symbols})["verdict"]


def cli(*args):
    return subprocess.run([sys.executable, "-m", *args], cwd=ROOT,
                          capture_output=True, text=True).returncode


def kernel_on(text):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "t.mm"
        p.write_text(text)
        return cli("kernel", "check", str(p))


def tiers(r):
    return [t["predicted_verdict"] for t in r["tiers"][:2]]


def in_world(fn):
    """Run fn on a fresh World (temporary folder of real reports), then clean up."""
    w = World()
    try:
        return fn(w)
    finally:
        w.close()


def mixed_example():
    r = point("y = x", "0.1", y=val(0), x=val([0, 1]))
    b = r["bisection"]
    return (r["verdict"], bool(b["pieces_that_hold"]), bool(b["pieces_that_fail"]),
            "holds_elsewhere" in json.dumps(r))


def gain_missing(w):
    c = w.case("SOLVE", refs=[w.ref("2b", 0, 6, "1/2"), w.ref("4", 0, 6, "3")])
    del c["gain"]
    r = w.run(c)
    return r["verdict"], "gain undeclared" in r["void_reason"]


def analogy(w):
    refs = [w.ref("1", i, 1) for i in range(3)] + [w.ref("2b", 0, 2), w.ref("4", 0, 3)]
    shared = read_environment(refs, w.dir)["features"]["shared_dims"]
    c = w.case(refs=refs, energy_budget={"available": "30", "reserve": "1"},
               time_budget={"available": "30", "reserve": "1"})
    first = w.run(c)["log"][1]["chosen"]
    p = next(p for p in w.proposals()["proposals"]
             if p["glyph"]["tool"] == "dimensional_analogy")
    return len(shared), shared[0]["dimension"], first, (p["lhs"], p["rhs"]), p["status"]


def mixed_region(w):
    feats = lambda refs: read_environment(refs, w.dir)["features"]["mixed_region"]
    return (w.reports["2b"]["records"][0]["verdict"], len(feats([w.ref("2b", 0, 1)])),
            w.reports["2b"]["records"][1]["verdict"], len(feats([w.ref("2b", 1, 1)])))


def seam(w):
    ev = {"id": "e", "type": "direct", "hypothesis": "boundary_probe", "lr": "5",
          "provenance": "p", "shared_ancestry": [], "status": "OBSERVED"}
    w.run(w.case("SOLVE", evidence=[ev]))
    data = w.proposals()
    rep = prove(w.dir / "proposals.json")
    return (data["proposals"][0]["rhs"], rep["counts"]["VOID"],
            "no numeral" in rep["records"][0]["reason"],
            all(q["status"] == "PROPOSED" for q in data["questions"]),
            w.proposals()["proposals"][0]["status"])


def hyp(i, prior):
    return {"id": i, "prior": prior, "prior_source": "stated", "prior_flag": None}


def declared_check():
    ev = {"id": "e", "type": "direct", "hypothesis": "a", "lr": "4", "provenance": "p",
          "shared_ancestry": [], "status": "OBSERVED", "check": {"branch": "2b", "verdict": "HOLDS"}}
    h = rank({"hypotheses": [hyp("a", "1/2"), hyp("b", "1/2")], "evidence": [ev]})["hypotheses"][0]
    return h["status"], h["status_reason"].startswith("CHECK_UNVERIFIED")


def re_read_check():
    """A real rigorous 2b HOLDS record lifts; a FAILS record and a --fast HOLDS do not."""
    v = lambda x, u: {"value": x, "unit": u}  # noqa: E731
    rep = check_all([
        {"formula": "F = m*a", "values": {"F": v("7.5", "N"), "m": v("2.5", "kg"), "a": v(3, "m/s**2")}},
        {"formula": "F = m*a", "values": {"F": v("8", "N"), "m": v("2.5", "kg"), "a": v(3, "m/s**2")}},
        {"formula": "y = x", "tolerance": "0.5", "fast": True,
         "values": {"y": v("1.0", "m"), "x": v("1.1", "m")}}], "checks.json")
    out = []
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "r.json").write_text(json.dumps(rep))
        for i, rec in enumerate(rep["records"]):
            ref = {"branch": "2b", "file": "r.json", "record": i, "sha256": record_sha(rec)}
            ev = {"id": "e", "type": "direct", "hypothesis": "a", "lr": "4", "provenance": "p",
                  "shared_ancestry": [], "status": "OBSERVED", "check_ref": ref}
            h = rank({"hypotheses": [hyp("a", "1/2"), hyp("b", "1/2")], "evidence": [ev]},
                     base_dir=d)["hypotheses"][0]
            out.append((rec["verdict"], h["status"]))
    return out


# (id, quote from README.md, observed(), expected). The quote is matched after
# whitespace is collapsed, so it may span wrapped lines.
CLAIMS = [
    ("constant-fold",
     "so (1e16 + 1) - 1e16 = 1 is exact at every tier (HOLDS, rigorous; no prediction)",
     lambda: (lambda r: (r["verdict"], r["rigorous"], tiers(r)))(
         point("y = (1e16 + 1) - 1e16", "0", y=val(1))),
     ("HOLDS", True, [None, None])),
    ("float-mispredicts-with-symbols",
     "y = ((a + b) - a)*c with a = 1e16, b = 3, c = 1e10, y = 3e10 holds exactly, "
     "but binary64 reads (1e16 + 3) - 1e16 as 4 and the float tier predicts FAILS; "
     "Decimal predicts HOLDS, the interval tier confirms HOLDS",
     lambda: (lambda r: (r["verdict"], r["deciding_tier"], tiers(r)))(
         point("y = ((a + b) - a)*c", "1", y=val("3e10"), a=val("1e16"), b=val(3),
               c=val("1e10"))),
     ("HOLDS", "interval", ["FAILS", "HOLDS"])),
    ("guard-without-scale-factor",
     'without the factor c the guard reads (a + b) - a as "too close to call"',
     lambda: point("y = (a + b) - a", "0.25", y=val(1), a=val("1e16"), b=val(1))
     ["tiers"][0]["outcome"],
     "too close to call"),
    ("dependency-problem",
     "on interval inputs an identity still reads UNDECIDED: x*x = x**2 on "
     "x in [0, 1] is UNDECIDED at tolerance 0",
     lambda: point("x*x = x**2", "0", x=val([0, 1], "m"))["verdict"],
     "UNDECIDED"),
    ("dependency-problem-with-tolerance",
     "With a tolerance > 0 it reads HOLDS via bisection, if the depth allows.",
     lambda: point("x*x = x**2", "0.05", x=val([0, 1], "m"))["verdict"],
     "HOLDS"),
    ("decimals-read-exactly",
     "Numbers are read exactly as written: 0.1 is one tenth.",
     # JSON numbers, as in checks.json, read through read_json; a Python float
     # handed to check_point directly is refused (test_a_binary_float_is_refused)
     lambda: check_point(read_json(
         '{"formula": "c = a + b", "tolerance": 0, "values": {'
         '"a": {"value": 0.1, "unit": "m"}, "b": {"value": 0.2, "unit": "m"}, '
         '"c": {"value": 0.3, "unit": "m"}}}'))["verdict"],
     "HOLDS"),
    ("unknown-units-void-today",
     "km, eV and degC are not in the unit table, so a check using them comes back "
     "VOID (unknown unit), not PASS.",
     lambda: [units("x = y", x="km", y="m"), units("E = q", E="eV", q="J"),
              units("T = U", T="degC", U="K")],
     ["VOID", "VOID", "VOID"]),
    ("torque-reads-as-energy",
     "rad, torque and energy already read alike today.",
     lambda: units("E = F*r", E="J", F="N", r="m"),
     "PASS"),
    ("symbolic-exponent-void",
     "on a base with a dimension, k must be a literal number, else VOID",
     lambda: units("y = x**n", y="m", x="m", n="1"),
     "VOID"),
    ("exp-argument-dimensionless",
     "exp log sin cos tan (x) x dimensionless",
     lambda: [units("N = N0*exp(t)", N="1", N0="1", t="s"),
              units("N = N0*exp(t/tau)", N="1", N0="1", t="s", tau="s")],
     ["FAIL", "PASS"]),
    ("unitaudit-exit-codes",
     "exit 0 all PASS | 1 any FAIL | 3 VOID, no FAIL | 2 usage",
     lambda: [cli("unitaudit", "check", "formulas.json"), cli("unitaudit")],
     [1, 2]),
    ("numcheck-exit-codes",
     "# exit 0 all HOLDS / BOTH_HOLD | 1 any FAILS / ONE_FAILS | 3 MIXED, UNDECIDED or VOID, "
     "none failed | 2 usage",
     lambda: [cli("numcheck", "check", "checks.json"), cli("numcheck")],
     [1, 2]),
    ("kernel-include-void",
     "include statements ($[ $]): file-level VOID",
     lambda: kernel_on("$[ other.mm $]\n"),
     3),
    # Registered 2026-11-19. The first guards the drift that got past the register:
    # mixed results once carried bisection.holds_elsewhere; on main they read MIXED.
    ("mixed-both-kinds-listed",
     "pieces that HOLD and pieces that FAIL -> MIXED (both kinds listed)",
     mixed_example,
     ("MIXED", True, True, False)),
    ("branch1-three-verdicts",
     "unitaudit/ BUILT: dimension check, PASS / FAIL / VOID",
     lambda: [units("E = F*r", E="J", F="N", r="m"),
              units("N = N0*exp(t)", N="1", N0="1", t="s"),
              units("x = y", x="km", y="m")],
     ["PASS", "FAIL", "VOID"]),
    ("glyph-gain-undeclared",
     'No gain -> VOID ("gain undeclared").',
     lambda: in_world(gain_missing),
     ("VOID", True)),
    ("glyph-dimensional-analogy",
     "dimensional_analogy shared_dims: two branch-1 PASS records with rhs of one = rhs of the",
     lambda: in_world(analogy),
     (1, "L^2 M T^-2", "dimensional_analogy", ("m*c**2", "m*v**2/2"), "PROPOSED")),
    ("glyph-analogy-example-is-false",
     "m*c**2 = m*v**2/2 is what dimensional_analogy proposes from two energy formulas",
     lambda: in_world(analogy)[3],
     ("m*c**2", "m*v**2/2")),
    ("glyph-boundary-probe-needs-mixed",
     "boundary_probe mixed_region: a branch-2b record that is MIXED",
     lambda: in_world(mixed_region),
     ("MIXED", 1, "HOLDS", 0)),
    ("glyph-seam-49-10-void",
     "a candidate with bounds such as 49/10 is VOID at the 2b -> 2a seam "
     "(algebra.mm has numerals 0 to 9 only)",
     lambda: in_world(seam),
     ("1/2", 1, True, True, "PROPOSED")),
    ("infer-one-rival-void",
     "hypotheses (>= 2 rivals; one alone -> VOID)",
     lambda: (lambda r: (r["verdict"], "one alone" in r["void_reason"]))(
         rank({"hypotheses": [hyp("only", "1")], "evidence": []})),
     ("VOID", True)),
    ("infer-declared-check-unverified",
     "Anything else, a merely declared check included: PROPOSED, reason CHECK_UNVERIFIED.",
     declared_check,
     ("PROPOSED", True)),
    ("infer-check-ref-re-read",
     "HOLDS / BOTH_HOLD with rigorous true (2b).",
     re_read_check,
     [("HOLDS", "DERIVED"), ("FAILS", "PROPOSED"), ("HOLDS", "PROPOSED")]),
]


class TestReadmeClaims(unittest.TestCase):
    def test_every_quote_is_still_in_the_readme(self):
        text = norm(README.read_text())
        for cid, quote, _, _ in CLAIMS:
            with self.subTest(claim=cid):
                self.assertIn(norm(quote), text,
                              f"{cid}: quote no longer in README.md; the prose changed. "
                              "Re-check the behaviour and update the register.")

    def test_every_quote_matches_behaviour(self):
        for cid, quote, observed, expected in CLAIMS:
            with self.subTest(claim=cid):
                self.assertEqual(observed(), expected,
                                 f"{cid}: README says {quote!r}; the code does otherwise")


VERDICT = re.compile(r"\b(PASS|FAIL|FAILS|VOID|HOLDS|UNDECIDED|MIXED|BOTH_HOLD|ONE_FAILS)\b")
EXAMPLE = re.compile(r"\d.*[=*/+]|[=*/+].*\d|\bkm\b|\beV\b|\bdegC\b")


def hunt():
    """README lines that look like concrete examples and no quote covers."""
    quotes = [norm(q) for _, q, _, _ in CLAIMS]
    out = []
    for n, line in enumerate(README.read_text().splitlines(), 1):
        body = norm(line)
        if not (VERDICT.search(body) and EXAMPLE.search(body)):
            continue
        if any(body in q or q in body for q in quotes):
            continue
        # a wrapped quote covers a line when a long run of the line is in it
        if any(len(body) > 20 and body[len(body) // 4: len(body) * 3 // 4] in q
               for q in quotes):
            continue
        out.append((n, line.strip()))
    return out


if __name__ == "__main__":
    if "--hunt" in sys.argv:
        rows = hunt()
        print(f"README claim hunt: {len(CLAIMS)} registered, {len(rows)} lines UNCHECKED "
              "(heuristic selection, PROPOSED; unchecked is not wrong)")
        for n, line in rows:
            print(f"  README.md:{n}: {line}")
    else:
        unittest.main()
