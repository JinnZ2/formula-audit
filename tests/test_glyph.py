"""Tests for glyph (branch 3). Co-authored."""
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
import numcheck  # noqa: E402
import unitaudit  # noqa: E402
import wordslots  # noqa: E402
from glyph import TABLE_V0, read_environment, replay, run  # noqa: E402
from infer import record_sha  # noqa: E402
from infer.ladder import Void  # noqa: E402
from kernel.bridge import prove  # noqa: E402


def val(v, u):
    return {"value": v, "unit": u}


class World:
    """Real reports from branches 1, 2b and 4 in a temporary folder, and the
    references to their records."""

    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        b1 = unitaudit.check_all([
            {"formula": "E = m*c**2", "symbols": {"E": "J", "m": "kg", "c": "m/s"}},
            {"formula": "K = m*v**2/2", "symbols": {"K": "J", "m": "kg", "v": "m/s"}},
            {"formula": "v = sqrt(2*K/m)", "symbols": {"v": "m/s", "K": "J", "m": "kg"}},
            {"formula": "F = m*a", "symbols": {"F": "N", "m": "kg", "a": "m/s**2"}}])
        b2 = numcheck.check_all([
            {"formula": "x = v*t", "tolerance": "0.5",
             "values": {"x": val(["9.8", "10.4"], "m"), "v": val(2, "m/s"),
                        "t": val(["4.9", "5.1"], "s")}},
            {"formula": "F = m*a", "values": {"F": val("7.5", "N"), "m": val("2.5", "kg"),
                                              "a": val(3, "m/s**2")}}])
        table = json.loads((ROOT / "wordslots" / "places.json").read_text())
        b4 = wordslots.check_all([{"word": "safe", "slots": {"x1": "the bridge"}}], table)
        self.reports = {"1": b1, "2b": b2, "4": b4}
        for name, rep in (("b1.json", b1), ("b2.json", b2), ("b4.json", b4)):
            (self.dir / name).write_text(json.dumps(rep))

    def ref(self, branch, record, at, rate=None):
        rec = self.reports[branch]["records"][record]
        out = {"branch": branch, "file": {"1": "b1.json", "2b": "b2.json", "4": "b4.json"}[
            branch], "record": record, "sha256": record_sha(rec), "at": at}
        if rate is not None:
            out["rate"] = rate
        return out

    def case(self, mode="EXPLORE", refs=None, **kw):
        c = {"purpose": {"mode": mode, "target": "find where x = v*t stops holding"},
             "environment": refs or [self.ref("1", 0, 1), self.ref("1", 3, 2),
                                     self.ref("2b", 0, 3), self.ref("4", 0, 4)],
             "energy_budget": {"available": "10", "reserve": "4"},
             "time_budget": {"available": "8", "reserve": "2"},
             "needed_function_met": "y", "now": "6", "default_drift_rate": "1/8",
             "units": {"energy": "J", "cost": "J", "time": "s", "drift_rate": "W"}}
        c.update(kw)
        return c

    def run(self, case, steps=1, **kw):
        return run(case, self.dir, steps, **kw)

    def proposals(self):
        p = self.dir / "proposals.json"
        return json.loads(p.read_text()) if p.exists() else None

    def close(self):
        self.tmp.cleanup()


class Base(unittest.TestCase):
    def setUp(self):
        self.w = World()
        self.addCleanup(self.w.close)


class TestInput(Base):
    def test_no_purpose_is_void(self):
        for purpose in (None, {}, {"target": "x"}, {"mode": "WANDER"}, "EXPLORE"):
            c = self.w.case()
            c["purpose"] = purpose
            r = self.w.run(c)
            self.assertEqual((r["verdict"], r["status"]), ("VOID", None), purpose)
            self.assertEqual(r["steps_done"], 0)
        c = self.w.case()
        del c["purpose"]
        r = self.w.run(c)
        self.assertIn("never defaulted", r["void_reason"])
        self.assertIsNone(self.w.proposals())                 # and nothing was written
        c = self.w.case("SOLVE")
        del c["purpose"]["target"]
        self.assertIn("needs a target", self.w.run(c)["void_reason"])

    def test_void_inputs_are_named(self):
        for key, why in (("energy_budget", "energy_budget is VOID"),
                         ("time_budget", "time_budget is VOID"), ("now", "now is VOID")):
            c = self.w.case()
            del c[key]
            r = self.w.run(c)
            self.assertEqual(r["verdict"], "VOID")
            self.assertIn(why, r["void_reason"])
        r = self.w.run(self.w.case(colour="red"))
        self.assertIn("undeclared field 'colour'", r["void_reason"])
        self.assertEqual(run("x")["verdict"], "VOID")


class TestGate(Base):
    def test_explore_blocked_by_unmet_function(self):
        r = self.w.run(self.w.case(needed_function_met="n"))
        e = r["log"][1]
        self.assertEqual((e["verdict"], e["mode"]), ("STEPPED", "SOLVE"))
        self.assertIn("EXPLORE refused: needed_function_met = n", e["gate"]["gate"])
        self.assertEqual(e["gate"]["asked"], "EXPLORE")
        r = self.w.run(self.w.case())
        self.assertEqual(r["log"][1]["mode"], "EXPLORE")

    def test_no_surplus_turns_to_solve(self):
        r = self.w.run(self.w.case(energy_budget={"available": "4", "reserve": "4"}))
        self.assertEqual(r["log"][1]["mode"], "SOLVE")
        self.assertIn("energy_surplus = n", r["log"][1]["gate"]["gate"])
        r = self.w.run(self.w.case(time_budget={"available": "1", "reserve": "2"}))
        self.assertIn("time_surplus = n", r["log"][1]["gate"]["gate"])

    def test_void_in_the_gate_is_void_naming_which(self):
        for met in ("VOID", None):
            c = self.w.case()
            if met is None:
                del c["needed_function_met"]
            else:
                c["needed_function_met"] = met
            r = self.w.run(c)
            self.assertEqual(r["verdict"], "VOID")
            self.assertIn("needed_function_met is VOID", r["void_reason"])
        r = self.w.run(self.w.case(needed_function_met="maybe"))
        self.assertEqual(r["verdict"], "VOID")
        c = self.w.case(needed_function_met="n")           # turned to SOLVE with no target
        del c["purpose"]["target"]
        self.assertIn("names no target", self.w.run(c)["void_reason"])

    def test_the_gate_is_asked_again_every_step(self):
        # energy 7, reserve 4: one boundary_probe (cost 3) uses the surplus up
        r = self.w.run(self.w.case(energy_budget={"available": "7", "reserve": "4"}), steps=2)
        self.assertEqual([e["mode"] for e in r["log"][1:]], ["EXPLORE", "SOLVE"])


class TestEnvironment(Base):
    def test_features(self):
        refs = [self.w.ref("1", 0, 1), self.w.ref("1", 1, 1), self.w.ref("1", 2, 1),
                self.w.ref("1", 3, 1), self.w.ref("2b", 0, 2), self.w.ref("2b", 1, 2),
                self.w.ref("4", 0, 3)]
        env = read_environment(refs, self.w.dir)
        f = env["features"]
        self.assertEqual(len(f["shared_dims"]), 1)             # E = m c^2 and K = m v^2 / 2
        self.assertEqual(f["shared_dims"][0]["dimension"], "L^2 M T^-2")
        self.assertEqual(len(f["mixed_region"]), 1)
        self.assertEqual(len(f["void_slots"]), 1)
        pq = {(c["p"], c["q"]) for c in f["conjugate_exponents"]}
        self.assertEqual(pq, {(F(2), F(1, 2))})                # a square and a sqrt
        self.assertEqual(sorted(c["base"] for c in f["conjugate_exponents"]), ["c", "v"])
        self.assertEqual(env["newest"], 3)

    def test_references_are_re_read(self):
        good = self.w.ref("2b", 0, 3)
        for bad, why in ((dict(good, sha256="0" * 64), "sha256 mismatch"),
                         (dict(good, file="none.json"), "cannot read"),
                         (dict(good, record=9), "no record"),
                         (dict(good, branch="7"), "branch"),
                         (dict(good, at=None), "no time"),
                         (dict(good, extra=1), "undeclared")):
            with self.assertRaises(Void) as c:
                read_environment([bad], self.w.dir)
            self.assertIn(why, str(c.exception))
            r = self.w.run(self.w.case(refs=[bad]))
            self.assertEqual(r["verdict"], "VOID")
            self.assertIn("environment reference 0", r["void_reason"])
        case = self.w.case()                                 # references taken now
        rep = copy.deepcopy(self.w.reports["2b"])            # the report changes afterwards
        rep["records"][0]["verdict"] = "HOLDS"
        (self.w.dir / "b2.json").write_text(json.dumps(rep))
        r = self.w.run(case)
        self.assertEqual(r["verdict"], "VOID")
        self.assertIn("sha256 mismatch", r["void_reason"])
        self.assertEqual(self.w.run(self.w.case(refs=[]))["verdict"], "VOID")


class TestOptions(Base):
    def test_drift_void_means_no_ranking(self):
        c = self.w.case("SOLVE")
        del c["default_drift_rate"]                           # and no reference carries a rate
        r = self.w.run(c)
        self.assertEqual((r["verdict"], r["steps_done"]), ("VOID", 0))
        self.assertIn("environment reference 0", r["void_reason"])      # the one it names
        self.assertIn("has no drift rate", r["void_reason"])
        self.assertIn("nothing is ranked", r["void_reason"])
        self.assertIsNone(r["log"][1]["rivals"])               # nothing was ranked
        self.assertIsNone(r["log"][1]["chosen"])
        self.assertIsNone(self.w.proposals())
        # every reference but one has a rate: still VOID, naming that one
        refs = [self.w.ref("1", 0, 1, "1/4"), self.w.ref("2b", 0, 3), self.w.ref("4", 0, 4, "1")]
        c = self.w.case("SOLVE", refs=refs)
        del c["default_drift_rate"]
        self.assertIn("environment reference 1 (b2.json", self.w.run(c)["void_reason"])

    def test_two_references_at_different_rates_sum(self):
        # ages 5 and 2 at now = 6: 1/4 x 5 + 3 x 2 = 29/4
        refs = [self.w.ref("2b", 0, 1, "1/4"), self.w.ref("4", 0, 4, "3")]
        c = self.w.case("SOLVE", refs=refs)
        del c["default_drift_rate"]
        e = self.w.run(c)["log"][1]
        ina = e["options"][-1]
        self.assertEqual((ina["name"], ina["cost"], ina["cost_status"]),
                         ("inaction", "29/4", "DERIVED"))
        self.assertEqual(ina["cost_parts"], [
            {"reference": 0, "rate": "1/4", "age": "5", "cost": "5/4",
             "rate_from": "the reference"},
            {"reference": 1, "rate": "3", "age": "2", "cost": "6",
             "rate_from": "the reference"}])
        self.assertEqual(ina["default_rate_used_for"], [])
        # a default fills the gaps, and its use is flagged
        refs = [self.w.ref("2b", 0, 1, "1/4"), self.w.ref("4", 0, 4)]
        e = self.w.run(self.w.case("SOLVE", refs=refs, default_drift_rate="2"))["log"][1]
        self.assertEqual(e["options"][-1]["cost"], "21/4")              # 5/4 + 2 x 2
        self.assertEqual(e["options"][-1]["default_rate_used_for"], [1])
        self.assertEqual(e["options"][-1]["cost_parts"][1]["rate_from"], "default")

    def test_just_updated_costs_zero_and_ranks(self):
        # every reference is dated now: nothing has drifted yet. Cost 0, DERIVED, and
        # inaction ranks first even against a tool with strong evidence
        refs = [self.w.ref("2b", 0, 6, "1/2"), self.w.ref("4", 0, 6, "3")]
        ev = [{"id": "e", "type": "direct", "hypothesis": "boundary_probe", "lr": "1000",
               "provenance": "p", "shared_ancestry": [], "status": "OBSERVED"}]
        r = self.w.run(self.w.case("SOLVE", refs=refs, evidence=ev))
        e = r["log"][1]
        self.assertEqual(r["verdict"], "STEPPED")
        ina = e["options"][-1]
        self.assertEqual((ina["cost"], ina["cost_status"]), ("0", "DERIVED"))
        self.assertEqual(e["chosen"], "inaction")
        self.assertIn("costs nothing", e["choice_reason"])
        self.assertEqual(e["rivals"][0]["name"], "inaction")
        self.assertEqual(e["rivals"][0]["score"], "unbounded (cost 0)")
        self.assertEqual(len(e["rivals"]), 3)                   # the others are still recorded
        # one step later the world has aged: the cost is no longer 0 and the tool wins
        r = self.w.run(self.w.case("SOLVE", refs=refs, evidence=ev), steps=2)
        self.assertEqual([x["chosen"] for x in r["log"][1:]], ["inaction", "boundary_probe"])
        self.assertEqual(r["log"][2]["options"][-1]["cost"], "7/2")

    def test_rate_zero_is_void(self):
        for refs, default in (([self.w.ref("2b", 0, 3, "0")], "1/8"),
                              ([self.w.ref("2b", 0, 3)], "0"),
                              ([self.w.ref("2b", 0, 3, "1"), self.w.ref("4", 0, 4, 0)], None)):
            c = self.w.case("SOLVE", refs=refs)
            if default is None:
                del c["default_drift_rate"]
            else:
                c["default_drift_rate"] = default
            r = self.w.run(c)
            self.assertEqual(r["verdict"], "VOID")
            self.assertIn("static world claimed, unevidenced", r["void_reason"])
            self.assertIsNone(r["log"][1]["chosen"])
        r = self.w.run(self.w.case(refs=[self.w.ref("2b", 0, 3, "-1")]))
        self.assertIn("below 0", r["void_reason"])
        r = self.w.run(self.w.case(refs=[self.w.ref("2b", 0, 9, "1")]))   # dated after now
        self.assertIn("dated after now", r["void_reason"])

    def test_inaction_is_always_an_option_and_its_cost_grows(self):
        r = self.w.run(self.w.case(), steps=4)
        costs = [next(o for o in e["options"] if o["name"] == "inaction")["cost"]
                 for e in r["log"][1:]]
        # 1/8 x (ages 5 + 4 + 3 + 2) = 7/4 at now 6; each step ages four references by 1
        self.assertEqual(costs, ["7/4", "9/4", "11/4", "13/4"])
        for e in r["log"][1:]:
            self.assertEqual(e["options"][-1]["name"], "inaction")
            self.assertTrue(e["options"][-1]["open"])
            self.assertEqual(e["options"][-1]["default_rate_used_for"], [0, 1, 2, 3])


class TestUnits(Base):
    def test_unit_mismatch_is_void(self):
        good = {"energy": "J", "cost": "J", "time": "s", "drift_rate": "W"}
        for units, why in ((dict(good, drift_rate="J"), "cost = rate*dt"),     # J x s is not J
                           (dict(good, cost="N"), "energy = cost"),
                           (dict(good, time="m"), "cost = rate*dt"),
                           (dict(good, drift_rate="furlong/s"), "units VOID")):
            r = self.w.run(self.w.case("SOLVE", units=units))
            self.assertEqual((r["verdict"], r["steps_done"]), ("VOID", 0), units)
            self.assertIn(why, r["void_reason"])
            self.assertIsNone(r["log"][1]["chosen"])
        r = self.w.run(self.w.case("SOLVE", units=dict(good, drift_rate="J")))
        self.assertIn("units FAIL", r["void_reason"])
        self.assertIn("L^2 M T^-2 vs L^2 M T^-1", r["void_reason"])
        self.assertIsNone(self.w.proposals())

    def test_units_must_be_declared(self):
        c = self.w.case()
        del c["units"]
        self.assertIn("units are VOID", self.w.run(c)["void_reason"])
        c = self.w.case(units={"energy": "J", "cost": "J", "time": "s"})
        self.assertIn("units are VOID for: drift_rate", self.w.run(c)["void_reason"])
        c = self.w.case(units={"energy": "J", "cost": "J", "time": "s", "drift_rate": "W",
                               "mass": "kg"})
        self.assertEqual(self.w.run(c)["verdict"], "VOID")

    def test_unit_checks_are_on_the_step(self):
        e = self.w.run(self.w.case())["log"][1]
        self.assertEqual([(u["formula"], u["verdict"]) for u in e["units"]],
                         [("energy = cost", "PASS"), ("cost = rate*dt", "PASS")])
        self.assertEqual(e["units"][1]["units"], {"cost": "J", "rate": "W", "dt": "s"})
        # equivalent spellings pass: J/s for W
        r = self.w.run(self.w.case(units={"energy": "kg*m**2/s**2", "cost": "J", "time": "s",
                                          "drift_rate": "J/s"}))
        self.assertEqual(r["verdict"], "STEPPED")
        # a reference may carry its own rate unit; it is checked too
        refs = [dict(self.w.ref("2b", 0, 3, "1"), rate_unit="W"),
                dict(self.w.ref("4", 0, 4, "1"), rate_unit="N")]
        r = self.w.run(self.w.case(refs=refs))
        self.assertEqual(r["verdict"], "VOID")
        self.assertIn("environment reference 1", r["void_reason"])


class TestOptionsMore(Base):
    def test_closed_options_say_why(self):
        e = self.w.run(self.w.case(energy_budget={"available": "6", "reserve": "1"},
                                   tools=[dict(TABLE_V0[1], cost="50")] + TABLE_V0[:1]))["log"][1]
        why = {o["name"]: o["why_not"] for o in e["options"]}
        self.assertIn("costs 50, energy available 6", why["boundary_probe"])
        self.assertIn("feature not in the environment: shared_dims", why["dimensional_analogy"])
        for bad in ([{"name": "t"}], [dict(TABLE_V0[0], status="DERIVED")],
                    [dict(TABLE_V0[0], needs=["magic"])], [dict(TABLE_V0[0], cost="0")]):
            self.assertEqual(self.w.run(self.w.case(tools=bad))["verdict"], "VOID")


class TestSolve(Base):
    def ev(self, name, lr):
        return {"id": f"e_{name}", "type": "direct", "hypothesis": name, "lr": lr,
                "provenance": "earlier runs", "shared_ancestry": [], "status": "OBSERVED"}

    def test_inaction_outranks_a_costly_weak_tool(self):
        c = self.w.case("SOLVE", tools=[dict(TABLE_V0[1], cost="50")],
                        energy_budget={"available": "100", "reserve": "4"})
        r = self.w.run(c)
        e = r["log"][1]
        self.assertEqual(e["chosen"], "inaction")
        rivals = {x["name"]: x for x in e["rivals"]}           # both rivals are on the record
        self.assertEqual(sorted(rivals), ["boundary_probe", "inaction"])
        self.assertEqual((rivals["inaction"]["posterior"], rivals["inaction"]["cost"],
                          rivals["inaction"]["score"]), ("1/2", "7/4", "2/7"))
        self.assertEqual((rivals["boundary_probe"]["cost"], rivals["boundary_probe"]["score"]),
                         ("50", "1/100"))
        self.assertIsNone(e["candidate"])
        self.assertIsNone(self.w.proposals())
        self.assertEqual(e["delta"], {"energy": "0", "time": "1"})

    def test_one_solve_step_writes_a_proposal(self):
        c = self.w.case("SOLVE", evidence=[self.ev("boundary_probe", "5")])
        r = self.w.run(c)
        e = r["log"][1]
        self.assertEqual((r["verdict"], r["status"], e["mode"], e["chosen"]),
                         ("STEPPED", "PROPOSED", "SOLVE", "boundary_probe"))
        rivals = {x["name"]: x for x in e["rivals"]}
        self.assertEqual(sorted(rivals), ["boundary_probe", "inaction", "slot_fill_audit"])
        self.assertEqual(rivals["boundary_probe"]["posterior"], "5/7")
        self.assertEqual(rivals["boundary_probe"]["score"], "5/21")
        self.assertEqual(e["infer"]["evidence_used"], 1)
        self.assertEqual(rivals["inaction"]["score"], "4/49")           # (1/7) / (7/4)
        saved = self.w.dir / e["infer_log"]["file"]                     # the ranking's own log
        self.assertTrue(saved.exists())
        self.assertEqual(len(e["infer_log"]["sha256"]), 64)
        data = self.w.proposals()
        self.assertEqual(len(data["proposals"]), 1)
        p = data["proposals"][0]
        self.assertEqual((p["lhs"], p["rhs"]), ("(x) - (v*t)", "1/2"))
        self.assertEqual(sorted(p["domain"]), ["t", "x"])
        self.assertEqual(p["fixed"], {"v": "2"})
        self.assertEqual((p["status"], p["tag"], p["proof"], p["proof_attempted"]),
                         ("PROPOSED", "SOLVE", None, False))
        self.assertEqual(p["glyph"]["tool"], "boundary_probe")
        self.assertEqual(p["glyph"]["sources"][0]["sha256"], c["environment"][2]["sha256"])
        self.assertEqual(p["glyph"]["target"], c["purpose"]["target"])
        self.assertIsNone(p["human_interest"])
        self.assertIsNone(p["ai_interest"])
        self.assertEqual(e["state_after"]["energy_available"], "7")
        self.assertEqual(e["environment_after"]["candidates_made"], 1)   # read again
        # the candidate is read by the 2b -> 2a seam like any other entry. Its bounds
        # (49/10 ...) have no numeral in algebra.mm, so the seam says VOID and leaves
        # the entry as it is: still PROPOSED.
        before = copy.deepcopy(p)
        rep = prove(self.w.dir / "proposals.json")
        self.assertEqual(rep["counts"], {"PASS": 0, "FAIL": 0, "VOID": 1, "NO_PROOF": 0})
        self.assertIn("no numeral", rep["records"][0]["reason"])
        self.assertEqual(self.w.proposals()["proposals"][0], before)

    def test_next_step_is_chosen_from_the_new_state(self):
        c = self.w.case("SOLVE", evidence=[self.ev("boundary_probe", "5")])
        r = self.w.run(c, steps=3)
        chosen = [e["chosen"] for e in r["log"][1:]]
        self.assertEqual(chosen[0], "boundary_probe")
        self.assertNotEqual(chosen[1], "boundary_probe")       # that instance has its candidate
        closed = next(o for o in r["log"][2]["options"] if o["name"] == "boundary_probe")
        self.assertEqual(closed["why_not"], "every instance already has a candidate")
        self.assertEqual(len(self.w.proposals()["proposals"]), 1)

    def test_only_inaction_open(self):
        c = self.w.case("SOLVE", refs=[self.w.ref("1", 3, 2)])
        e = self.w.run(c)["log"][1]
        self.assertEqual((e["chosen"], e["choice_reason"]), ("inaction", "the only open option"))


class TestExplore(Base):
    def test_explore_picks_unpaired_features_and_tags_them(self):
        r = self.w.run(self.w.case(), steps=3)
        self.assertEqual([e["chosen"] for e in r["log"][1:]],
                         ["boundary_probe", "slot_fill_audit", "inaction"])
        data = self.w.proposals()
        self.assertEqual((data["proposals"][0]["tag"], data["proposals"][0]["status"]),
                         ("EXPLORE", "PROPOSED"))
        q = data["questions"][0]
        self.assertEqual((q["word"], q["tag"], q["status"]), ("safe", "EXPLORE", "PROPOSED"))
        self.assertEqual([s["name"] for s in q["void_slots"]], ["x2", "x3"])
        self.assertIn("no tool has an unpaired feature", r["log"][3]["choice_reason"])

    def test_all_four_tools(self):
        refs = [self.w.ref("1", 0, 1), self.w.ref("1", 1, 1), self.w.ref("1", 2, 1),
                self.w.ref("2b", 0, 2), self.w.ref("4", 0, 3)]
        c = self.w.case(refs=refs, energy_budget={"available": "30", "reserve": "1"},
                        time_budget={"available": "30", "reserve": "1"})
        r = self.w.run(c, steps=5)
        # two conjugate pairs: c**2 with the sqrt, and v**2 with the sqrt
        self.assertEqual([e["chosen"] for e in r["log"][1:]],
                         ["dimensional_analogy", "boundary_probe", "conjugate_map",
                          "conjugate_map", "slot_fill_audit"])
        keys = [e["candidate"]["key"] for e in r["log"][1:]]
        self.assertEqual(len(set(keys)), 5)                     # one candidate per instance
        props = {}
        for p in self.w.proposals()["proposals"]:
            props.setdefault(p["glyph"]["tool"], p)
        self.assertEqual((props["dimensional_analogy"]["lhs"], props["dimensional_analogy"]["rhs"]),
                         ("m*c**2", "m*v**2/2"))
        self.assertEqual(props["conjugate_map"]["rhs"], "c")
        self.assertEqual(props["conjugate_map"]["lhs"], "((c)**(2))**(1/2)")

    def test_ceiling(self):
        r = self.w.run(self.w.case(), steps=3)
        data = self.w.proposals()
        for e in data["proposals"] + data["questions"]:
            self.assertEqual(e["status"], "PROPOSED")
            self.assertEqual(e["glyph"]["tool_status"], "PROPOSED")
        for e in r["log"][1:]:
            self.assertEqual(e["status"], "PROPOSED")
        self.assertEqual(r["status"], "PROPOSED")
        for t in TABLE_V0:
            self.assertEqual(t["status"], "PROPOSED")
        self.assertEqual([t["name"] for t in TABLE_V0],
                         ["dimensional_analogy", "boundary_probe", "conjugate_map",
                          "slot_fill_audit"])


class TestLog(Base):
    def test_replay_reproduces(self):
        r = self.w.run(self.w.case(), steps=4)
        self.assertTrue(r["replay_matches"])
        again = replay(json.loads(json.dumps(r["log"])), self.w.dir)
        self.assertEqual(again["verdict"], "REPRODUCED")
        self.assertEqual(again["state"], r["final_state"])
        made = [x["glyph"]["key"] for part in ("proposals", "questions")
                for x in self.w.proposals()[part]]
        self.assertEqual(sorted(again["candidates"]), sorted(made))
        self.assertEqual(again["state"], {"energy_available": "6", "energy_reserve": "4",
                                          "time_available": "4", "time_reserve": "2",
                                          "now": "10"})
        # a log that stops early gives the state at that point
        self.assertEqual(replay(r["log"][:2], self.w.dir)["state"], r["log"][1]["state_after"])

    def solve(self, steps=2):
        ev = [{"id": "e", "type": "direct", "hypothesis": "boundary_probe", "lr": "5",
               "provenance": "p", "shared_ancestry": [], "status": "OBSERVED"}]
        return self.w.run(self.w.case("SOLVE", evidence=ev), steps=steps)

    def test_replay_runs_branch_5_again_from_the_saved_log(self):
        r = self.solve()
        again = replay(r["log"], self.w.dir)
        self.assertEqual((again["verdict"], again["infer_logs_rerun"], again["failures"]),
                         ("REPRODUCED", 2, []))
        saved = json.loads((self.w.dir / r["log"][1]["infer_log"]["file"]).read_text())
        self.assertEqual(sorted(saved), ["input", "log", "posteriors"])
        self.assertEqual(saved["posteriors"]["boundary_probe"], "5/7")
        self.assertEqual(saved["input"]["evidence"][0]["lr"], "5")

    def test_replay_with_a_tampered_infer_log_fails(self):
        r = self.solve()
        path = self.w.dir / r["log"][1]["infer_log"]["file"]
        original = path.read_text()
        # the evidence in the saved log is changed: the file no longer matches its sha256
        path.write_text(original.replace('"lr": "5"', '"lr": "1/5"'))
        again = replay(r["log"], self.w.dir)
        self.assertEqual(again["verdict"], "FAILS")
        self.assertEqual(again["failures"][0]["step"], 1)
        self.assertIn("sha256 differs", again["failures"][0]["reason"])
        # the file is changed AND the step log's sha256 is changed to match: branch 5 run
        # again gives another ranking than the step log holds
        import hashlib
        log = json.loads(json.dumps(r["log"]))
        log[1]["infer_log"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        again = replay(log, self.w.dir)
        self.assertEqual(again["verdict"], "FAILS")
        self.assertIn("different ranking", again["failures"][0]["reason"])
        # the step log itself is changed: a rival's posterior is edited
        path.write_text(original)
        log = json.loads(json.dumps(r["log"]))
        log[1]["rivals"][0]["posterior"] = "6/7"
        self.assertEqual(replay(log, self.w.dir)["verdict"], "FAILS")
        # the file is gone
        path.unlink()
        again = replay(r["log"], self.w.dir)
        self.assertEqual(again["verdict"], "FAILS")
        self.assertIn("cannot read", again["failures"][0]["reason"])

    def test_dry_run_writes_nothing(self):
        r = self.w.run(self.w.case(), write=False)
        self.assertEqual(r["verdict"], "STEPPED")
        self.assertIsNone(self.w.proposals())
        self.assertFalse((self.w.dir / "glyph_log").exists())

    def test_existing_proposals_are_kept(self):
        old = {"proposals": [{"lhs": "x*x", "rhs": "x**2", "domain": {}, "status": "PROPOSED"}]}
        (self.w.dir / "proposals.json").write_text(json.dumps(old))
        self.w.run(self.w.case())
        got = self.w.proposals()["proposals"]
        self.assertEqual(got[0], old["proposals"][0])
        self.assertEqual(len(got), 2)
        (self.w.dir / "proposals.json").write_text("not json")
        self.assertEqual(self.w.run(self.w.case())["verdict"], "VOID")
        self.assertEqual((self.w.dir / "proposals.json").read_text(), "not json")


class TestCli(Base):
    def cli(self, *args):
        return subprocess.run([sys.executable, "-m", "glyph", *args], cwd=ROOT,
                              capture_output=True, text=True)

    def test_step_and_ref(self):
        r = self.cli("ref", "2b", str(self.w.dir / "b2.json"), "0", "3")
        self.assertEqual(r.returncode, 0, r.stderr)
        ref = json.loads(r.stdout)
        self.assertEqual(ref["sha256"], self.w.ref("2b", 0, 3)["sha256"])
        (self.w.dir / "case.json").write_text(json.dumps(self.w.case()))
        r = self.cli("step", str(self.w.dir / "case.json"), "--steps", "2")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("EXPLORE allowed", r.stdout)
        self.assertIn("status PROPOSED", r.stdout)
        self.assertEqual(len(self.w.proposals()["proposals"]), 1)
        c = self.w.case()
        del c["purpose"]
        (self.w.dir / "case.json").write_text(json.dumps(c))
        r = self.cli("step", str(self.w.dir / "case.json"))
        self.assertEqual(r.returncode, 3)
        self.assertIn("VOID", r.stdout)
        self.assertEqual(self.cli().returncode, 2)
        self.assertEqual(self.cli("step", "nope.json").returncode, 2)
        self.assertEqual(self.cli("step", str(self.w.dir / "case.json"), "--steps",
                                  "0").returncode, 2)
        self.assertEqual(self.cli("ref", "2b", str(self.w.dir / "b2.json"), "77").returncode, 2)


if __name__ == "__main__":
    unittest.main()
