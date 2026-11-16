"""Tests for kernel.axiom_audit. Co-authored. set.mm is not needed here."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from kernel.axiom_audit import (Reader, SETMM, audit, step2_equation,  # noqa: E402
                                step3_samples, truth_table)

REP = audit()
TV, WV = {"t", "r", "s"}, {"ph", "ps", "ch"}


def rd(text):
    return Reader(text.split(), TV, WV).whole_wff()


class TestAudit(unittest.TestCase):
    def test_no_axiom_fails(self):
        s = REP["summary"]
        self.assertEqual(s["FAILS"], [])
        self.assertEqual(s["statements"], 83)
        self.assertEqual(s["by_class"], {"syntax": 22, "propositional": 7, "equational": 28,
                                         "conditional": 26})
        self.assertEqual(s["DERIVED"] + s["PROPOSED_sampled"] + s["by_class"]["syntax"], 83)
        for a in REP["axioms"]:
            self.assertEqual((a["kernel_status"], a["kernel_verdict"]), ("OBSERVED", None))
            self.assertNotEqual(a["class"], "unreadable", a["label"])

    def test_equational_axioms_are_proved_or_exact(self):
        for a in REP["axioms"]:
            if a["class"] == "equational":
                self.assertIn(a["step2"]["result"], ("DERIVED", "HOLDS"), a["label"])
                self.assertIsNone(a["step3"], a["label"])
            if a["class"] == "propositional":
                self.assertEqual(a["step2"]["method"], "truth_table")
            if a["class"] == "conditional":
                self.assertEqual(a["step3"]["samples"]["false"], 0, a["label"])
                self.assertEqual(a["step3"]["status"], "PROPOSED")      # evidence only
                self.assertTrue(a["step3"]["evidence_only"])
                self.assertTrue(a["verdict"].startswith("PROPOSED"))

    def test_every_axiom_has_a_map_entry(self):
        self.assertEqual(REP["summary"]["UNMAPPED"], [])
        for a in REP["axioms"]:
            self.assertIn(a["label"], SETMM)
            self.assertIsNone(a["setmm"]["quoted"])           # no set.mm given: nothing quoted

    def test_mutants_are_caught(self):
        m = REP["mutation"]
        self.assertGreater(m["mutants"], 60)
        # the one mutant not caught is a true statement: t - 0 = t
        self.assertEqual([(x["label"], x["mutant"]) for x in m["not_caught"]],
                         [("add0", "(t - 0) = t")])
        self.assertEqual(m["caught"], m["mutants"] - 1)

    def test_planted_equational_faults_fail_step_2(self):
        for text in ("( t * ( r + s ) ) = ( ( t * r ) - ( t * s ) )",      # sign flipped
                     "( t * ( r + s ) ) = ( ( t * r ) + s )",
                     "( ( t * r ) * s ) = ( t * ( r + s ) )",
                     "( t ^ 3 ) = ( ( t ^ 2 ) * ( t * t ) )",
                     "5 = ( 3 + 1 )", "( t + -u t ) = t"):
            w = rd(text)
            self.assertEqual(step2_equation(w[1], w[2])["result"], "FAILS", text)
        w = rd("( t * ( r + s ) ) = ( ( t * r ) + ( t * s ) )")
        self.assertEqual(step2_equation(w[1], w[2])["result"], "DERIVED")

    def test_planted_conditional_faults_fail_step_3(self):
        for text in ("( ( sqrt t ) * ( sqrt t ) ) = t",                    # guard removed
                     "( ( t / r ) * r ) = t", "0 <_ ( sqrt t )",
                     "( -. t <_ r -> t <_ r )", "( 0 <_ t -> 0 <_ ( t * r ) )",
                     "( ( t = r /\\ r = s ) -> t = 0 )"):
            r = step3_samples(rd(text), [])
            self.assertEqual(r["result"], "FAILS", text)
            self.assertIsNotNone(r["first_counterexample"])
        # with its guard, the same statement has no counterexample
        r = step3_samples(rd("( 0 <_ t -> ( ( sqrt t ) * ( sqrt t ) ) = t )"), [])
        self.assertEqual((r["result"], r["samples"]["false"]), ("no counterexample", 0))

    def test_truth_table(self):
        self.assertEqual(truth_table(rd("( ph -> ( ps -> ph ) )"), [])["result"], "DERIVED")
        self.assertEqual(truth_table(rd("( ph -> ps )"), [])["result"], "FAILS")
        self.assertEqual(truth_table(rd("ps"), [rd("ph"), rd("( ph -> ps )")])["result"],
                         "DERIVED")                            # modus ponens as a rule
        self.assertEqual(truth_table(rd("ph"), [rd("ps"), rd("( ph -> ps )")])["result"],
                         "FAILS")                              # affirming the consequent


if __name__ == "__main__":
    unittest.main()
