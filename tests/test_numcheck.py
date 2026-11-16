"""Tests for numcheck (branch 2b). Co-authored."""
import json
import math
import subprocess
import sys
import tempfile
import unittest
from fractions import Fraction as F
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from numcheck import Interval, IntervalVoid, check_intersection, check_point, read_json  # noqa: E402
from numcheck import interval as I  # noqa: E402
from numcheck.tiers import FloatSys  # noqa: E402


def val(value, unit="1", status=None):
    return {"value": value, "unit": unit, "status": status}


def point(formula, tolerance="0", fast=False, **values):
    return check_point({"formula": formula, "tolerance": tolerance, "values": values,
                        "fast": fast})


class TestInterval(unittest.TestCase):
    def test_exact_arithmetic(self):
        a, b = Interval(1, 2), Interval(-3, F(1, 2))
        self.assertEqual(a + b, Interval(-2, F(5, 2)))
        self.assertEqual(a - b, Interval(F(1, 2), 5))
        self.assertEqual(a * b, Interval(-6, 1))
        self.assertEqual(Interval(1) / Interval(2, 4), Interval(F(1, 4), F(1, 2)))
        self.assertEqual(Interval(-2, 3).powi(2), Interval(0, 9))
        self.assertEqual(Interval(-2, 3).powi(3), Interval(-8, 27))
        self.assertEqual(Interval(-3, -2).powi(2), Interval(4, 9))
        self.assertEqual(Interval(2, 4).powi(-1), Interval(F(1, 4), F(1, 2)))
        self.assertEqual(abs(Interval(-2, 1)), Interval(0, 2))
        with self.assertRaises(ValueError):
            Interval(2, 1)

    def test_division_by_zero_interval_is_void(self):
        for d in (Interval(-1, 1), Interval(0), Interval(0, 5), Interval(-5, 0)):
            with self.assertRaises(IntervalVoid):
                Interval(1) / d
        with self.assertRaises(IntervalVoid):
            Interval(-1, 1).powi(-2)

    def test_enclosures_contain_and_are_tight(self):
        for name, f, xs in (("sqrt", math.sqrt, (2, 3, F(1, 7), 1000)),
                            ("exp", math.exp, (1, -3, F(1, 7), 20)),
                            ("ln", math.log, (2, F(1, 7), 1000)),
                            ("sin", math.sin, (1, -3, F(22, 7), 100, 999)),
                            ("cos", math.cos, (1, -3, F(22, 7), 100, 999))):
            for x in xs:
                e = getattr(I, name)(Interval(x), 30)
                self.assertLess(e.lo, e.hi)
                self.assertAlmostEqual(float(e.lo), f(float(x)), delta=abs(f(float(x))) * 1e-12)
                self.assertLess(e.width, abs(e.hi) * F(1, 10 ** 26) + F(1, 10 ** 26))
                wider = getattr(I, name)(Interval(x), 15)
                self.assertTrue(e.inside(wider), (name, x))     # more digits: inside fewer

    def test_exact_cases_stay_exact(self):
        self.assertEqual(I.sqrt(Interval(F(9, 4)), 30), Interval(F(3, 2)))
        self.assertEqual(I.sqrt(Interval(0, 4), 30), Interval(0, 2))
        self.assertEqual(I.exp(Interval(0), 30), Interval(1))
        self.assertEqual(I.ln(Interval(1), 30), Interval(0))

    def test_known_digits(self):
        d = str(I.to_decimal(I.pi(40).lo, 40, True))
        self.assertTrue(d.startswith("3.14159265358979323846264338327950288419"))
        self.assertTrue(str(I.to_decimal(I.exp(Interval(1), 40).lo, 38, True))
                        .startswith("2.718281828459045235360287471352662497"))
        self.assertTrue(str(I.to_decimal(I.sin(Interval(1), 40).lo, 38, True))
                        .startswith("0.84147098480789650665250232163029899"))

    def test_trig_over_wide_intervals(self):
        self.assertEqual(I.sin(Interval(0, 10), 20), Interval(-1, 1))
        s = I.sin(Interval(1, 2), 20)                 # holds pi/2: the top is exactly 1
        self.assertEqual(s.hi, 1)
        self.assertAlmostEqual(float(s.lo), math.sin(1), places=12)
        c = I.cos(Interval(3, 4), 20)                 # holds pi: the bottom is exactly -1
        self.assertEqual(c.lo, -1)
        m = I.sin(Interval(F(1, 10), F(1, 2)), 20)    # monotone piece: just the two ends
        self.assertAlmostEqual(float(m.lo), math.sin(0.1), places=12)
        self.assertAlmostEqual(float(m.hi), math.sin(0.5), places=12)

    def test_void_domains(self):
        for f, iv in ((I.sqrt, Interval(-1, 4)), (I.ln, Interval(0, 1)), (I.ln, Interval(-2)),
                      (I.sin, Interval(1001)), (I.cos, Interval(-5000, 5000))):
            with self.assertRaises(IntervalVoid):
                f(iv, 20)


class TestPoint(unittest.TestCase):
    def test_exact_rational_holds(self):
        r = point("F = m*a", F=val("7.5", "N", "OBSERVED"), m=val("2.5", "kg", "PROPOSED"),
                  a=val(3, "m/s**2"))
        self.assertEqual((r["verdict"], r["status"]), ("HOLDS", "DERIVED"))
        self.assertEqual((r["deciding_tier"], r["precision"], r["rigorous"]),
                         ("interval", "exact", True))
        self.assertEqual(r["intervals"]["difference"]["lo"], "0")
        self.assertEqual({k: v["status"] for k, v in r["inputs"].items()},
                         {"F": "OBSERVED", "m": "PROPOSED", "a": None})     # own tags kept
        self.assertEqual(r["units"]["verdict"], "PASS")
        self.assertIsNone(r["human_interest"])
        self.assertIsNone(r["ai_interest"])
        r = point("y = x/3", y=val("1/3", "m"), x=val(1, "m"))
        self.assertEqual((r["verdict"], r["deciding_tier"]), ("HOLDS", "interval"))

    def test_float_trap(self):
        self.assertNotEqual(0.1 + 0.2, 0.3)             # what a bare float check would see
        data = read_json('{"formula": "c = a + b", "tolerance": 0, "values": {'
                         '"a": {"value": 0.1, "unit": "m"}, "b": {"value": 0.2, "unit": "m"},'
                         '"c": {"value": 0.3, "unit": "m"}}}')
        r = check_point(data)
        self.assertEqual(r["verdict"], "HOLDS")
        self.assertEqual(r["deciding_tier"], "interval")
        self.assertEqual([t["outcome"] for t in r["tiers"]],
                         ["too close to call", "too close to call", "decided"])
        self.assertEqual(r["tiers"][0]["tier"], "float")
        self.assertEqual(r["triage"], {"predictions": [], "disagrees_with_verdict": []})
        fast = check_point(dict(data, fast=True))        # even fast cannot shortcut this one
        self.assertEqual((fast["verdict"], fast["deciding_tier"], fast["rigorous"]),
                         ("HOLDS", "interval", True))
        # and the float tier never says HOLDS or FAILS on it by itself
        S = FloatSys()
        d = S.sub(S.const(F(3, 10)), S.add(S.const(F(1, 10)), S.const(F(2, 10))))
        self.assertNotEqual(d, 0.0)
        self.assertIsNone(S.judge(d, F(0))[0])
        # the same trap the other way round: really unequal by 1e-17, a float sees equal
        r = point("c = a + b", a=val("0.1", "m"), b=val("0.2", "m"),
                  c=val("0.30000000000000001", "m"))
        self.assertEqual(0.1 + 0.2 - 0.30000000000000001, 0.1 + 0.2 - 0.3)
        self.assertEqual((r["verdict"], r["deciding_tier"], r["rigorous"]),
                         ("FAILS", "interval", True))
        self.assertEqual(r["tiers"][0]["outcome"], "too close to call")     # float could not
        self.assertEqual(r["tiers"][1]["predicts"], "FAILS")                # Decimal saw it
        self.assertEqual(r["intervals"]["difference"]["lo"], "1/100000000000000000")

    def test_a_binary_float_is_refused(self):
        r = point("c = a", a=val(0.1, "m"), c=val("0.1", "m"))
        self.assertEqual(r["verdict"], "VOID")
        self.assertIn("binary float", r["void_reason"])

    def test_interval_tier_decides_by_default(self):
        kw = dict(E=val("9.0e16", "J"), m=val(1, "kg"), c=val(299792458, "m/s"))
        r = point("E = m*c**2", "1e9", **kw)
        self.assertEqual((r["verdict"], r["deciding_tier"], r["precision"], r["rigorous"]),
                         ("FAILS", "interval", "exact", True))
        self.assertEqual([(t["tier"], t["role"], t["predicts"]) for t in r["tiers"]],
                         [("float", "triage", "FAILS"), ("decimal", "triage", "FAILS"),
                          ("interval", "decides", None)])
        self.assertEqual(r["triage"], {"predictions": ["FAILS", "FAILS"],
                                       "disagrees_with_verdict": []})
        self.assertEqual(r["intervals"]["difference"]["lo"], str(9 * 10 ** 16 - 299792458 ** 2))
        self.assertEqual(r["intervals"]["difference"]["lo"], "124482126318236")
        self.assertFalse(r["fast"])
        r = point("y = x", "0.5", y=val("1.0", "m"), x=val("1.1", "m"))
        self.assertEqual((r["verdict"], r["deciding_tier"], r["rigorous"]),
                         ("HOLDS", "interval", True))

    def test_fast_takes_a_triage_prediction_and_says_so(self):
        kw = dict(E=val("9.0e16", "J"), m=val(1, "kg"), c=val(299792458, "m/s"))
        r = point("E = m*c**2", "1e9", fast=True, **kw)
        self.assertEqual((r["verdict"], r["deciding_tier"], r["rigorous"], r["fast"]),
                         ("FAILS", "float", False, True))
        self.assertEqual(len(r["tiers"]), 1)
        self.assertEqual(r["tiers"][0]["role"], "decided (fast)")
        self.assertIsNone(r["intervals"])
        r = point("y = x", "1e-12", fast=True, y=val("1", "m"), x=val("1.000000000001001", "m"))
        self.assertEqual((r["verdict"], r["deciding_tier"], r["precision"], r["rigorous"]),
                         ("FAILS", "decimal", 50, False))
        self.assertEqual(r["tiers"][0]["outcome"], "too close to call")
        r = check_point({"formula": "y = x", "values": {"y": val(1, "m"), "x": val(2, "m")}},
                        fast=True)                       # the caller's flag, e.g. --fast
        self.assertEqual((r["deciding_tier"], r["rigorous"]), ("float", False))

    def test_a_wrong_triage_prediction_is_logged_not_used(self):
        # the float margin rule is a heuristic and can be wrong: binary64 reads
        # (1e16 + 3) - 1e16 as 4, and the factor 1e10 lifts that error far above
        # the guard (1e-9 x the largest magnitude met). Exactly, y = 3e10 holds.
        self.assertEqual((1e16 + 3) - 1e16, 4.0)
        kw = dict(y=val("3e10", "1"), a=val("1e16", "1"), b=val(3, "1"), c=val("1e10", "1"))
        r = point("y = ((a + b) - a)*c", "1", **kw)
        self.assertEqual((r["verdict"], r["deciding_tier"], r["rigorous"]),
                         ("HOLDS", "interval", True))
        self.assertEqual(r["tiers"][0]["predicts"], "FAILS")           # float: wrong
        self.assertEqual(r["tiers"][1]["predicts"], "HOLDS")           # Decimal(50): right
        self.assertEqual(r["triage"]["disagrees_with_verdict"], ["float"])
        fast = point("y = ((a + b) - a)*c", "1", fast=True, **kw)
        self.assertEqual((fast["verdict"], fast["rigorous"]), ("FAILS", False))   # why not fast
        # a milder cancellation is caught by the guard: "too close to call"
        r = point("y = (a + b) - a", "0.25", y=val(1, "1"), a=val("1e16", "1"), b=val(1, "1"))
        self.assertEqual((r["verdict"], r["tiers"][0]["outcome"]),
                         ("HOLDS", "too close to call"))

    def test_straddle_is_undecided(self):
        r = point("x = v*t", "0.5", x=val(["9.8", "10.4"], "m"), v=val(2, "m/s"),
                  t=val(["4.9", "5.1"], "s"))
        self.assertEqual((r["verdict"], r["status"], r["deciding_tier"]),
                         ("UNDECIDED", "DERIVED", "interval"))
        self.assertEqual([t["outcome"] for t in r["tiers"][:2]], ["skipped", "skipped"])
        self.assertEqual((r["intervals"]["difference"]["lo"], r["intervals"]["difference"]["hi"]),
                         ("-2/5", "3/5"))
        b = r["bisection"]                 # bisected first; the straddle is real
        self.assertTrue(b["mixed"])
        self.assertGreater(b["hold"], 0)
        self.assertGreater(b["fail"], 0)
        self.assertEqual(sorted(b["variables_split"]), ["t", "x"])
        self.assertIsNotNone(b["a_piece_that_fails"])
        r = point("x = v*t", "0.7", x=val(["9.8", "10.4"], "m"), v=val(2, "m/s"),
                  t=val(["4.9", "5.1"], "s"))
        self.assertEqual(r["verdict"], "HOLDS")
        self.assertIsNone(r["bisection"])                 # decided without it
        r = point("x = v*t", "0.1", x=val(["9.8", "10.4"], "m"), v=val(2, "m/s"),
                  t=val(["5.3", "5.4"], "s"))
        self.assertEqual(r["verdict"], "FAILS")

    def test_bisection_closes_a_dependency_straddle(self):
        # x*x and x**2 are equal; on a wide x their enclosures differ by up to 2
        kw = dict(x=val([0, 1], "m"))
        r = point("x*x = x**2", "0.05", **kw)
        self.assertEqual(r["intervals"]["difference"]["lo"], "-1")      # the first look
        self.assertEqual((r["verdict"], r["rigorous"]), ("HOLDS", True))
        b = r["bisection"]
        self.assertEqual((b["fail"], b["straddle_at_depth_limit"], b["mixed"]), (0, 0, False))
        self.assertGreater(b["hold"], 1)
        r = check_point({"formula": "x*x = x**2", "tolerance": "0.05", "depth": 2,
                         "values": kw})
        self.assertEqual(r["verdict"], "UNDECIDED")                    # depth limit too low
        self.assertEqual(r["bisection"]["reading"], "pieces still straddle at the depth limit")
        r = point("x*x = x**2", "0", **kw)        # tolerance 0: pieces narrow, never close
        self.assertEqual(r["verdict"], "UNDECIDED")
        r = point("x*x = x**2 + c", "0.05", c=val(1, "m**2"), **kw)     # every piece fails
        self.assertEqual(r["verdict"], "FAILS")
        r = point("y = c/x", "1", y=val(1, "1"), c=val(1, "1"), x=val([-1, 1], "1"))
        self.assertEqual(r["verdict"], "VOID")                         # still fail-closed

    def test_enclosure_precision_climbs(self):
        # sqrt(2)**2 = 2 exactly, but an enclosure of sqrt(2) can only straddle 0
        r = point("y = sqrt(x)*sqrt(x)", y=val(2, "m**2"), x=val(2, "m**2"))
        self.assertEqual((r["verdict"], r["deciding_tier"], r["precision"]),
                         ("UNDECIDED", "interval", 120))
        self.assertEqual([t["precision"] for t in r["tiers"] if t["tier"] == "interval"],
                         [30, 60, 120])
        r = point("y = sqrt(x)*sqrt(x)", "1e-40", y=val(2, "m**2"), x=val(2, "m**2"))
        self.assertEqual((r["verdict"], r["precision"]), ("HOLDS", 60))
        self.assertIsNone(r["bisection"])                 # point inputs: nothing to split
        r = point("y = sin(x)", "1e-20", y=val("0.8414709848078965066525", "1"), x=val(1, "1"))
        self.assertEqual((r["verdict"], r["deciding_tier"]), ("HOLDS", "interval"))
        self.assertEqual(r["tiers"][1]["outcome"], "cannot run")       # no sin at decimal

    def test_division_by_zero_interval_is_void(self):
        r = point("v = x/t", "0.1", v=val(2, "m/s"), x=val(10, "m"), t=val([-1, 1], "s"))
        self.assertEqual((r["verdict"], r["status"]), ("VOID", None))
        self.assertIn("containing 0", r["void_reason"])
        r = point("v = x/t", v=val(2, "m/s"), x=val(10, "m"), t=val(0, "s"))
        self.assertEqual(r["verdict"], "VOID")                  # not a float inf or an error

    def test_units_fail_is_void(self):
        r = point("E = m*c", E=val(1, "J"), m=val(1, "kg"), c=val(1, "m/s"))
        self.assertEqual((r["verdict"], r["status"]), ("VOID", None))
        self.assertIn("units FAIL", r["void_reason"])
        self.assertEqual(r["units"]["verdict"], "FAIL")
        self.assertEqual(r["tiers"], [])                         # no numeric tier was run
        r = point("E = m*c**2", E=val(1, "J"), m=val(1, "kg"), c=val(1, "furlong/s"))
        self.assertIn("units VOID", r["void_reason"])
        r = point("y = exp(t)", y=val(1, "1"), t=val(0, "s"))
        self.assertIn("units FAIL", r["void_reason"])

    def test_other_voids(self):
        self.assertEqual(point("y = x", y=val(1, "m"))["verdict"], "VOID")
        self.assertEqual(point("y = x", y=val(1, "m"), x={"unit": "m"})["verdict"], "VOID")
        self.assertEqual(point("y = x", "-1", y=val(1, "m"), x=val(1, "m"))["verdict"], "VOID")
        self.assertEqual(point("y = x", y=val("abc", "m"), x=val(1, "m"))["verdict"], "VOID")
        self.assertEqual(point("y = x", y=val([2, 1], "m"), x=val(1, "m"))["verdict"], "VOID")
        self.assertEqual(point("y = x", y=val(1, "m", "sure"), x=val(1, "m"))["verdict"], "VOID")
        self.assertEqual(point("y = x**k", y=val(1, "1"), x=val(1, "1"),
                               k=val(2, "1"))["verdict"], "VOID")
        self.assertEqual(point("y = sqrt(x)", y=val(1, "m"),
                               x=val([-1, 4], "m**2"))["verdict"], "VOID")
        self.assertEqual(check_point("y = x")["verdict"], "VOID")

    def test_slots(self):
        r = check_point({"formula": "y = x", "values": {"y": val(1, "m"), "x": val(1, "m")},
                         "slots": {"sign": "+"}})
        self.assertEqual(r["slots"]["limit"]["slot_state"], "VOID")
        self.assertEqual(r["slots"]["sign"]["slot_state"], "UNCHECKED")


def inter(f1, t1, f2, t2, region, depth=8, **values):
    return check_intersection({"formulas": [{"formula": f1, "tolerance": t1},
                                            {"formula": f2, "tolerance": t2}],
                               "region": region, "depth": depth, "values": values})


class TestIntersection(unittest.TestCase):
    base = dict(x={"unit": "m"}, y=val(3, "m"), k=val(2, "1"), c=val("0.5", "m"))

    def test_both_hold(self):
        r = inter("y = k*x - k*x + y", "0.1", "x*x = x**2", "0.1", {"x": [0, 1]}, **self.base)
        self.assertEqual((r["verdict"], r["status"], r["rigorous"]), ("BOTH_HOLD", "DERIVED", True))
        s = r["subboxes"]
        self.assertEqual(s["undecided_at_depth_limit"], 0)
        self.assertGreater(s["both_hold"], 1)                   # it needed bisection
        self.assertLessEqual(s["deepest"], 8)
        self.assertTrue(r["inputs"]["x"]["from_region"])

    def test_one_fails_located(self):
        r = inter("y = k*x - k*x + y", "0.1", "x = c", "0.1", {"x": [0, 1]}, **self.base)
        self.assertEqual(r["verdict"], "ONE_FAILS")
        loc = r["located"]
        self.assertEqual((loc["formula_number"], loc["formula"]), (2, "x = c"))
        self.assertEqual((loc["subbox"]["x"]["lo"], loc["subbox"]["x"]["hi"]), ("0", "1/4"))
        self.assertEqual(loc["depth"], 2)

    def test_undecided_at_depth_limit(self):
        r = inter("y = k*x - k*x + y", "0.1", "x*x = x**2", "0.1", {"x": [0, 1]}, depth=1,
                  **self.base)
        self.assertEqual(r["verdict"], "UNDECIDED")
        self.assertEqual(r["subboxes"]["deepest"], 1)
        self.assertIsNotNone(r["first_undecided_subbox"])
        # tolerance 0 on an interval: the two sides are equal but their enclosures are not
        r = inter("x*x = x**2", "0", "y = y", "0", {"x": [0, 1]}, depth=4, **self.base)
        self.assertEqual(r["verdict"], "UNDECIDED")

    def test_void(self):
        # x / x has no value on any subbox that holds 0, however far it is bisected
        r = inter("x/x = k/k", "2", "x = x", "2", {"x": [-1, 1]}, depth=3,
                  x={"unit": "1"}, k=val(2, "1"))
        self.assertEqual((r["verdict"], r["status"]), ("VOID", None))
        self.assertIn("containing 0", r["void_reason"])
        self.assertEqual(r["subboxes"]["no_value_at_depth_limit"], 2)
        self.assertGreater(r["subboxes"]["both_hold"], 0)
        # a formula that fails everywhere on some subbox is ONE_FAILS, void elsewhere or not
        r = inter("y = c/x", "1", "x = x", "2", {"x": [-1, 1]}, depth=3,
                  x={"unit": "1"}, y=val(3, "m"), c=val("0.5", "m"))
        self.assertEqual(r["verdict"], "ONE_FAILS")
        r = inter("y = k*x", "1", "x = y*y", "1", {"x": [0, 1]}, **self.base)   # units FAIL
        self.assertEqual(r["verdict"], "VOID")
        self.assertIn("formula 2: units FAIL", r["void_reason"])
        self.assertEqual(check_intersection({"formulas": []})["verdict"], "VOID")
        r = inter("y = y", "0", "c = c", "0", {"x": [0, 1]}, **self.base)
        self.assertIn("neither formula", r["void_reason"])

    def test_two_variables(self):
        r = inter("x + t = t + x", "0.2", "x*t = t*x", "0.2", {"x": [0, 1], "t": [0, 1]},
                  depth=10, x={"unit": "1"}, t={"unit": "1"})
        self.assertEqual(r["verdict"], "BOTH_HOLD")


class TestCli(unittest.TestCase):
    def cli(self, *args):
        return subprocess.run([sys.executable, "-m", "numcheck", *args], cwd=ROOT,
                              capture_output=True, text=True)

    def test_exit_codes(self):
        r = self.cli("check", "checks.json", "--json")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(json.loads(r.stdout)["counts"],
                         {"HOLDS": 2, "FAILS": 1, "UNDECIDED": 1, "VOID": 2, "BOTH_HOLD": 0,
                          "ONE_FAILS": 1})
        self.assertEqual(self.cli().returncode, 2)
        self.assertEqual(self.cli("check", "nope.json").returncode, 2)
        ok = {"formula": "y = x", "values": {"y": val(1, "m"), "x": val(1, "m")}}
        und = {"formula": "y = x", "values": {"y": val([0, 2], "m"), "x": val(1, "m")}}
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "c.json"
            f.write_text(json.dumps([ok]))
            self.assertEqual(self.cli("check", str(f)).returncode, 0)
            f.write_text(json.dumps([ok, und]))
            self.assertEqual(self.cli("check", str(f)).returncode, 3)
            f.write_text(json.dumps([ok, {"kind": "other"}]))
            self.assertEqual(self.cli("check", str(f)).returncode, 3)
            f.write_text(json.dumps([ok]))
            slow = json.loads(self.cli("check", str(f), "--json").stdout)["records"][0]
            quick = json.loads(self.cli("check", str(f), "--json", "--fast").stdout)["records"][0]
            self.assertEqual((slow["rigorous"], slow["deciding_tier"]), (True, "interval"))
            self.assertEqual((quick["rigorous"], quick["fast"]), (True, True))   # 1 = 1: too close
        r = json.loads(self.cli("check", "checks.json", "--json", "--fast").stdout)["records"][2]
        self.assertEqual((r["deciding_tier"], r["rigorous"]), ("float", False))


if __name__ == "__main__":
    unittest.main()
