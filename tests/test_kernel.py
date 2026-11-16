"""Tests for kernel (branch 2a). Co-authored. Hand-written databases only."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from kernel import check_lines  # noqa: E402

PROP = (ROOT / "tests" / "data" / "prop.mm").read_text()

DV = """
$c |- term wff = E. $.
$v x y z $.
tx $f term x $.  ty $f term y $.  tz $f term z $.
weq $a wff x = y $.
${ $d x y $.  ax-dv $a |- E. x x = y $. $}
${ $d y z $.  ok $p |- E. y y = z $= ty tz ax-dv $. $}
nodv $p |- E. y y = z $= ty tz ax-dv $.
same $p |- E. x x = x $= tx tx ax-dv $.
"""


def run(text, **kw):
    return check_lines(text.splitlines(), **kw).report()


def by_label(rep):
    return {r["label"]: r for r in rep["theorem_records"]}


class TestValid(unittest.TestCase):
    def test_pass(self):
        rep = run(PROP)
        self.assertEqual(rep["counts"], {"PASS": 4, "FAIL": 0, "VOID": 0})
        self.assertTrue(rep["whole_file_read"])
        self.assertIsNone(rep["file_void"])
        t = by_label(rep)
        self.assertEqual(t["id"]["proof_format"], "normal")
        self.assertEqual(t["idc"]["proof_format"], "compressed")
        self.assertEqual((t["id"]["steps"], t["idc"]["steps"]), (40, 28))   # Z saves 12 steps
        for r in rep["theorem_records"]:
            self.assertEqual(r["status"], "DERIVED")
            self.assertIsNone(r["human_interest"])
            self.assertIsNone(r["ai_interest"])

    def test_axioms_are_observed_with_no_verdict(self):
        rep = run(PROP)
        self.assertEqual(rep["axioms"]["count"], 4)
        for a in rep["axiom_records"]:
            self.assertEqual(a["status"], "OBSERVED")
            self.assertIsNone(a["verdict"])
        self.assertEqual({a["label"] for a in rep["axiom_records"]},
                         {"wi", "ax-1", "ax-2", "mp"})


class TestFail(unittest.TestCase):
    def test_one_broken_step(self):
        # the first ax-1 gets wq where the proof needs wp
        bad = PROP.replace("  wp wp ax-1\n", "  wp wq ax-1\n", 1)
        self.assertNotEqual(bad, PROP)
        t = by_label(run(bad))
        r = t["id"]
        self.assertEqual((r["verdict"], r["status"]), ("FAIL", "DERIVED"))
        e = r["located_error"]
        self.assertEqual(e["step"], 40)                  # the last mp: its minor premise
        self.assertEqual(e["step_label"], "mp")
        self.assertIn("min", e["rule"])
        self.assertEqual(e["expected"], "|- ( P -> ( P -> P ) )")
        self.assertEqual(e["got"], "|- ( P -> ( Q -> P ) )")
        self.assertEqual(t["idc"]["verdict"], "PASS")           # the other proofs are untouched
        self.assertEqual(t["idd"]["verdict"], "PASS")
        self.assertEqual(t["idd"]["rests_on_non_pass"], ["id"])  # and says what it rests on

    def test_wrong_statement(self):
        t = by_label(run(PROP.replace("id $p |- ( P -> P ) $=", "id $p |- ( P -> Q ) $=")))
        e = t["id"]["located_error"]
        self.assertEqual(t["id"]["verdict"], "FAIL")
        self.assertEqual((e["expected"], e["got"]), ("|- ( P -> Q )", "|- ( P -> P )"))

    def test_typecode_underflow_unknown_label_leftover(self):
        base = "$c wff |- ( ) -> $. $v P $. wp $f wff P $. ax $a |- P $. wi $a wff ( P -> P ) $.\n"
        cases = {"t $p |- P $= ax $.": "not enough entries",
                 "t $p |- P $= wp ax ax $.": "typecode",
                 "t $p |- P $= wp nothere $.": "not an active hypothesis",
                 "t $p |- P $= wp wp ax $.": "exactly one entry",
                 "t $p |- P $= wp t $.": "not an active hypothesis"}
        for text, rule in cases.items():
            r = run(base + text)["theorem_records"][0]
            self.assertEqual(r["verdict"], "FAIL", text)
            self.assertIn(rule, r["located_error"]["rule"], text)
            self.assertIsNotNone(r["located_error"]["step"])

    def test_hypothesis_out_of_scope(self):
        t = by_label(run(PROP + "\nbad $p |- P $= a1i.1 $.\n"))
        self.assertEqual(t["bad"]["verdict"], "FAIL")
        self.assertEqual(t["bad"]["located_error"]["step"], 1)

    def test_disjoint_variables(self):
        t = by_label(run(DV))
        self.assertEqual(t["ok"]["verdict"], "PASS")
        self.assertEqual(t["nodv"]["verdict"], "FAIL")
        self.assertEqual(t["nodv"]["located_error"]["expected"], "$d y z in effect")
        self.assertEqual(t["same"]["verdict"], "FAIL")
        self.assertEqual(t["same"]["located_error"]["got"], "x in both")
        self.assertEqual(t["same"]["located_error"]["step"], 3)

    def test_dv_violation_is_located(self):
        # 1a: a substitution that breaks a $d -> FAIL at the step that applies it
        text = (ROOT / "tests" / "data" / "dv.mm").read_text()
        rep = run(text)
        t = by_label(rep)
        self.assertEqual(rep["counts"], {"PASS": 2, "FAIL": 3, "VOID": 0})
        self.assertEqual(t["good"]["verdict"], "PASS")
        self.assertEqual(t["good2"]["verdict"], "PASS")
        e = t["no-dv"]["located_error"]           # same proof as good, its $d line gone
        self.assertEqual((t["no-dv"]["verdict"], t["no-dv"]["status"]), ("FAIL", "DERIVED"))
        self.assertEqual((e["step"], e["step_label"]), (3, "ax-ex"))
        self.assertEqual(e["rule"], "disjoint variables x y")
        self.assertEqual((e["expected"], e["got"]), ("$d y z in effect", "no such $d"))
        e = t["same-var"]["located_error"]        # x := y and y := y share y
        self.assertEqual((e["step"], e["step_label"]), (3, "ax-ex"))
        self.assertEqual((e["expected"], e["got"]), ("no shared variable", "y in both"))
        e = t["inside"]["located_error"]          # y := ( z + z ) contains x := z
        self.assertEqual((e["step"], e["step_label"]), (5, "ax-ex"))
        self.assertEqual(e["got"], "z in both")

    def test_deleting_a_needed_dv_fails(self):
        # 1b on hand data: remove the one $d line the proof of `good` needs
        from kernel.setmm_check import dv_deletions, mutations
        import random
        text = (ROOT / "tests" / "data" / "dv.mm").read_text()
        out = dv_deletions(text, 50, random.Random(0))
        self.assertEqual(out["candidates_in_slice"], 3)
        self.assertEqual(out["counts"]["FAIL"], 1)          # good's $d y z: needed
        self.assertEqual(out["counts"]["PASS"], 2)          # good2: either line covers
        self.assertEqual(sorted(p["deleted"] for p in out["passes"]),
                         ["$d y z $.", "$d z y $."])
        self.assertEqual({p["line"] for p in out["passes"]}, {16})
        self.assertEqual(out["fails_not_located_as_disjoint_variables"], [])
        self.assertEqual(out["first_fails"][0]["theorem"], "good")
        m = mutations(PROP, 40, random.Random(0))           # the only compressed proof: idc
        self.assertEqual(m["counts"]["PASS"], 0)
        self.assertEqual(m["counts"]["FAIL"] + m["counts"]["VOID"], 40)

    def test_compressed_broken(self):
        good = "AAABZBFAACAFABBAFBFBAFCAFADEE"
        self.assertIn(good, PROP)
        t = by_label(run(PROP.replace(good, "AAABZBFAACAFABBAFBFBAFCAFADEC")))
        self.assertEqual(t["idc"]["verdict"], "FAIL")
        t = by_label(run(PROP.replace(good, "AAABZBGAACAFABBAFBFBAFCAFADEE")))
        self.assertEqual(t["idc"]["verdict"], "FAIL")
        self.assertIn("saved step", t["idc"]["located_error"]["rule"])


class TestVoid(unittest.TestCase):
    def test_unknown_keyword(self):
        rep = run(PROP.replace("idd $p", "$x idd $p"))
        self.assertIn("unknown keyword $x", rep["file_void"]["reason"])
        self.assertFalse(rep["whole_file_read"])
        self.assertNotIn("idd", by_label(rep))               # nothing after it gets a verdict
        self.assertEqual(rep["counts"]["PASS"], 3)

    def test_unknown_keyword_inside_a_proof(self):
        rep = run(PROP.replace("wp wp ax-1\n", "wp $zz ax-1\n", 1))
        t = by_label(rep)
        self.assertEqual(t["id"]["verdict"], "VOID")
        self.assertIsNone(t["id"]["status"])
        self.assertIsNotNone(rep["file_void"])
        self.assertEqual(rep["counts"]["PASS"], 0)

    def test_incomplete_and_undecodable(self):
        t = by_label(run(PROP.replace("mp mp $.", "mp ? $.")))
        self.assertEqual(t["id"]["verdict"], "VOID")
        self.assertIn("incomplete", t["id"]["void_reason"])
        good = "AAABZBFAACAFABBAFBFBAFCAFADEE"
        for bad in ("ZAAB", "AAAB?", "AAABU", "AAAb", "AUZA"):
            t = by_label(run(PROP.replace(good, bad)))
            self.assertEqual(t["idc"]["verdict"], "VOID", bad)
        t = by_label(run(PROP.replace("( wi ax-1 ax-2 mp ) " + good, "( wi ax-1 " + good)))
        self.assertEqual(t["idc"]["verdict"], "VOID")

    def test_malformed_database(self):
        for text in ("$c a $. ${ $c b $. $}", "$c a $. $v a $.", "$c w $. $v x $. l $f w x $. "
                     "l $a w x $.", "$c w $. $v x $. a $a w x $.", "$c w $. a $a w y $.",
                     "$c w $. ${", "$c w $. $}", "$c w $. $[ other.mm $]",
                     "$( never closed", "$c w $. $v x y $. $d x x $.", "$c w $. a w $.",
                     "$c w $. a $a w", "$v x $. a $a x $."):
            rep = run(text)
            self.assertIsNotNone(rep["file_void"], text)
            self.assertFalse(rep["whole_file_read"], text)

    def test_never_pass_when_unread(self):
        rep = run(PROP, limit=1)
        self.assertEqual(rep["provable_statements"], 1)
        self.assertFalse(rep["whole_file_read"])
        self.assertIn("limit", rep["stopped"])
        rep = run(PROP, until="idc")
        self.assertEqual(rep["provable_statements"], 2)


class TestScopes(unittest.TestCase):
    def test_variable_reuse_after_scope(self):
        text = ("$c w |- $. ${ $v x $. fx $f w x $. a1 $a |- x $. $} "
                "${ $v x $. gx $f w x $. t $p |- x $= gx a1 $. $}")
        self.assertEqual(run(text)["counts"]["PASS"], 1)

    def test_hypothesis_order_is_database_order(self):
        # $e before a later $f: the mandatory hypotheses keep that order
        text = ("$c w |- $. $v x y $. fx $f w x $. ${ e1 $e |- x $. fy $f w y $. "
                "ax $a |- y $. $} ${ h $e |- x $. t $p |- x $= fx h fx ax $. $}")
        rep = run(text)
        self.assertEqual(rep["counts"]["PASS"], 1, rep["theorem_records"])
        bad = text.replace("$= fx h fx ax $.", "$= fx fx h ax $.")
        self.assertEqual(run(bad)["counts"]["FAIL"], 1)


class TestCli(unittest.TestCase):
    def cli(self, *args):
        return subprocess.run([sys.executable, "-m", "kernel", *args], cwd=ROOT,
                              capture_output=True, text=True)

    def test_exit_codes(self):
        self.assertEqual(self.cli("check", "tests/data/prop.mm").returncode, 0)
        self.assertEqual(self.cli().returncode, 2)
        self.assertEqual(self.cli("check", "no/such/file.mm").returncode, 2)
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "x.mm"
            f.write_text(PROP.replace("  wp wp ax-1\n", "  wp wq ax-1\n", 1))
            r = self.cli("check", str(f))
            self.assertEqual(r.returncode, 1)
            self.assertIn("step 40", r.stdout)
            f.write_text(PROP.replace("idd $p", "$x idd $p"))
            self.assertEqual(self.cli("check", str(f)).returncode, 3)
            f.write_text(PROP.replace("mp mp $.", "mp ? $."))
            self.assertEqual(self.cli("check", str(f)).returncode, 3)
            f.write_bytes(b"$c \xff $.")
            self.assertEqual(self.cli("check", str(f)).returncode, 3)


if __name__ == "__main__":
    unittest.main()
