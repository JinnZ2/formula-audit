"""Tests for infer (branch 5). Co-authored."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from fractions import Fraction as F
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from infer import rank, read_json, record_sha, replay, verify_check  # noqa: E402
from kernel import check_file  # noqa: E402
from numcheck import check_all  # noqa: E402

SNOW = read_json((ROOT / "case_snow.json").read_text())


def hyp(i, prior=None, source="a stated source", flag=None):
    return {"id": i, "prior": prior, "prior_source": source if prior else None,
            "prior_flag": flag}


def ev(i, kind, target, lr, tags=(), status="OBSERVED", **kw):
    e = {"id": i, "type": kind, "lr": lr, "provenance": "p", "shared_ancestry": list(tags),
         "status": status, **kw}
    if kind == "shadow":
        e["consistent_with"] = target if isinstance(target, list) else [target]
        e.setdefault("alternative_casters", ["something else"])
    else:
        e["hypothesis"] = target
    if kind == "cross_domain":
        e.setdefault("constraints", [{"name": "c1", "matched": True}])
    return e


def run(evidence, hyps=None, base_dir=None, **kw):
    return rank({"hypotheses": hyps or [hyp("a", "1/2"), hyp("b", "1/2")],
                 "evidence": evidence, **kw}, base_dir=base_dir)


def post(rep):
    return {h["id"]: F(h["posterior"]) for h in rep["hypotheses"]}


class TestSnow(unittest.TestCase):
    def test_worked_case(self):
        r = rank(SNOW)
        self.assertEqual((r["verdict"], r["status"]), ("RANKED", "PROPOSED"))
        # the prior flag on miasma: its 9/10 is not used; the set goes flat
        self.assertEqual(r["log"][1]["op"], "FLAT_PRIOR")
        self.assertEqual(r["log"][1]["flags"], {"miasma": "normalization"})
        self.assertEqual(r["log"][1]["priors_given"], {"miasma": "9/10", "water": "1/10"})
        h = {x["id"]: x for x in r["hypotheses"]}
        self.assertEqual((h["miasma"]["prior_used"], h["water"]["prior_used"]), ("1/2", "1/2"))
        self.assertEqual(h["miasma"]["prior_flag"], "normalization")
        # the shadow (pump cluster): alternative casters listed, lr 8 capped at 3
        e = {x["id"]: x for x in r["evidence"]}
        self.assertEqual((e["pump_cluster"]["lr_given"], e["pump_cluster"]["lr_effective"],
                          e["pump_cluster"]["capped"]), ("8", "3", True))
        # same inquiry twice: only the stronger counts
        self.assertEqual((e["spared_groups"]["outcome"], e["handle_removed"]["outcome"]),
                         ("APPLY", "NO_UPDATE"))
        self.assertIn("inquiry_1854", e["handle_removed"]["reason"])
        # a declared constraint is not matched: no update
        self.assertEqual(e["poison_analogy"]["outcome"], "NO_UPDATE")
        self.assertIn("more consumed, more harm", e["poison_analogy"]["reason"])
        # 1/2 x 3 x 5 against 1/2
        self.assertEqual(post(r), {"miasma": F(1, 16), "water": F(15, 16)})
        self.assertEqual([x["id"] for x in r["ranking"]], ["water", "miasma"])
        # two independent types raise water: RISING. Inference only: PROPOSED, not more
        self.assertEqual((h["water"]["direction"], h["water"]["status"]), ("RISING", "PROPOSED"))
        self.assertEqual((h["miasma"]["direction"], h["miasma"]["status"]),
                         ("NO_SIGNAL", "PROPOSED"))
        self.assertEqual(r["caps"]["status"], "PROPOSED")
        self.assertIsNone(r["human_interest"])
        self.assertIsNone(r["ai_interest"])

    def test_without_the_flag_the_prior_stands(self):
        case = copy.deepcopy(SNOW)
        del case["hypotheses"][0]["prior_flag"]
        r = rank(case)
        self.assertEqual(r["log"][1]["op"], "PRIOR")
        self.assertEqual(post(r)["water"], F(15, 24))          # (1/10 x 15) / (1/10 x 15 + 9/10)


class TestHypotheses(unittest.TestCase):
    def test_single_rival_is_void(self):
        r = rank({"hypotheses": [hyp("only", "1")], "evidence": []})
        self.assertEqual((r["verdict"], r["status"]), ("VOID", None))
        self.assertIn("one alone", r["void_reason"])
        self.assertEqual(r["hypotheses"], [])
        for bad in ([], None, "x"):
            self.assertEqual(rank({"hypotheses": bad})["verdict"], "VOID")

    def test_prior_flags(self):
        for flag in ("normalization", "superiority", "convenience", "unknown"):
            r = run([], [hyp("a", "9/10", flag=flag), hyp("b", "1/10")])
            self.assertEqual(post(r), {"a": F(1, 2), "b": F(1, 2)}, flag)
            self.assertEqual(r["log"][1]["flags"], {"a": flag})
        r = run([], [hyp("a", "9/10", source=None), hyp("b", "1/10")])     # no source: unknown
        self.assertEqual(r["log"][1]["flags"], {"a": "unknown"})
        r = run([], [hyp("a"), hyp("b", "1/10"), hyp("c", "2/10")])        # no prior: unknown
        self.assertEqual(post(r)["c"], F(1, 3))
        r = run([], [hyp("a", "3/10"), hyp("b", "1/10")])                  # normalised, logged
        self.assertEqual(post(r)["a"], F(3, 4))
        self.assertIn("normalised", r["log"][1]["reason"])

    def test_bad_sets_are_void(self):
        for hs in ([hyp("a", "1/2"), hyp("a", "1/2")], [hyp("a", "0"), hyp("b", "1")],
                   [hyp("a", "x"), hyp("b", "1")], [hyp("a", "1/2", flag="hunch"), hyp("b", "1/2")],
                   [{"id": "a", "weight": 3}, hyp("b", "1")], [hyp("", "1/2"), hyp("b", "1/2")]):
            self.assertEqual(run([], hs)["verdict"], "VOID")
        self.assertEqual(rank("x")["verdict"], "VOID")
        self.assertEqual(run([], caps={"direct": 2})["verdict"], "VOID")
        self.assertEqual(run([], caps={"shadow": "1/2"})["verdict"], "VOID")


class TestEvidence(unittest.TestCase):
    def test_direct_is_exact_and_uncapped(self):
        r = run([ev("e", "direct", "a", "7/3")])
        self.assertEqual(post(r), {"a": F(7, 10), "b": F(3, 10)})
        r = run([ev("e", "direct", "a", "1/4")])                # evidence against
        self.assertEqual(post(r)["a"], F(1, 5))
        self.assertEqual(r["hypotheses"][0]["lowered_by"], [{"evidence": "e", "type": "direct"}])

    def test_shadow(self):
        r = run([ev("s", "shadow", "a", "10")])
        self.assertEqual(post(r)["a"], F(3, 4))                 # capped at 3
        r = run([ev("s", "shadow", "a", "1/10")])
        self.assertEqual(post(r)["a"], F(1, 4))                 # capped the other way too
        r = run([ev("s", "shadow", "a", "10")], caps={"shadow": "5"})
        self.assertEqual(post(r)["a"], F(5, 6))
        self.assertEqual(r["caps"]["source"], {"shadow": "case", "cross_domain": "default"})
        r = run([ev("s", "shadow", "a", "2", alternative_casters=[])])
        self.assertEqual(r["evidence"][0]["outcome"], "VOID")
        self.assertIn("alternative casters", r["evidence"][0]["reason"])
        self.assertEqual(post(r)["a"], F(1, 2))                 # and nothing moved

    def test_shadow_updates_the_class_not_one(self):
        three = [hyp("a", "1/3"), hyp("b", "1/3"), hyp("c", "1/3")]
        r = run([ev("s", "shadow", ["a", "b"], "3")], three)
        self.assertEqual(post(r), {"a": F(3, 7), "b": F(3, 7), "c": F(1, 7)})
        self.assertEqual(post(r)["a"], post(r)["b"])            # it does not pick between them
        r = run([ev("s", "shadow", ["a", "b", "c"], "3")], three)
        self.assertEqual(r["evidence"][0]["outcome"], "NO_UPDATE")
        self.assertIn("every rival", r["evidence"][0]["reason"])
        e = ev("s", "shadow", "a", "3")
        del e["consistent_with"]
        self.assertEqual(run([e])["evidence"][0]["outcome"], "VOID")

    def test_cross_domain(self):
        ok = [{"name": "c1", "matched": True}, {"name": "c2", "matched": True}]
        r = run([ev("x", "cross_domain", "a", "9", constraints=ok)])
        self.assertEqual(post(r)["a"], F(2, 3))                 # capped at 2
        bad = [{"name": "c1", "matched": True}, {"name": "c2", "matched": False}]
        r = run([ev("x", "cross_domain", "a", "9", constraints=bad)])
        self.assertEqual(r["evidence"][0]["outcome"], "NO_UPDATE")
        self.assertIn("constraint not matched: c2", r["evidence"][0]["reason"])
        self.assertEqual(post(r)["a"], F(1, 2))
        for cons in (None, [], [{"name": "c1"}], [{"matched": True}], "all"):
            r = run([ev("x", "cross_domain", "a", "2", constraints=cons)])
            self.assertEqual(r["evidence"][0]["outcome"], "VOID", cons)

    def test_shared_ancestry_counts_once(self):
        r = run([ev("e1", "direct", "a", "5", ["t"]), ev("e2", "direct", "a", "2", ["t"]),
                 ev("e3", "direct", "a", "5", ["t", "u"])])
        self.assertEqual(post(r)["a"], F(5, 6))                 # 5 once, not 5 x 2 x 5
        self.assertEqual([e["outcome"] for e in r["evidence"]], ["APPLY", "NO_UPDATE",
                                                                 "NO_UPDATE"])
        # a stronger one arriving later takes the earlier one's place
        r = run([ev("e1", "direct", "a", "2", ["t"]), ev("e2", "direct", "a", "5", ["t"])])
        self.assertEqual(post(r)["a"], F(5, 6))
        self.assertEqual([s["op"] for s in r["log"][2:]], ["APPLY", "REVERSE", "APPLY"])
        self.assertFalse(r["evidence"][0]["counts_now"])
        self.assertIn("reversed", r["evidence"][0]["reason"])
        # no shared tag, or another hypothesis: both count
        r = run([ev("e1", "direct", "a", "5", ["t"]), ev("e2", "direct", "a", "2", ["u"])])
        self.assertEqual(post(r)["a"], F(10, 11))
        r = run([ev("e1", "direct", "a", "5", ["t"]), ev("e2", "direct", "b", "5", ["t"])])
        self.assertEqual(post(r)["a"], F(1, 2))
        # strength is two-sided: 1/5 against is as strong as 5 for
        r = run([ev("e1", "direct", "a", "2", ["t"]), ev("e2", "direct", "a", "1/5", ["t"])])
        self.assertEqual(post(r)["a"], F(1, 6))

    def test_void_evidence_is_logged_never_applied(self):
        cases = [ev("e", "rumour", "a", "2"), ev("e", "direct", "zzz", "2"),
                 ev("e", "direct", "a", "0"), ev("e", "direct", "a", "-2"),
                 ev("e", "direct", "a", "two"), ev("e", "direct", "a", "2", status="sure"),
                 dict(ev("e", "direct", "a", "2"), provenance=""),
                 dict(ev("e", "direct", "a", "2"), weight=3),
                 dict(ev("e", "direct", "a", "2"), check="passed"), "not a record"]
        for c in cases:
            r = run([c])
            self.assertEqual(r["verdict"], "RANKED")
            self.assertEqual(r["evidence"][0]["outcome"], "VOID", c)
            self.assertEqual(post(r)["a"], F(1, 2), c)
            self.assertEqual(r["counts"]["VOID"], 1)
        r = run([ev("e", "direct", "a", "2"), ev("e", "direct", "a", "2")])
        self.assertEqual(r["evidence"][1]["outcome"], "VOID")           # id used twice
        r = run([dict(ev("e", "direct", "a", "2"), lr=2.5)])
        self.assertEqual(r["evidence"][0]["outcome"], "VOID")           # a binary float


class TestCeilingAndDirection(unittest.TestCase):
    def test_inference_only_is_at_most_proposed(self):
        r = run([ev("e1", "direct", "a", "1000"), ev("e2", "shadow", "a", "3"),
                 ev("e3", "cross_domain", "a", "2")])
        h = r["hypotheses"][0]
        self.assertGreater(F(h["posterior"]), F(999, 1000))
        self.assertEqual(h["status"], "PROPOSED")                       # however high it goes

    def _reports(self, d):
        """A real 2b report and a real 2a report, written into folder d."""
        val = lambda v, u: {"value": v, "unit": u}                      # noqa: E731
        checks = [{"formula": "F = m*a", "values": {"F": val("7.5", "N"), "m": val("2.5", "kg"),
                                                    "a": val(3, "m/s**2")}},
                  {"formula": "F = m*a", "values": {"F": val("8", "N"), "m": val("2.5", "kg"),
                                                    "a": val(3, "m/s**2")}},
                  {"formula": "y = x", "tolerance": "0.5", "fast": True,
                   "values": {"y": val("1.0", "m"), "x": val("1.1", "m")}}]
        b2 = check_all(checks, "checks.json")
        (Path(d) / "numcheck_report.json").write_text(json.dumps(b2))
        a2 = check_file(ROOT / "tests" / "data" / "prop.mm")
        (Path(d) / "kernel_report.json").write_text(json.dumps(a2))
        return b2, a2

    def _ref(self, branch, file, record, rec):
        return {"branch": branch, "file": file, "record": record, "sha256": record_sha(rec)}

    def test_declared_but_absent_check_is_unverified(self):
        # a check that is only declared: never enough
        for check in ({"branch": "2a", "verdict": "PASS"}, {"branch": "2b", "verdict": "HOLDS"}):
            r = run([ev("e", "direct", "a", "4", check=check)])
            h = r["hypotheses"][0]
            self.assertEqual(h["status"], "PROPOSED", check)
            self.assertTrue(h["status_reason"].startswith("CHECK_UNVERIFIED"))
            self.assertEqual(h["checks"][0]["state"], "CHECK_UNVERIFIED")
        # a check_ref to a file that is not there
        with tempfile.TemporaryDirectory() as d:
            ref = {"branch": "2b", "file": "missing.json", "record": 0, "sha256": "0" * 64}
            r = run([ev("e", "direct", "a", "4", check_ref=ref)], base_dir=d)
            h = r["hypotheses"][0]
            self.assertEqual(h["status"], "PROPOSED")
            self.assertIn("CHECK_UNVERIFIED", h["status_reason"])
            self.assertIn("cannot read missing.json", h["checks"][0]["reason"])
        self.assertEqual(post(r)["a"], F(4, 5))            # the evidence still counts as inference

    def test_real_2b_holds_record_moves_to_derived(self):
        with tempfile.TemporaryDirectory() as d:
            b2, _ = self._reports(d)
            self.assertEqual((b2["records"][0]["verdict"], b2["records"][0]["rigorous"]),
                             ("HOLDS", True))
            ref = self._ref("2b", "numcheck_report.json", 0, b2["records"][0])
            r = run([ev("e", "direct", "a", "4", check_ref=ref)], base_dir=d)
            h = r["hypotheses"]
            self.assertEqual(h[0]["status"], "DERIVED")
            self.assertEqual(h[0]["checks"][0]["state"], "VERIFIED")
            self.assertEqual(h[0]["checks"][0]["verdict_read"], "HOLDS")
            self.assertIn("re-read and confirmed", h[0]["status_reason"])
            self.assertEqual(h[1]["status"], "PROPOSED")           # only the one it bears on
            self.assertEqual(r["status"], "PROPOSED")              # the ranking itself stays so
            # the record FAILS, or is a --fast verdict: not confirmed
            for i, why in ((1, "verdict is FAILS"), (2, "not rigorous")):
                ref = self._ref("2b", "numcheck_report.json", i, b2["records"][i])
                r = run([ev("e", "direct", "a", "4", check_ref=ref)], base_dir=d)
                self.assertEqual(r["hypotheses"][0]["status"], "PROPOSED", i)
                self.assertIn(why, r["hypotheses"][0]["checks"][0]["reason"])
            # verified, but the evidence is hearsay, or lowers the hypothesis: not a lift
            ref = self._ref("2b", "numcheck_report.json", 0, b2["records"][0])
            for e in (ev("e", "direct", "a", "4", check_ref=ref, status="PROPOSED"),
                      ev("e", "direct", "a", "1/4", check_ref=ref)):
                h = run([e], base_dir=d)["hypotheses"][0]
                self.assertEqual((h["status"], h["checks"][0]["state"]),
                                 ("PROPOSED", "CHECK_UNVERIFIED"))
            # a shadow cannot carry one
            e = ev("s", "shadow", "a", "3", check_ref=ref)
            self.assertEqual(run([e], base_dir=d)["hypotheses"][0]["status"], "PROPOSED")

    def test_real_2a_pass_record_moves_to_derived(self):
        with tempfile.TemporaryDirectory() as d:
            _, a2 = self._reports(d)
            rec = next(t for t in a2["theorem_records"] if t["label"] == "id")
            ref = self._ref("2a", "kernel_report.json", "id", rec)
            r = run([ev("e", "direct", "a", "4", check_ref=ref)], base_dir=d)
            self.assertEqual(r["hypotheses"][0]["status"], "DERIVED")
            ref["record"] = "nosuch"
            r = run([ev("e", "direct", "a", "4", check_ref=ref)], base_dir=d)
            self.assertEqual(r["hypotheses"][0]["status"], "PROPOSED")

    def test_hash_mismatch_is_unverified(self):
        with tempfile.TemporaryDirectory() as d:
            b2, _ = self._reports(d)
            good = self._ref("2b", "numcheck_report.json", 0, b2["records"][0])
            # the sha256 of another record
            ref = dict(good, sha256=record_sha(b2["records"][1]))
            r = run([ev("e", "direct", "a", "4", check_ref=ref)], base_dir=d)
            h = r["hypotheses"][0]
            self.assertEqual(h["status"], "PROPOSED")
            self.assertIn("CHECK_UNVERIFIED", h["status_reason"])
            self.assertIn("sha256 mismatch", h["checks"][0]["reason"])
            # the report is edited after the reference was taken
            self.assertEqual(run([ev("e", "direct", "a", "4", check_ref=good)],
                                 base_dir=d)["hypotheses"][0]["status"], "DERIVED")
            b2["records"][0]["verdict"] = "HOLDS "
            b2["records"][0]["note"] = "edited"
            (Path(d) / "numcheck_report.json").write_text(json.dumps(b2))
            r = run([ev("e", "direct", "a", "4", check_ref=good)], base_dir=d)
            self.assertEqual(r["hypotheses"][0]["status"], "PROPOSED")
            self.assertIn("sha256 mismatch", r["hypotheses"][0]["checks"][0]["reason"])
            for bad in (None, "x", {"branch": "9z"}, {"branch": "2b"},
                        dict(good, extra=1), dict(good, record="0"), dict(good, record=99)):
                self.assertEqual(verify_check(bad, d)["state"], "CHECK_UNVERIFIED", bad)

    def test_direction(self):
        def d(*evidence):
            return run(list(evidence))["hypotheses"][0]["direction"]
        self.assertEqual(d(ev("e1", "direct", "a", "2"), ev("e2", "shadow", "a", "2")), "RISING")
        self.assertEqual(d(ev("e1", "direct", "a", "2"), ev("e2", "direct", "a", "3"),
                           ev("e3", "direct", "a", "5")), "STACKED")
        self.assertEqual(d(ev("e1", "direct", "a", "2")), "NO_SIGNAL")
        self.assertEqual(d(), "NO_SIGNAL")
        # two types that come from the same place are not independent
        self.assertEqual(d(ev("e1", "direct", "a", "2", ["t"]),
                           ev("e2", "cross_domain", "a", "3", ["t"])), "NO_SIGNAL")
        # one up and one down: neither direction has two
        self.assertEqual(d(ev("e1", "direct", "a", "2"), ev("e2", "shadow", "a", "1/2")),
                         "NO_SIGNAL")
        r = run([ev("e1", "direct", "a", "2"), ev("e2", "direct", "a", "3")])
        self.assertIn("no signal", r["hypotheses"][0]["direction_reason"])

    def test_falling(self):
        r = run([ev("e1", "direct", "a", "1/2"), ev("e2", "shadow", "a", "1/3")])
        h = r["hypotheses"][0]
        self.assertEqual(h["direction"], "FALLING")
        self.assertIn("lowered by independent evidence of types: direct, shadow",
                      h["direction_reason"])
        self.assertEqual(post(r)["a"], F(1, 7))
        self.assertEqual(r["hypotheses"][1]["direction"], "NO_SIGNAL")   # b was not touched
        self.assertEqual(len(h["lowered_by"]), 2)

        def d(*evidence):
            return run(list(evidence))["hypotheses"][0]["direction"]
        # one type lowering twice: stacked, no signal
        self.assertEqual(d(ev("e1", "direct", "a", "1/2"), ev("e2", "direct", "a", "1/3")),
                         "STACKED")
        # two types lowering, same ancestry: not independent
        self.assertEqual(d(ev("e1", "direct", "a", "1/2", ["t"]),
                           ev("e2", "cross_domain", "a", "1/2", ["t"])), "NO_SIGNAL")
        # raised by two independent types and lowered by two others: no signal either way
        self.assertEqual(d(ev("e1", "direct", "a", "2"), ev("e2", "shadow", "a", "2"),
                           ev("e3", "direct", "a", "1/3"), ev("e4", "cross_domain", "a", "1/2")),
                         "NO_SIGNAL")
        # raised by two independent types, lowered by one: still RISING
        self.assertEqual(d(ev("e1", "direct", "a", "2"), ev("e2", "shadow", "a", "2"),
                           ev("e3", "direct", "a", "1/3")), "RISING")


class TestLog(unittest.TestCase):
    def test_replay_reproduces_the_posteriors(self):
        cases = [SNOW,
                 {"hypotheses": [hyp("a", "1/5"), hyp("b", "3/5"), hyp("c", "1/5")],
                  "evidence": [ev("e1", "direct", "a", "2", ["t"]),
                               ev("e2", "shadow", ["a", "c"], "7"),
                               ev("e3", "direct", "a", "5", ["t"]),      # reverses e1
                               ev("e4", "cross_domain", "b", "1/9"),
                               ev("e5", "direct", "zzz", "2")]}]
        for case in cases:
            r = rank(case)
            self.assertTrue(r["replay_matches"])
            self.assertEqual(replay(json.loads(json.dumps(r["log"]))),
                             {h["id"]: h["posterior"] for h in r["hypotheses"]})
            self.assertEqual(r["log"][0]["op"], "CAPS")                  # caps logged per run
            self.assertEqual(sum(post(r).values()), 1)
            for step in r["log"][1:]:
                self.assertIn("posterior_after", step)
        r = rank(cases[1])
        self.assertEqual(r["counts"], {"APPLY": 4, "NO_UPDATE": 0, "VOID": 1, "REVERSE": 1})
        # every step can be undone: replaying all but the last update gives the state before it
        log = r["log"]
        last = max(i for i, s in enumerate(log) if s["op"] == "APPLY")
        before = [s for s in log[:last] if "posterior_after" in s][-1]["posterior_after"]
        self.assertEqual(replay(log[:last]), before)


class TestCli(unittest.TestCase):
    def cli(self, *args):
        return subprocess.run([sys.executable, "-m", "infer", *args], cwd=ROOT,
                              capture_output=True, text=True)

    def test_exit_codes(self):
        r = self.cli("rank", "case_snow.json")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("15/16", r.stdout)
        self.assertIn("RISING", r.stdout)
        self.assertEqual(self.cli().returncode, 2)
        self.assertEqual(self.cli("rank", "nope.json").returncode, 2)
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "c.json"
            f.write_text(json.dumps({"hypotheses": [hyp("only", "1")]}))
            r = self.cli("rank", str(f))
            self.assertEqual(r.returncode, 3)
            self.assertIn("VOID", r.stdout)
            f.write_text(json.dumps({"hypotheses": [hyp("a", "1/2"), hyp("b", "1/2")],
                                     "evidence": [ev("e", "rumour", "a", "2")]}))
            self.assertEqual(self.cli("rank", str(f)).returncode, 3)
            log = Path(d) / "log.json"
            self.assertEqual(self.cli("rank", "case_snow.json", "--log", str(log)).returncode, 0)
            self.assertEqual(replay(json.loads(log.read_text())["log"]),
                             {"miasma": "1/16", "water": "15/16"})
            self.assertEqual(self.cli("rank", "case_snow.json", "--log", str(log)).returncode, 2)
        j = json.loads(self.cli("rank", "case_snow.json", "--json").stdout)
        self.assertEqual(j["ranking"][0]["id"], "water")

    def test_ref_and_rank_from_files(self):
        # numcheck writes a report; "infer ref" makes the check_ref; rank re-reads it
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "checks.json").write_text(json.dumps([{"formula": "y = x", "values": {
                "y": {"value": 1, "unit": "m"}, "x": {"value": 1, "unit": "m"}}}]))
            out = subprocess.run([sys.executable, "-m", "numcheck", "check",
                                  str(d / "checks.json"), "--json"], cwd=ROOT,
                                 capture_output=True, text=True).stdout
            (d / "report.json").write_text(out)
            r = self.cli("ref", "2b", str(d / "report.json"), "0")
            self.assertEqual(r.returncode, 0, r.stderr)
            ref = json.loads(r.stdout)
            ref["file"] = "report.json"                    # looked for beside the case file
            case = {"hypotheses": [hyp("a", "1/2"), hyp("b", "1/2")],
                    "evidence": [ev("e", "direct", "a", "4", check_ref=ref)]}
            (d / "case.json").write_text(json.dumps(case))
            j = json.loads(self.cli("rank", str(d / "case.json"), "--json").stdout)
            self.assertEqual(j["hypotheses"][0]["status"], "DERIVED")
            self.assertEqual(self.cli("ref", "2b", str(d / "report.json"), "7").returncode, 2)
            self.assertEqual(self.cli("ref", "2c", str(d / "report.json"), "0").returncode, 2)


if __name__ == "__main__":
    unittest.main()
