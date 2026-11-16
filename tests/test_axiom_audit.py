"""Tests for kernel.axiom_audit. Co-authored. set.mm is not needed here."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from kernel.axiom_audit import (Reader, SETMM, Surd, antecedents, audit,  # noqa: E402
                                exact_sqrt, guard_row, step2_equation, step3_samples,
                                truth_table, _xcmp, _xmul)

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
            for q in a["setmm"]["quoted"]:                    # from the recorded quotes file
                self.assertIsNotNone(q, a["label"])
        self.assertIn("setmm_quotes.json", REP["quotes_source"])

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

    def test_guard_table_is_all_ok(self):
        s = REP["summary"]
        self.assertEqual(s["guard_verdicts"], {"GUARD_OK": 45, "GUARD_WEAKER": 0, "UNCLEAR": 0})
        self.assertEqual((s["seam_pass_route"], s["consistency_status"], s["second_reader"]),
                         ("OPEN", "DERIVED", "VOID"))
        rows = {g["label"]: g for g in REP["guard_table"]}
        self.assertEqual(len(rows), 45)
        for a in REP["axioms"]:                      # every conditional axiom has a row
            if a["class"] == "conditional":
                self.assertIn(a["label"], rows)
                self.assertEqual(a["truth_in_model"]["status"], "DERIVED")
        g = rows["divmul"]
        self.assertEqual((g["algebra_guards"], g["setmm_guards"], g["setmm_typing"]),
                         (["-. r = 0"], ["B =/= 0"], ["A e. CC", "B e. CC"]))
        g = rows["sqrtsq"]
        self.assertEqual((g["algebra_guards"], g["setmm_guards"]), (["0 <_ t"], ["0 <_ A"]))
        self.assertEqual(rows["lemul"]["setmm_guards"], ["0 <_ A", "0 <_ B"])
        self.assertEqual(rows["letr"]["algebra_guards"], ["t <_ r", "r <_ s"])
        self.assertEqual(rows["addcom"]["reason"], "set.mm has typing antecedents only")
        c = REP["consistency"]
        self.assertEqual((c["status"], c["second_reader"], c["blocked_by"]),
                         ("DERIVED", "VOID", []))
        self.assertIn("guard table", c["rests_on"])

    def test_a_weaker_guard_is_seen(self):
        rows = {g["label"]: g for g in REP["guard_table"]}
        axioms = {a["label"]: a for a in REP["axioms"]}
        for label, weaker in (("sqrtsq", "|- ( ( sqrt t ) * ( sqrt t ) ) = t"),
                              ("divmul", "|- ( ( t / r ) * r ) = t"),
                              ("lemul", "|- ( 0 <_ t -> 0 <_ ( t * r ) )"),
                              ("letr", "|- ( t <_ r -> t <_ s )"),
                              ("sqrtge0", "|- ( 0 <_ r -> 0 <_ ( sqrt t ) )")):   # wrong variable
            fake = dict(axioms[label], statement=weaker)
            g = guard_row(fake, fake["setmm"]["quoted"])
            self.assertEqual(g["verdict"], "GUARD_WEAKER", label)
            self.assertTrue(g["not_covered"])
            self.assertEqual(rows[label]["verdict"], "GUARD_OK")
        g = guard_row(axioms["sqrtsq"], None)
        self.assertEqual(g["verdict"], "UNCLEAR")
        # more guards on the algebra side is the safe direction
        fake = dict(axioms["addcom"], statement="|- ( 0 <_ t -> ( t + r ) = ( r + t ) )")
        self.assertEqual(guard_row(fake, fake["setmm"]["quoted"])["verdict"], "GUARD_OK")

    def test_antecedents(self):
        self.assertEqual(antecedents("( ( A e. RR /\\ 0 <_ A ) -> X )".split()),
                         ["A e. RR", "0 <_ A"])
        self.assertEqual(antecedents("( ( A e. RR /\\ B e. RR /\\ C e. RR ) -> "
                                     "( ( A <_ B /\\ B <_ C ) -> A <_ C ) )".split()),
                         ["A e. RR", "B e. RR", "C e. RR", "A <_ B", "B <_ C"])
        self.assertEqual(antecedents("( ( ( A e. RR /\\ 0 <_ A ) /\\ ( B e. RR /\\ 0 <_ B ) )"
                                     " -> 0 <_ ( A x. B ) )".split()),
                         ["A e. RR", "0 <_ A", "B e. RR", "0 <_ B"])
        self.assertEqual(antecedents("( A + B ) = ( B + A )".split()), [])
        self.assertEqual(antecedents("( A <_ B \\/ B <_ A )".split()), [])

    def test_sqrt_samples_are_decided_exactly(self):
        self.assertEqual(REP["summary"]["samples_not_decided"], 0)
        from fractions import Fraction as F
        self.assertEqual(exact_sqrt(F(9, 4)), F(3, 2))
        self.assertEqual(exact_sqrt(F(0)), 0)
        r = exact_sqrt(F(1, 2))                       # sqrt(1/2) = (1/2) sqrt 2
        self.assertEqual((r.c, r.n), (F(1, 2), 2))
        r = exact_sqrt(F(18))
        self.assertEqual((r.c, r.n), (F(3), 2))
        self.assertEqual(_xmul(exact_sqrt(F(2)), exact_sqrt(F(2))), 2)       # squared back
        self.assertEqual(_xmul(exact_sqrt(F(1, 2)), exact_sqrt(F(1, 2))), F(1, 2))
        self.assertEqual(_xcmp(exact_sqrt(F(2)), exact_sqrt(F(2))), 0)
        self.assertEqual(_xcmp(exact_sqrt(F(2)), F(3, 2)), -1)               # 2 < 9/4
        self.assertEqual(_xcmp(F(3, 2), exact_sqrt(F(2))), 1)
        self.assertEqual(_xcmp(Surd(F(-1), 2), F(0)), -1)
        self.assertEqual(_xcmp(exact_sqrt(F(2)), exact_sqrt(F(3))), -1)
        # a false sqrt statement at a non-square point is now FALSE, not undecided
        r = step3_samples(rd("( 0 <_ t -> ( ( sqrt t ) * ( sqrt t ) ) = ( t + t ) )"), [])
        self.assertEqual(r["result"], "FAILS")
        r = step3_samples(rd("( 0 <_ t -> ( sqrt t ) <_ t )"), [])            # false at t = 1/2
        self.assertEqual(r["result"], "FAILS")
        self.assertEqual(r["first_counterexample"]["at"], {"t": "1/2"})

    def test_truth_table(self):
        self.assertEqual(truth_table(rd("( ph -> ( ps -> ph ) )"), [])["result"], "DERIVED")
        self.assertEqual(truth_table(rd("( ph -> ps )"), [])["result"], "FAILS")
        self.assertEqual(truth_table(rd("ps"), [rd("ph"), rd("( ph -> ps )")])["result"],
                         "DERIVED")                            # modus ponens as a rule
        self.assertEqual(truth_table(rd("ph"), [rd("ps"), rd("( ph -> ps )")])["result"],
                         "FAILS")                              # affirming the consequent


if __name__ == "__main__":
    unittest.main()
