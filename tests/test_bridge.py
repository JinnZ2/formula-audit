"""Tests for kernel.bridge (the proposals -> kernel seam). Co-authored."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from kernel.bridge import BridgeVoid, check_proof, entry_id, prove, translate  # noqa: E402
from kernel import check_lines  # noqa: E402

DB = (ROOT / "tests" / "data" / "algebra.mm").read_text()
PROOF = (ROOT / "tests" / "data" / "proofs" / "x_times_x.mm").read_text()
SQ = {"lhs": "x*x", "rhs": "x**2", "domain": {"x": {"lo": "0", "hi": "1"}},
      "status": "PROPOSED", "proof": None, "proof_attempted": False}
SQRT = {"lhs": "sqrt(x)**2", "rhs": "x", "domain": {"x": {"lo": "1", "hi": "2"}},
        "status": "PROPOSED", "proof": None, "proof_attempted": False}
POLY = dict(SQ, status="DERIVED", proof={"method": "polynomial_identity_by_points",
                                          "degrees": {"x": 2}, "grid_size": 3},
            proof_attempted=True)


class Work:
    """A proposals.json and a proofs/ folder in a temporary directory."""

    def __init__(self, entries):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.path = self.dir / "proposals.json"
        self.path.write_text(json.dumps({"proposals": copy.deepcopy(entries)}))
        (self.dir / "proofs").mkdir()

    def put(self, entry, text):
        (self.dir / "proofs" / f"{entry_id(entry)[0]}.mm").write_text(text)

    def run(self, now="2026-11-16T00:00:00+00:00", **kw):
        return prove(self.path, now=now, **kw)

    def entries(self):
        return json.loads(self.path.read_text())["proposals"]

    def close(self):
        self.tmp.cleanup()


class TestDatabase(unittest.TestCase):
    def test_algebra_axioms_are_given_input(self):
        rep = check_lines(DB.splitlines()).report()
        self.assertIsNone(rep["file_void"])
        self.assertEqual(rep["provable_statements"], 0)          # nothing proved in it
        self.assertGreater(rep["axioms"]["count"], 50)
        for a in rep["axiom_records"]:
            self.assertEqual((a["status"], a["verdict"]), ("OBSERVED", None))


class TestTranslate(unittest.TestCase):
    def test_statements(self):
        t = translate(SQ)
        self.assertEqual(" ".join(t["statement"]), "|- ( v0 * v0 ) = ( v0 ^ 2 )")
        self.assertEqual([" ".join(h) for h in t["hypotheses"]], ["|- 0 <_ v0", "|- v0 <_ 1"])
        self.assertEqual(t["variables"], {"x": "v0"})
        t = translate(SQRT)
        self.assertEqual(" ".join(t["statement"]), "|- ( ( sqrt v0 ) ^ 2 ) = v0")
        t = translate({"lhs": "(a + b)*y/2", "rhs": "-y + x**(1/2) - 1.5",
                       "domain": {"y": {"lo": "-1", "hi": "1/2"}, "a": {"lo": 0, "hi": 9},
                                  "x": {"lo": 0, "hi": 4}},
                       "fixed": {"b": "3"}, "status": "PROPOSED"})
        self.assertEqual(t["variables"], {"a": "v0", "x": "v1", "y": "v2"})
        self.assertEqual(" ".join(t["statement"]),
                         "|- ( ( ( v0 + 3 ) * v2 ) / 2 ) = ( ( -u v2 + ( sqrt v1 ) ) - ( 3 / 2 ) )")
        self.assertIn("|- -u 1 <_ v2", [" ".join(h) for h in t["hypotheses"]])
        self.assertIn("|- v2 <_ ( 1 / 2 )", [" ".join(h) for h in t["hypotheses"]])

    def test_every_translation_is_well_formed_in_the_database(self):
        # the kernel must be able to read the statement: wrap it as a $p with a "?" proof
        for e in (SQ, SQRT):
            t = translate(e)
            text = DB + "\n${ " + " ".join(f"h{i} $e {' '.join(h)} $." for i, h
                                           in enumerate(t["hypotheses"])) \
                + f" target $p {' '.join(t['statement'])} $= ? $. $}}"
            rep = check_lines(text.splitlines()).report()
            self.assertIsNone(rep["file_void"])
            self.assertEqual(rep["theorem_records"][0]["void_reason"], "incomplete proof: ? step")

    def test_untranslatable_is_void_with_reason(self):
        cases = {"sin(x)": "the function sin", "x**10": "power 10", "x**(1/3)": "power 1/3",
                 "x*12": "integer 12", "x + k": "neither a domain nor a fixed value",
                 "x**y": "not a literal number", "x if x else 1": "not translatable",
                 "x +": "does not parse", "x % 2": "operator Mod"}
        for text, why in cases.items():
            with self.assertRaises(BridgeVoid, msg=text) as c:
                translate(dict(SQ, lhs=text))
            self.assertIn(why, str(c.exception), text)
        for bad in ({}, "x", dict(SQ, status="sure"), dict(SQ, domain=None),
                    dict(SQ, domain={"x": {"lo": "0"}}), dict(SQ, lhs=""),
                    dict(SQ, domain={"x": {"lo": "0", "hi": "30"}}),
                    dict(SQ, domain={"x": {"lo": "a", "hi": "1"}})):
            with self.assertRaises(BridgeVoid):
                translate(bad)

    def test_id(self):
        short, full = entry_id(SQ)
        self.assertEqual((len(short), len(full), full[:16]), (16, 64, short))
        self.assertEqual(entry_id(dict(SQ, status="DERIVED", source_check={}))[0], short)
        self.assertNotEqual(entry_id(dict(SQ, rhs="x**3"))[0], short)
        self.assertNotEqual(entry_id(dict(SQ, domain={"x": {"lo": "0", "hi": "2"}}))[0], short)


class TestCheckProof(unittest.TestCase):
    def test_hand_proof_passes(self):
        r = check_proof(translate(SQ), PROOF, DB)
        self.assertEqual(r["verdict"], "PASS")
        self.assertEqual((r["labels"], r["steps"]), (["target"], 24))
        self.assertEqual(r["axioms"]["status"], "OBSERVED")

    def test_broken_step_fails_located(self):
        bad = PROOF.replace("tv0 exp2", "tv0 exp3")
        self.assertNotEqual(bad, PROOF)
        r = check_proof(translate(SQ), bad, DB)
        self.assertEqual(r["verdict"], "FAIL")
        e = r["located"]
        self.assertEqual((e["label"], e["step"], e["step_label"]), ("target", 24, "ax-mp"))
        self.assertIn("min", e["rule"])
        self.assertEqual(e["expected"], "|- ( v0 ^ 2 ) = ( v0 * v0 )")
        self.assertEqual(e["got"], "|- ( v0 ^ 3 ) = ( ( v0 ^ 2 ) * v0 )")
        self.assertIsNotNone(e["line_in_proof_file"])

    def test_a_proof_file_may_not_declare_anything(self):
        for cheat in ("cheat $a |- ( v0 * v0 ) = ( v0 ^ 2 ) $.\n" + PROOF,
                      "$c magic $.\n" + PROOF, "$v w $.\n" + PROOF,
                      "$d v0 v1 $.\n" + PROOF, "$[ other.mm $]\n" + PROOF):
            r = check_proof(translate(SQ), cheat, DB)
            self.assertEqual(r["verdict"], "VOID", cheat[:20])
            self.assertIn("only $e and $p", r["reason"])
        # a keyword inside a comment is only a comment
        self.assertEqual(check_proof(translate(SQ), "$( no $a here $)\n" + PROOF, DB)["verdict"],
                         "PASS")

    def test_target_must_be_the_translated_statement(self):
        other = dict(SQ, rhs="x**3")                         # the proof proves something else
        r = check_proof(translate(other), PROOF, DB)
        self.assertEqual(r["verdict"], "FAIL")
        self.assertIn("not the translated statement", r["located"]["rule"])
        self.assertEqual(r["located"]["expected"], "|- ( v0 * v0 ) = ( v0 ^ 3 )")
        r = check_proof(translate(SQ), PROOF.replace("target $p", "lemma $p"), DB)
        self.assertEqual(r["verdict"], "VOID")
        self.assertIn('"target"', r["reason"])

    def test_target_may_not_assume_more_than_the_domain(self):
        free = ("${ gift $e |- ( v0 * v0 ) = ( v0 ^ 2 ) $.\n"
                "   target $p |- ( v0 * v0 ) = ( v0 ^ 2 ) $= gift $. $}")
        r = check_proof(translate(SQ), free, DB)
        self.assertEqual(r["verdict"], "FAIL")
        self.assertIn("not a domain bound", r["located"]["rule"])
        # a wider domain bound is not the stated one either
        r = check_proof(translate(SQ), PROOF.replace("|- v0 <_ 1", "|- v0 <_ 2"), DB)
        self.assertEqual(r["verdict"], "FAIL")

    def test_lemmas_and_void_proofs(self):
        lemma = ("lem $p |- ( v0 ^ 2 ) = ( v0 * v0 ) $= tv0 exp2 $.\n"
                 "target $p |- ( v0 * v0 ) = ( v0 ^ 2 ) $=\n"
                 " tv0 n2 tpow tv0 tv0 tmul weq tv0 tv0 tmul tv0 n2 tpow weq\n"
                 " tv0 lem tv0 n2 tpow tv0 tv0 tmul eqcom ax-mp $.")
        r = check_proof(translate(SQ), lemma, DB)
        self.assertEqual((r["verdict"], r["labels"]), ("PASS", ["lem", "target"]))
        r = check_proof(translate(SQ), lemma.replace("tv0 exp2 $.", "tv0 exp3 $."), DB)
        self.assertEqual((r["verdict"], r["located"]["label"]), ("FAIL", "lem"))
        r = check_proof(translate(SQ), PROOF.replace("ax-mp $.", "? $."), DB)
        self.assertEqual(r["verdict"], "VOID")                  # incomplete: never PASS
        r = check_proof(translate(SQ), PROOF.replace("$}", ""), DB)
        self.assertEqual(r["verdict"], "VOID")
        r = check_proof(translate(SQ), "tt $p |- v0 = v0 $= tv0 eqid $.\n" + PROOF, DB)
        self.assertEqual(r["verdict"], "VOID")                  # label already in the database
        self.assertEqual(check_proof(translate(SQ), PROOF, "$c a $. $x")["verdict"], "VOID")


class TestProve(unittest.TestCase):
    def test_kernel_pass_makes_a_proposed_entry_derived(self):
        w = Work([SQ])
        w.put(SQ, PROOF)
        rep = w.run()
        e = w.entries()[0]
        self.assertEqual(rep["counts"], {"PASS": 1, "FAIL": 0, "VOID": 0, "NO_PROOF": 0})
        self.assertEqual((e["status"], e["proof"], e["proof_attempted"], e["routes"]),
                         ("DERIVED", "kernel", True, ["kernel"]))
        self.assertEqual(e["history"], [{"at": "2026-11-16T00:00:00+00:00", "route": "kernel",
                                         "from": "PROPOSED", "to": "DERIVED",
                                         "note": "kernel PASS against algebra.mm"}])
        self.assertEqual(e["kernel"]["statement"], "|- ( v0 * v0 ) = ( v0 ^ 2 )")
        self.assertEqual(e["kernel"]["checks"][0]["verdict"], "PASS")
        self.assertEqual(e["id"], entry_id(SQ)[0])
        # a second run changes nothing and appends nothing
        text = w.path.read_text()
        rep = w.run(now="2027-01-01T00:00:00+00:00")
        self.assertFalse(rep["written"])
        self.assertEqual(w.path.read_text(), text)
        w.close()

    def test_broken_proof_leaves_the_entry_proposed(self):
        w = Work([SQ])
        w.put(SQ, PROOF.replace("tv0 exp2", "tv0 exp3"))
        rep = w.run()
        e = w.entries()[0]
        self.assertEqual(rep["counts"]["FAIL"], 1)
        self.assertEqual((e["status"], e["proof"], e["proof_attempted"]),
                         ("PROPOSED", None, True))
        self.assertNotIn("history", e)                          # no status change
        c = e["kernel"]["checks"][0]
        self.assertEqual((c["verdict"], c["located"]["step"], c["located"]["step_label"]),
                         ("FAIL", 24, "ax-mp"))
        # the proof is then repaired: the failed check stays in the log
        w.put(SQ, PROOF)
        w.run(now="2026-11-17T00:00:00+00:00")
        e = w.entries()[0]
        self.assertEqual(e["status"], "DERIVED")
        self.assertEqual([c["verdict"] for c in e["kernel"]["checks"]], ["FAIL", "PASS"])
        self.assertEqual(e["history"][0]["at"], "2026-11-17T00:00:00+00:00")
        w.close()

    def test_no_proof_file_stays_proposed(self):
        w = Work([SQRT])
        rep = w.run()
        e = w.entries()[0]
        self.assertEqual(rep["counts"]["NO_PROOF"], 1)
        self.assertEqual(rep["records"][0]["reason"], "NO_PROOF")
        self.assertIsNone(rep["records"][0]["kernel_verdict"])
        self.assertEqual((e["status"], e["proof"], e["proof_attempted"]),
                         ("PROPOSED", None, False))
        self.assertEqual(e["kernel"]["reason"], "NO_PROOF")
        self.assertEqual(e["kernel"]["statement"], "|- ( ( sqrt v0 ) ^ 2 ) = v0")
        self.assertEqual(e["kernel"]["checks"], [])
        self.assertNotIn("history", e)
        w.close()

    def test_bad_expression_is_void_and_the_entry_is_unchanged(self):
        bad = dict(SQ, lhs="sin(x)*x")
        w = Work([bad, SQ, "not a record"])
        w.put(SQ, PROOF)
        rep = w.run()
        got = w.entries()
        self.assertEqual(rep["counts"], {"PASS": 1, "FAIL": 0, "VOID": 2, "NO_PROOF": 0})
        self.assertEqual(got[0], bad)                           # exactly as it was
        self.assertEqual(got[2], "not a record")
        self.assertIn("the function sin", rep["records"][0]["reason"])
        self.assertEqual(rep["records"][2]["reason"], "entry is not a record")
        self.assertEqual(got[1]["status"], "DERIVED")           # the others are still done
        w.close()

    def test_polynomial_route_is_left_and_a_kernel_route_is_added(self):
        w = Work([POLY])
        rep = w.run()                                            # no proof file yet
        e = w.entries()[0]
        self.assertEqual((e["status"], e["proof"], e["routes"]),
                         ("DERIVED", POLY["proof"], ["polynomial_identity_by_points"]))
        self.assertNotIn("history", e)
        self.assertEqual(rep["records"][0]["reason"], "NO_PROOF")
        w.put(POLY, PROOF)
        w.run()
        e = w.entries()[0]
        self.assertEqual(e["status"], "DERIVED")
        self.assertEqual(e["proof"], POLY["proof"])              # left as it was
        self.assertEqual(e["routes"], ["polynomial_identity_by_points", "kernel"])
        self.assertEqual((e["history"][0]["from"], e["history"][0]["to"], e["history"][0]["route"]),
                         ("DERIVED", "DERIVED", "kernel"))
        self.assertIn("second, independent route", e["history"][0]["note"])
        w.close()

    def test_a_kernel_route_that_stops_checking_is_withdrawn_not_erased(self):
        w = Work([SQ])
        w.put(SQ, PROOF)
        w.run(now="2026-11-16T00:00:00+00:00")
        w.put(SQ, PROOF.replace("tv0 exp2", "tv0 exp3"))
        w.run(now="2026-11-18T00:00:00+00:00")
        e = w.entries()[0]
        self.assertEqual((e["status"], e["proof"], e["routes"]), ("PROPOSED", None, []))
        self.assertEqual([(h["from"], h["to"]) for h in e["history"]],
                         [("PROPOSED", "DERIVED"), ("DERIVED", "PROPOSED")])
        self.assertEqual([c["verdict"] for c in e["kernel"]["checks"]], ["PASS", "FAIL"])
        w.close()

    def test_malformed_file_is_void_and_never_written(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "proposals.json"
            for text in ("not json", '{"proposals": 3}', '"x"', '{"other": []}'):
                p.write_text(text)
                rep = prove(p)
                self.assertIsNotNone(rep["file_void"], text)
                self.assertEqual(rep["records"], [])
                self.assertFalse(rep["written"])
                self.assertEqual(p.read_text(), text)
            self.assertIsNotNone(prove(Path(d) / "missing.json")["file_void"])
            p.write_text(json.dumps([SQ]))
            self.assertIn("database", prove(p, db_path=Path(d) / "none.mm")["file_void"])

    def test_dry_run_writes_nothing(self):
        w = Work([SQ])
        w.put(SQ, PROOF)
        text = w.path.read_text()
        rep = w.run(write=False)
        self.assertEqual((rep["counts"]["PASS"], rep["written"]), (1, False))
        self.assertEqual(w.path.read_text(), text)
        w.close()


class TestCli(unittest.TestCase):
    def cli(self, *args):
        return subprocess.run([sys.executable, "-m", "kernel", *args], cwd=ROOT,
                              capture_output=True, text=True)

    def test_exit_codes(self):
        w = Work([SQ])
        w.put(SQ, PROOF)
        r = self.cli("prove", str(w.path))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("PROPOSED -> DERIVED", r.stdout)
        self.assertIn("rests on the database's axioms", r.stdout)
        w.close()
        w = Work([SQ, SQRT])
        w.put(SQ, PROOF)
        self.assertEqual(self.cli("prove", str(w.path)).returncode, 3)      # one still open
        w.put(SQRT, PROOF)                                                   # the wrong proof
        r = self.cli("prove", str(w.path))
        self.assertEqual(r.returncode, 1)
        self.assertIn("not the translated statement", r.stdout)
        w.path.write_text("not json")
        self.assertEqual(self.cli("prove", str(w.path)).returncode, 3)
        self.assertEqual(self.cli("prove").returncode, 2)
        w.close()

    def test_from_numcheck_to_kernel(self):
        # the whole seam: numcheck writes the candidate, the kernel checks the hand proof
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "c.json").write_text(json.dumps([
                {"formula": "x*x = x**2", "values": {"x": {"value": [0, 1], "unit": "m"}}},
                {"formula": "sqrt(x)**2 = x", "values": {"x": {"value": [1, 2], "unit": "m**2"}}}]))
            subprocess.run([sys.executable, "-m", "numcheck", "check", str(d / "c.json"),
                            "--proposals", str(d / "proposals.json")], cwd=ROOT,
                           capture_output=True, text=True)
            first = json.loads((d / "proposals.json").read_text())["proposals"]
            (d / "proofs").mkdir()
            (d / "proofs" / f"{entry_id(first[0])[0]}.mm").write_text(PROOF)
            r = self.cli("prove", str(d / "proposals.json"), "--json")
            rep = json.loads(r.stdout)
            self.assertEqual(rep["counts"], {"PASS": 1, "FAIL": 0, "VOID": 0, "NO_PROOF": 1})
            got = json.loads((d / "proposals.json").read_text())["proposals"]
            self.assertEqual(got[0]["routes"], ["polynomial_identity_by_points", "kernel"])
            self.assertEqual((got[1]["status"], got[1]["kernel"]["reason"]),
                             ("PROPOSED", "NO_PROOF"))
            self.assertEqual(got[0]["source_check"], first[0]["source_check"])   # nothing lost
            self.assertEqual(r.returncode, 3)


if __name__ == "__main__":
    unittest.main()
