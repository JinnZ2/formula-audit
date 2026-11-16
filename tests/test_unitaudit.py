"""Tests for unitaudit, branch 1. Co-authored."""
import json
import subprocess
import sys
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from unitaudit import check_formula, unit_dim, UnknownUnit, Dim  # noqa: E402
from unitaudit.dims import L, M, T, ONE, UNITS  # noqa: E402
from unitaudit.scan import scan  # noqa: E402


def chk(formula, **symbols):
    return check_formula({"formula": formula, "symbols": symbols})


class TestDims(unittest.TestCase):
    def test_algebra(self):
        self.assertEqual(L * L / L, L)
        self.assertEqual((L ** 2) ** Fraction(1, 2), L)
        self.assertEqual(str(M * L ** 2 / T ** 2), "L^2 M T^-2")
        self.assertEqual(str(ONE), "1")
        self.assertTrue((L / L).dimensionless)
        with self.assertRaises(ValueError):
            Dim(1, 2)

    def test_units(self):
        self.assertEqual(unit_dim("J"), unit_dim("kg*m**2/s**2"))
        self.assertEqual(unit_dim("N"), unit_dim("kg*m/s^2"))
        self.assertEqual(unit_dim("W"), unit_dim("J/s"))
        self.assertEqual(unit_dim("Pa"), unit_dim("N/m**2"))
        self.assertEqual(unit_dim("V"), unit_dim("W/A"))
        self.assertEqual(unit_dim("ohm"), unit_dim("V/A"))
        self.assertEqual(unit_dim("Ω"), unit_dim("ohm"))
        self.assertEqual(unit_dim("C"), unit_dim("A*s"))
        self.assertEqual(unit_dim("Wb"), unit_dim("V*s"))
        self.assertEqual(unit_dim("T"), unit_dim("Wb/m**2"))
        self.assertEqual(unit_dim("Hz"), unit_dim("1/s"))
        self.assertTrue(unit_dim("1").dimensionless)
        for base in ("m", "kg", "s", "A", "K", "mol", "cd"):
            self.assertEqual(sum(UNITS[base].e), 1)

    def test_unknown_unit(self):
        for bad in ("furlong", "m/", "m**x", None, "m+s"):
            with self.assertRaises(UnknownUnit):
                unit_dim(bad)


class TestCheck(unittest.TestCase):
    def test_pass(self):
        self.assertEqual(chk("E = m*c**2", E="J", m="kg", c="m/s")["verdict"], "PASS")
        self.assertEqual(chk("F = m*a", F="N", m="kg", a="m/s**2")["verdict"], "PASS")
        r = chk("p*V = n*R*T", p="Pa", V="m**3", n="mol", R="J/(mol*K)", T="K")
        self.assertEqual(r["verdict"], "PASS")
        self.assertEqual(r["dims"]["lhs"]["text"], "L^2 M T^-2")
        self.assertEqual(r["status"], "OBSERVED")
        self.assertEqual(chk("v == sqrt(2*g*h)", v="m/s", g="m/s**2", h="m")["verdict"], "PASS")

    def test_fail_sides(self):
        r = chk("E = m*c", E="J", m="kg", c="m/s")
        self.assertEqual(r["verdict"], "FAIL")
        self.assertEqual(r["located_error"]["side"], "both")
        self.assertEqual(r["located_error"]["dims"], ["L^2 M T^-2", "L M T^-1"])

    def test_fail_exp(self):
        r = chk("N = N0*exp(t)", N="1", N0="1", t="s")
        self.assertEqual(r["verdict"], "FAIL")
        e = r["located_error"]
        self.assertEqual((e["side"], e["text"], e["dims"]), ("rhs", "t", ["T"]))
        self.assertEqual("N0*exp(t)"[e["col"]:e["end_col"]], "t")
        for f in ("log", "sin", "cos", "tan"):
            self.assertEqual(chk(f"y = {f}(t)", y="1", t="s")["verdict"], "FAIL")
        self.assertEqual(chk("y = exp(t/tau)", y="1", t="s", tau="s")["verdict"], "PASS")

    def test_fail_sum_located(self):
        r = chk("x = a*t + v", x="m", a="m/s**2", t="s", v="m")
        self.assertEqual(r["verdict"], "FAIL")
        self.assertEqual(r["located_error"]["text"], "a*t + v")
        self.assertEqual(r["located_error"]["dims"], ["L T^-1", "L"])

    def test_pow(self):
        self.assertEqual(chk("y = x**t", y="1", x="1", t="s")["verdict"], "FAIL")
        self.assertEqual(chk("y = x**k", y="1", x="1", k="1")["verdict"], "PASS")
        r = chk("y = x**k", y="m", x="m", k="1")
        self.assertEqual(r["verdict"], "VOID")
        self.assertEqual(chk("A = r**(4/2)", A="m**2", r="m")["verdict"], "PASS")

    def test_void(self):
        r = chk("E = m*q", E="J", m="kg")
        self.assertEqual(r["verdict"], "VOID")
        self.assertIn("unknown symbol 'q'", r["void_reason"])
        self.assertIsNone(r["status"])
        self.assertEqual(chk("E = m", E="J", m="stone")["verdict"], "VOID")
        self.assertEqual(chk("E = m", E="J", m=None)["verdict"], "VOID")
        self.assertEqual(chk("E = gamma(m)", E="J", m="kg")["verdict"], "VOID")
        self.assertEqual(chk("E m", E="J", m="kg")["verdict"], "VOID")
        self.assertEqual(chk("E = m = c", E="J", m="J", c="J")["verdict"], "VOID")
        self.assertEqual(chk("E = m[0]", E="J", m="J")["verdict"], "VOID")
        self.assertEqual(chk("E <= m", E="J", m="J")["verdict"], "VOID")
        self.assertEqual(check_formula({"symbols": {}})["verdict"], "VOID")
        self.assertEqual(check_formula("E = m")["verdict"], "VOID")
        self.assertEqual(check_formula({"formula": "E = m", "symbols": {"E": "J", "m": "J"},
                                        "status": "sure"})["verdict"], "VOID")

    def test_slots_and_status(self):
        r = check_formula({"formula": "F = m*a", "symbols": {"F": "N", "m": "kg", "a": "m/s**2"},
                           "slots": {"sign": "+"}, "source_path": "x.md:3",
                           "status": "PROPOSED"})
        self.assertEqual(r["slots"]["limit"], "VOID")
        self.assertEqual(r["slots"]["magnitude_range"], "VOID")
        self.assertEqual(r["slots"]["sign"]["given"], "+")
        self.assertEqual(r["slots"]["sign"]["checked"], "VOID")
        self.assertEqual(r["status"], "PROPOSED")
        self.assertEqual(r["provenance"]["source_path"], "x.md:3")
        self.assertIsNone(r["human_interest"])
        self.assertIsNone(r["ai_interest"])


class TestCliAndScan(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-m", "unitaudit", *args], cwd=ROOT,
                              capture_output=True, text=True)

    def test_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            def write(name, entries):
                p = Path(d) / name
                p.write_text(json.dumps(entries))
                return str(p)
            ok = {"formula": "F = m*a", "symbols": {"F": "N", "m": "kg", "a": "m/s**2"}}
            bad = {"formula": "F = m", "symbols": {"F": "N", "m": "kg"}}
            void = {"formula": "F = z", "symbols": {"F": "N"}}
            self.assertEqual(self.run_cli("check", write("a.json", [ok])).returncode, 0)
            self.assertEqual(self.run_cli("check", write("b.json", [ok, void, bad])).returncode, 1)
            self.assertEqual(self.run_cli("check", write("c.json", [ok, void])).returncode, 3)
            self.assertEqual(self.run_cli("check", str(Path(d) / "none.json")).returncode, 2)
            self.assertEqual(self.run_cli().returncode, 2)
        r = self.run_cli("check", "formulas.json", "--json")
        self.assertEqual(json.loads(r.stdout)["counts"], {"PASS": 3, "FAIL": 2, "VOID": 1})

    def test_scan_draft_is_void(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "notes.md").write_text("energy: `E = m*c**2` holds\nplain words here\n")
            (Path(d) / "code.py").write_text("# F = m*a\nx = 3\n")
            draft = scan(d)
            self.assertEqual(sorted(e["formula"] for e in draft["formulas"]),
                             ["E = m*c**2", "F = m*a"])
            for e in draft["formulas"]:
                self.assertEqual(e["status"], "PROPOSED")
                self.assertEqual(check_formula(e)["verdict"], "VOID")
            out = Path(d) / "draft.json"
            self.assertEqual(self.run_cli("scan", d, "-o", str(out)).returncode, 0)
            self.assertEqual(self.run_cli("scan", d, "-o", str(out)).returncode, 2)


if __name__ == "__main__":
    unittest.main()
