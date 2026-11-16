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
