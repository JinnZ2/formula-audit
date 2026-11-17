"""Tests for wordslots (branch 4). Co-authored."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from wordslots import EVIDENTIAL, RECORD_FIELDS, check_all, check_claim, read_table  # noqa: E402

TABLE = json.loads((ROOT / "wordslots" / "places.json").read_text())
WORDS = read_table(TABLE)
FULL = {"x1": "the bridge", "x2": "collapse under a 3 t load", "x3": "pedestrians"}


def claim(word, slots, **kw):
    """A claim with a source_id, unless the test passes source_id=None; a claim
    of "safe" is in the PROTECTED sense, unless the test passes sense=None."""
    kw.setdefault("source_id", "a stated source")
    if word == "safe":
        kw.setdefault("sense", "PROTECTED")
    for k in ("source_id", "sense"):
        if k in kw and kw[k] is None:
            del kw[k]
    return check_claim({"word": word, "slots": slots, **kw}, WORDS)


def warm(value, unit="K", rng="room"):
    return claim("warm", {"x1": "the room", "x2": {"text": "std", "value": value, "unit": unit,
                                                    "is": rng}}, reading="PHYSICAL")


class TestTable(unittest.TestCase):
    def test_shipped_table_is_all_proposed(self):
        for entry in WORDS.values():
            self.assertEqual(entry["status"], "PROPOSED")
            for s in entry["slots"]:
                self.assertEqual(s["status"], "PROPOSED")
        self.assertEqual([s["name"] for s in WORDS["safe"]["slots"]], ["x1", "x2", "x3", "x4"])
        self.assertEqual([s["role"] for s in WORDS["warm"]["slots"]],
                         ["what is warm", "by standard", "to whom",
                          "in what actions or behaviour"])

    def test_every_slot_carries_a_source_predicate(self):
        ref = json.loads((ROOT / "REFERENCES" / "lojban_place_structures.json").read_text())
        known = {p["gismu"] for p in ref["data"]["place_structures"] if p["gismu"]}
        got = {w: [s["source_predicate"] for s in e["slots"]] for w, e in WORDS.items()}
        for w, preds in got.items():
            for g in preds:                               # a word of the reference, or physics_def
                self.assertTrue(g == "physics_def" or g in known, (w, g))
        self.assertEqual(got["warm"], ["glare", "glare", "xendo", "xendo"])
        self.assertEqual(got["safe"], ["snura", "snura", "ckape", "ckape"])
        self.assertEqual(got["hostile"], ["le'onmo"] * 2)
        self.assertEqual(got["better"], ["xagmau"] * 5)
        self.assertEqual(got["appropriate"], ["mapti"] * 3)
        self.assertEqual((got["more"], got["less"]), (["zmadu"] * 4, ["mleca"] * 4))
        self.assertEqual(got["near"], ["jibni"] * 3)
        r = claim("safe", FULL)                           # and it rides along in the record
        self.assertEqual([x["source_predicate"] for x in r["slots"]],
                         ["snura", "snura", "ckape", "ckape"])

    def test_efficient_keeps_lojban_void(self):
        e = WORDS["efficient"]
        self.assertEqual((e["lojban"], e["shape"]), ("VOID", None))
        self.assertEqual({s["source_predicate"] for s in e["slots"]}, {"physics_def"})
        self.assertEqual([s["role"] for s in e["slots"]],
                         ["what is efficient", "useful output", "input supplied", "process",
                          "baseline compared against"])
        whole = {"x1": "this pump", "x2": "water lifted", "x3": "fuel burned",
                 "x4": "lifting from the well", "x5": "the old pump"}
        r = claim("efficient", whole)
        self.assertEqual((r["verdict"], r["lojban"], r["shape"]), ("PASS", "VOID", None))
        r = claim("efficient", {"x1": "this pump"})
        self.assertEqual((r["verdict"], r["missing_required"]),
                         ("DEGRADED", ["x2", "x3", "x4", "x5"]))

    def test_efficient_missing_baseline_is_degraded_naming_it(self):
        whole = {"x1": "this pump", "x2": "water lifted", "x3": "fuel burned",
                 "x4": "lifting from the well", "x5": "the old pump"}
        r = claim("efficient", {k: v for k, v in whole.items() if k != "x5"})
        self.assertEqual((r["verdict"], r["pass_equivalent"], r["missing_required"]),
                         ("DEGRADED", False, ["x5"]))
        m = r["degraded"]["missing"][0]
        self.assertEqual((m["name"], m["role"], m["reason"]),
                         ("x5", "baseline compared against", "required slot empty"))
        self.assertEqual(r["degraded"]["kept"], ["x1", "x2", "x3", "x4"])     # kept, usable
        r = claim("efficient", {k: v for k, v in whole.items() if k != "x4"})
        self.assertEqual((r["missing_required"], r["degraded"]["missing"][0]["role"]),
                         (["x4"], "process"))
        for change in (lambda e: e.update(shape="zmadu"),             # VOID and a shape
                       lambda e: e["slots"][0].update(source_predicate="zmadu"),
                       lambda e: e.update(lojban="unknown")):
            t = copy.deepcopy(TABLE)
            change(t["words"]["efficient"])
            self.assertIsNotNone(check_all([{"word": "efficient"}], t)["table_void"])

    def test_bad_tables_void_every_claim(self):
        def broken(change):
            t = copy.deepcopy(TABLE)
            change(t["words"]["safe"])
            return check_all([{"word": "safe", "slots": FULL}], t)
        for change in (lambda e: e.pop("status"),
                       lambda e: e["slots"][0].pop("required"),
                       lambda e: e["slots"][0].pop("status"),
                       lambda e: e["slots"][0].update(colour="red"),
                       lambda e: e["slots"][0].pop("source_predicate"),
                       lambda e: e["slots"][0].update(source_predicate=""),
                       lambda e: e["slots"][1].update(senses=["SAFE_ENOUGH"]),
                       lambda e: e.pop("sense_field"),
                       lambda e: e.update(sense_field="mood"),
                       lambda e: e["slots"].append(dict(e["slots"][0])),
                       lambda e: e.update(slots=[])):
            rep = broken(change)
            self.assertEqual(rep["counts"]["VOID"], 1)
            self.assertIsNotNone(rep["table_void"])
            self.assertIn("place table VOID", rep["records"][0]["void_reason"])
        self.assertEqual(check_all([{"word": "safe"}], {})["counts"]["VOID"], 1)


class TestClaims(unittest.TestCase):
    def test_safe_with_no_x2_x3_is_degraded_naming_both(self):
        r = claim("safe", {"x1": "the bridge"}, source_path="notes.md:3")
        self.assertEqual((r["verdict"], r["status"]), ("DEGRADED", "DERIVED"))
        self.assertFalse(r["pass_equivalent"])                  # downstream: not a PASS
        self.assertEqual(r["missing_required"], ["x2", "x3"])
        m = r["degraded"]["missing"]
        self.assertEqual([(x["name"], x["role"], x["reason"]) for x in m],
                         [("x2", "from threat", "required slot empty"),
                          ("x3", "for whom", "required slot empty")])
        self.assertEqual(m[0]["provenance"]["source_path"], "notes.md:3")
        self.assertEqual(m[0]["provenance"]["declared_in"], "place table")
        # what is filled is kept and usable
        self.assertEqual(r["degraded"]["kept"], ["x1"])
        self.assertEqual(r["usable"]["slots"], {"x1": "the bridge"})
        self.assertEqual([(s["name"], s["slot_state"]) for s in r["slots"]],
                         [("x1", "FILLED"), ("x2", "VOID"), ("x3", "VOID"), ("x4", "VOID")])
        for empty in ("", "   ", None, {"text": ""}, {"text": None}):
            r = claim("safe", dict(FULL, x3=empty))
            self.assertEqual((r["verdict"], r["missing_required"]), ("DEGRADED", ["x3"]), empty)
        self.assertEqual(claim("safe", None)["missing_required"], ["x1", "x2", "x3"])

    def test_fully_filled_passes(self):
        r = claim("safe", FULL, evidential="observed", source_id="inspection report 12")
        self.assertEqual((r["verdict"], r["status"]), ("PASS", "DERIVED"))
        self.assertEqual(r["missing_required"], [])
        self.assertEqual(r["source_id"], "inspection report 12")
        self.assertEqual(r["table_entry_status"], "PROPOSED")      # the table's tag rides along
        self.assertIsNone(r["human_interest"])
        self.assertIsNone(r["ai_interest"])

    def test_hearsay_is_carried_not_upgraded(self):
        r = claim("safe", FULL, evidential="hearsay", source_id="a neighbour")
        self.assertEqual(r["verdict"], "PASS")
        self.assertEqual(r["status"], "DERIVED")                   # the verdict's status
        self.assertEqual((r["evidential"], r["claim_status"]), ("hearsay", "PROPOSED"))
        self.assertNotEqual(r["claim_status"], r["status"])        # a PASS does not lift it
        self.assertEqual({e: claim("safe", FULL, evidential=e)["claim_status"]
                          for e in EVIDENTIAL if e not in ("se'o", "ka'u", "ba'acu'i")},
                         {"observed": "OBSERVED", "concluded": "DERIVED", "hearsay": "PROPOSED",
                          "opinion": "PROPOSED", "defined": "OBSERVED", "ja'o": "DERIVED",
                          "ba'anai": "OBSERVED", "ba'a": "PROPOSED", "su'a": "PROPOSED"})
        r = claim("safe", FULL)                                    # none given: stays null
        self.assertEqual((r["verdict"], r["claim_status"]), ("PASS", None))
        r = claim("safe", {"x1": "the bridge"}, evidential="hearsay")
        self.assertEqual((r["verdict"], r["claim_status"]), ("DEGRADED", "PROPOSED"))

    def test_undeclared_field_unknown_word_unknown_evidential(self):
        r = check_claim({"word": "safe", "slots": FULL, "certainty": "high"}, WORDS)
        self.assertEqual(r["verdict"], "VOID")
        self.assertIn("undeclared field: 'certainty'", r["void_reason"])
        r = claim("cosy", {"x1": "the room"})
        self.assertIn("unknown word 'cosy'", r["void_reason"])
        r = claim("safe", dict(FULL, x5="extra"))
        self.assertIn("undeclared slot for 'safe': x5", r["void_reason"])
        r = claim("safe", dict(FULL, x2={"text": "fire", "weight": 3}))
        self.assertIn("undeclared field 'weight'", r["void_reason"])
        r = claim("safe", FULL, evidential="certain")
        self.assertIn("unknown evidential 'certain'", r["void_reason"])
        r = claim("safe", dict(FULL, x2={"text": "fire", "status": "sure"}))
        self.assertEqual(r["verdict"], "VOID")
        for bad in (None, "safe", 3, {"slots": FULL}, {"word": "", "slots": FULL},
                    {"word": "safe", "slots": ["a", "b", "c"]},
                    {"word": "safe", "slots": dict(FULL, x2=7)}):
            self.assertEqual(check_claim(bad, WORDS)["verdict"], "VOID", bad)
        self.assertEqual(set(RECORD_FIELDS),
                         {"word", "slots", "reading", "sense", "magnitude", "evidential", "speaker",
                          "oral_record", "source_id", "source_path", "table"})
        for bad in ({"reading": "WARMISH"}, {"evidential": "za'a'a"},
                    {"magnitude": {"value": "1", "weight": 2}}, {"oral_record": {}}):
            r = check_claim({"word": "safe", "slots": FULL, "sense": "PROTECTED",
                             "source_id": "s", **bad}, WORDS)
            self.assertEqual(r["verdict"], "VOID", bad)          # a bad tag stays VOID

    def test_optional_slot_may_stay_void(self):
        r = claim("near", {"x1": "the shop", "x2": "the station"})
        self.assertEqual(r["verdict"], "PASS")
        self.assertEqual(r["slots"][2]["slot_state"], "VOID")        # kept, and not required
        self.assertEqual(r["ranges"], [])


class TestV1(unittest.TestCase):
    def test_the_water_is_warm_is_degraded(self):
        # "the water is warm": what is warm is given, and that a temperature is meant;
        # the standard and the magnitude are not
        r = claim("warm", {"x1": "the water"}, reading="PHYSICAL", evidential="hearsay",
                  source_id="a sign by the pool")
        self.assertEqual((r["verdict"], r["status"], r["pass_equivalent"]),
                         ("DEGRADED", "DERIVED", False))
        self.assertEqual(r["missing_required"], ["x2", "magnitude"])
        m = {x["name"]: x for x in r["degraded"]["missing"]}
        self.assertEqual(m["x2"]["role"], "by standard")
        self.assertIn("needs a magnitude with its unit", m["magnitude"]["reason"])
        self.assertEqual(m["magnitude"]["provenance"]["declared_in"], "claim record")
        self.assertEqual(r["usable"], {"slots": {"x1": "the water"}, "reading": "PHYSICAL",
                                       "magnitude": None})
        self.assertEqual((r["claim_status"], r["word_class"], r["shape"]),
                         ("PROPOSED", "EMOTIVE", "glare"))
        # with the standard and a magnitude it is whole, and the magnitude is checked
        r = claim("warm", {"x1": "the water", "x2": {"text": "room standard", "is": "room"}},
                  reading="PHYSICAL", magnitude={"value": "295", "unit": "K"})
        self.assertEqual((r["verdict"], r["pass_equivalent"]), ("PASS", True))
        self.assertEqual((r["ranges"][0]["state"], r["ranges"][0]["value_from"]),
                         ("IN_RANGE", "the claim's magnitude"))
        r = claim("warm", {"x1": "the water", "x2": {"text": "room standard", "is": "room"}},
                  reading="PHYSICAL", magnitude={"value": "320", "unit": "K"})
        self.assertEqual(r["verdict"], "FAIL")
        # a FAIL on what is filled outranks DEGRADED, and the missing part is still listed
        r = claim("near", {"x1": "a", "x3": {"value": "250", "unit": "m"}})
        self.assertEqual((r["verdict"], r["missing_required"]), ("FAIL", ["x2"]))

    def test_emotive_needs_its_reading(self):
        r = claim("warm", {"x1": "the welcome", "x2": "local custom"})
        self.assertEqual((r["verdict"], r["missing_required"]),
                         ("DEGRADED", ["reading", "x3", "x4"]))    # x2 is filled; SOCIAL's are not
        self.assertEqual([m["sense"] for m in r["degraded"]["missing"]],
                         [None, "SOCIAL", "SOCIAL"])
        social = {"x1": "the host", "x3": "the guests", "x4": "the welcome at the door"}
        r = claim("warm", social, reading="SOCIAL")
        self.assertEqual(r["verdict"], "PASS")                    # SOCIAL needs no magnitude
        r = claim("safe", FULL)                                   # FEAR: no reading asked
        self.assertEqual(r["verdict"], "PASS")

    def test_i_feel_warm_self_report_passes_self_scoped(self):
        r = claim("warm", None, evidential="se'o", speaker="Ana")
        self.assertEqual((r["verdict"], r["status"], r["pass_equivalent"]),
                         ("PASS", "DERIVED", True))
        self.assertEqual((r["claim_status"], r["scope"]),
                         ("OBSERVED", "speaker's own state only"))
        self.assertTrue(r["x1_auto_filled"])
        self.assertEqual(r["slots"][0]["filling"], "Ana")          # x1 = the speaker
        self.assertEqual(r["slots"][1]["slot_state"], "VOID")
        self.assertEqual(r["waived_by_self_report"], ["reading"])   # no reading: x2..x4 not asked
        w = claim("warm", None, evidential="se'o", speaker="Ana", reading="PHYSICAL")
        self.assertEqual(w["slots"][1]["slot_state"], "WAIVED")
        self.assertEqual(w["waived_by_self_report"], ["x2", "magnitude"])
        for x1 in ("I", "me", "Ana"):                              # said outright: the same
            r = claim("warm", {"x1": x1}, evidential="se'o", speaker="Ana")
            self.assertEqual(r["verdict"], "PASS", x1)
        r = claim("warm", None, evidential="se'o")                 # no speaker to fill x1 with
        self.assertEqual(r["verdict"], "DEGRADED")
        self.assertEqual(r["missing_required"][:2], ["reading", "speaker"])   # the sense first

    def test_she_is_hostile_self_report_is_degraded(self):
        r = claim("hostile", {"x1": "she"}, evidential="se'o", speaker="Ana")
        self.assertEqual((r["verdict"], r["pass_equivalent"]), ("DEGRADED", False))
        m = r["degraded"]["missing"]
        self.assertEqual((m[0]["name"], m[0]["kind"]), ("x1", "scope"))
        self.assertIn("speaker's own state only", m[0]["reason"])
        self.assertIn("'she', not the speaker", m[0]["reason"])
        self.assertEqual(r["missing_required"], ["x1", "x2", "reading"])   # nothing waived
        self.assertEqual(r["waived_by_self_report"], [])
        self.assertEqual(r["usable"]["slots"], {"x1": "she"})      # kept all the same
        r = claim("safe", dict(FULL, x1="that location"), evidential="se'o", speaker="Ana")
        self.assertEqual(r["verdict"], "DEGRADED")                 # external, though all filled

    ORAL = {"shared": "y", "multi_gen": "y", "checkable": "y", "not_central": "y",
            "answered_by": "the carrier"}
    FOUR = ("shared", "multi_gen", "checkable", "not_central")
    BETTER = {"x1": "the new route", "x2": "the old route", "x3": "night drivers",
              "x4": "hours of rest kept"}

    def test_kau_passing_all_four_is_observed_with_provenance(self):
        r = claim("better", self.BETTER, evidential="ka'u", oral_record=self.ORAL)
        self.assertEqual((r["verdict"], r["claim_status"]), ("PASS", "OBSERVED"))   # not demoted
        self.assertEqual(r["claim_provenance"], {"transmission": "oral",
                                                 "multi_generation": True, "relay": "holder",
                                                 "answered_by": "the carrier"})
        self.assertTrue(r["oral_record"]["all_met"])
        self.assertEqual(r["oral_record"]["checks"], {n: "y" for n in self.FOUR})
        self.assertIsNone(r["oral_record"]["checkable_ref"])       # none given: no change
        self.assertEqual((r["word_class"], r["shape"]), ("JUDGMENT", "xagmau"))
        self.assertEqual(r["status"], "DERIVED")                   # the verdict's own tag
        # the provenance belongs to ka'u only
        self.assertIsNone(claim("better", self.BETTER, evidential="observed")["claim_provenance"])
        self.assertEqual(claim("better", self.BETTER, evidential="ja'o")["claim_status"],
                         "DERIVED")
        # CARRIED is no longer a status value anywhere in the checker
        import wordslots.check as wc
        self.assertNotIn("CARRIED", (ROOT / "wordslots" / "check.py").read_text())
        self.assertEqual(wc.ORAL_CHECKS, ("shared", "multi_gen", "checkable", "not_central"))

    def test_kau_one_check_n_is_proposed(self):
        for name in self.FOUR:
            row = dict(self.ORAL, **{name: "n"})
            r = claim("better", self.BETTER, evidential="ka'u", oral_record=row)
            self.assertEqual((r["verdict"], r["claim_status"]), ("PASS", "PROPOSED"), name)
            self.assertEqual(r["oral_record"]["not_met"], [name])
            self.assertIsNone(r["claim_provenance"])               # no oral provenance claimed
        r = claim("better", self.BETTER, evidential="ka'u",
                  oral_record=dict(dict.fromkeys(self.FOUR, "n"), answered_by="the carrier"))
        self.assertEqual(r["claim_status"], "PROPOSED")

    def test_kau_wrong_check_name_is_degraded(self):
        row = {"shared": "y", "multi_gen": "y", "checkable": "y", "famous": "y",
               "answered_by": "the carrier"}
        r = claim("better", self.BETTER, evidential="ka'u", oral_record=row)
        self.assertEqual((r["verdict"], r["pass_equivalent"]), ("DEGRADED", False))
        m = {x["name"]: x for x in r["degraded"]["missing"]}
        self.assertEqual(sorted(m), ["famous", "not_central"])     # both are named
        self.assertEqual(m["not_central"]["reason"], "oral-record check not answered")
        self.assertIn("not one of the four", m["famous"]["reason"])
        self.assertEqual(m["famous"]["kind"], "oral_record")
        self.assertEqual((r["claim_status"], r["claim_provenance"]), ("PROPOSED", None))
        self.assertEqual(r["usable"]["slots"], self.BETTER)        # the claim's slots are kept
        # an extra name beside the four right ones is still named
        r = claim("better", self.BETTER, evidential="ka'u",
                  oral_record=dict(self.ORAL, famous="y"))
        self.assertEqual((r["verdict"], r["missing_required"]), ("DEGRADED", ["famous"]))
        # a check left out, and no row at all
        row = {k: v for k, v in self.ORAL.items() if k != "checkable"}
        r = claim("better", self.BETTER, evidential="ka'u", oral_record=row)
        self.assertEqual((r["verdict"], r["missing_required"]), ("DEGRADED", ["checkable"]))
        r = claim("better", self.BETTER, evidential="ka'u")
        self.assertEqual((r["verdict"], r["missing_required"]),
                         ("DEGRADED", ["shared", "multi_gen", "checkable", "not_central",
                                       "answered_by"]))
        # an answer that is not y / n, or a row that is not a table: a bad tag, VOID
        for bad in (dict(self.ORAL, shared="maybe"), dict(self.ORAL, shared=True),
                    ["y", "y", "y", "y"], "yes"):
            self.assertEqual(claim("better", self.BETTER, evidential="ka'u",
                                   oral_record=bad)["verdict"], "VOID", bad)
        r = claim("better", self.BETTER, evidential="hearsay", oral_record=self.ORAL)
        self.assertEqual(r["verdict"], "VOID")                     # not a way round hearsay

    def test_kau_needs_answered_by(self):
        row = {k: v for k, v in self.ORAL.items() if k != "answered_by"}
        r = claim("better", self.BETTER, evidential="ka'u", oral_record=row)
        self.assertEqual((r["verdict"], r["pass_equivalent"]), ("DEGRADED", False))
        self.assertEqual(r["missing_required"], ["answered_by"])
        m = r["degraded"]["missing"][0]
        self.assertEqual((m["name"], m["kind"]), ("answered_by", "source"))
        self.assertEqual(m["reason"], "no source: an oral claim names where it comes from in "
                                      "oral_record.answered_by")
        self.assertEqual((r["claim_status"], r["claim_provenance"]), ("PROPOSED", None))
        for empty in ("", "   "):
            r = claim("better", self.BETTER, evidential="ka'u",
                      oral_record=dict(row, answered_by=empty))
            self.assertEqual(r["missing_required"], ["answered_by"], repr(empty))
        r = claim("better", self.BETTER, evidential="ka'u",
                  oral_record=dict(row, answered_by="a" * 41))       # X(40)
        self.assertEqual(r["verdict"], "VOID")
        self.assertIn("would truncate", r["void_reason"])
        r = claim("better", self.BETTER, evidential="ka'u", oral_record=dict(row, answered_by=7))
        self.assertEqual(r["verdict"], "VOID")
        # with it, whole again; and it is not counted as a fifth check
        r = claim("better", self.BETTER, evidential="ka'u", oral_record=self.ORAL)
        self.assertEqual((r["verdict"], r["oral_record"]["answered_by"]), ("PASS", "the carrier"))
        self.assertEqual(r["oral_record"]["other_names"], [])

    def test_kau_checkable_ref_is_re_read(self):
        import tempfile
        from infer import record_sha
        from numcheck import check_all as numcheck_all
        val = lambda v, u: {"value": v, "unit": u}                 # noqa: E731
        with tempfile.TemporaryDirectory() as d:
            report = numcheck_all([{"formula": "F = m*a", "values": {
                "F": val("7.5", "N"), "m": val("2.5", "kg"), "a": val(3, "m/s**2")}}])
            (Path(d) / "report.json").write_text(json.dumps(report))
            ref = {"file": "report.json", "record": 0,
                   "sha256": record_sha(report["records"][0])}

            def run(oral):
                return check_claim({"word": "better", "slots": self.BETTER,
                                    "evidential": "ka'u", "oral_record": oral}, WORDS,
                                   base_dir=d)
            r = run(dict(self.ORAL, checkable_ref=ref))            # re-read and equal
            self.assertEqual((r["verdict"], r["claim_status"]), ("PASS", "OBSERVED"))
            c = r["oral_record"]["checkable_ref"]
            self.assertEqual((c["state"], c["sha256"], c["verdict_read"]),
                             ("RE_READ", ref["sha256"], "HOLDS"))
            # mismatch: the sha256 of something else
            r = run(dict(self.ORAL, checkable_ref=dict(ref, sha256="0" * 64)))
            self.assertEqual((r["verdict"], r["missing_required"]),
                             ("DEGRADED", ["checkable_ref"]))
            self.assertIn("sha256 mismatch", r["degraded"]["missing"][0]["reason"])
            self.assertEqual((r["claim_status"], r["claim_provenance"]), ("PROPOSED", None))
            self.assertEqual(r["oral_record"]["checkable_ref"]["state"], "NOT_RE_READ")
            # the file is edited after the reference was taken
            changed = json.loads(json.dumps(report))
            changed["records"][0]["verdict"] = "FAILS"
            (Path(d) / "report.json").write_text(json.dumps(changed))
            self.assertEqual(run(dict(self.ORAL, checkable_ref=ref))["verdict"], "DEGRADED")
            # the file is not there, the record is not there, the reference is malformed
            for bad, why in ((dict(ref, file="none.json"), "cannot read"),
                             (dict(ref, record=9), "no record 9"),
                             (dict(ref, branch="2b"), "undeclared field"),
                             ({"file": "report.json"}, "needs file and sha256"),
                             ("report.json", "not a {file, record, sha256}")):
                r = run(dict(self.ORAL, checkable_ref=bad))
                self.assertEqual(r["verdict"], "DEGRADED", bad)
                self.assertIn(why, r["degraded"]["missing"][0]["reason"])
            # absent: no change at all
            r = run(self.ORAL)
            self.assertEqual((r["verdict"], r["claim_status"]), ("PASS", "OBSERVED"))

    def test_written_claim_needs_a_source_id(self):
        r = claim("safe", FULL, evidential="hearsay", source_id=None)
        self.assertEqual((r["verdict"], r["status"], r["pass_equivalent"]),
                         ("DEGRADED", "DERIVED", False))
        self.assertEqual(r["missing_required"], ["source_id"])
        m = r["degraded"]["missing"][0]
        self.assertEqual((m["name"], m["kind"]), ("source_id", "source"))
        self.assertEqual(m["reason"],
                         "no source: a written claim names where it comes from in source_id")
        self.assertEqual(r["usable"]["slots"], FULL)               # the claim is kept
        self.assertEqual(r["source_kind"], "written")
        for empty in ("", "   "):
            r = claim("safe", FULL, evidential="observed", source_id=empty)
            self.assertEqual(r["missing_required"], ["source_id"], repr(empty))
        r = claim("safe", FULL, source_id=None)                    # no evidential at all
        self.assertEqual((r["verdict"], r["missing_required"]), ("DEGRADED", ["source_id"]))
        # with a source_id: unchanged
        for ev in ("observed", "hearsay", "concluded", "opinion", "defined", "ja'o", None):
            r = claim("safe", FULL, evidential=ev, source_id="report 12")
            self.assertEqual((r["verdict"], r["pass_equivalent"], r["source_id"]),
                             ("PASS", True, "report 12"), ev)
        # the old field name is not a declared field any more
        r = check_claim({"word": "safe", "slots": FULL, "source": "report 12"}, WORDS)
        self.assertEqual(r["verdict"], "VOID")
        self.assertIn("undeclared field: 'source'", r["void_reason"])

    def test_self_report_needs_no_source(self):
        r = claim("warm", None, evidential="se'o", speaker="Ana", source_id=None)
        self.assertEqual((r["verdict"], r["pass_equivalent"]), ("PASS", True))
        self.assertEqual((r["source_id"], r["source_kind"]), ("Ana", "self"))   # = the speaker
        self.assertTrue(r["source_auto_filled"])
        self.assertNotIn("source_id", r["missing_required"])
        # external se'o is DEGRADED for its scope, and still not for a source
        r = claim("hostile", {"x1": "she"}, evidential="se'o", speaker="Ana", source_id=None)
        self.assertEqual(r["verdict"], "DEGRADED")
        self.assertNotIn("source_id", r["missing_required"])

    def test_oral_claim_needs_no_source_id(self):
        r = claim("better", self.BETTER, evidential="ka'u", oral_record=self.ORAL,
                  source_id=None)
        self.assertEqual((r["verdict"], r["claim_status"]), ("PASS", "OBSERVED"))
        self.assertEqual((r["source_id"], r["source_kind"]), ("the carrier", "oral"))

    def test_missing_source_has_the_same_shape_on_both_routes(self):
        written = claim("better", self.BETTER, evidential="hearsay", source_id=None)
        row = {k: v for k, v in self.ORAL.items() if k != "answered_by"}
        oral = claim("better", self.BETTER, evidential="ka'u", oral_record=row, source_id=None)
        for r in (written, oral):
            self.assertEqual((r["verdict"], r["status"], r["pass_equivalent"]),
                             ("DEGRADED", "DERIVED", False))
            self.assertEqual(len(r["degraded"]["missing"]), 1)
            self.assertEqual(r["degraded"]["kept"], ["x1", "x2", "x3", "x4"])
            self.assertEqual(r["usable"]["slots"], self.BETTER)
            self.assertEqual(r["located_error"]["slot"], r["missing_required"][0])
        mw, mo = written["degraded"]["missing"][0], oral["degraded"]["missing"][0]
        self.assertEqual(sorted(mw), sorted(mo))                   # the same keys
        self.assertEqual((mw["kind"], mo["kind"]), ("source", "source"))
        self.assertEqual(mw["provenance"], mo["provenance"])
        self.assertEqual((mw["name"], mo["name"]), ("source_id", "answered_by"))
        self.assertTrue(mw["reason"].startswith("no source: a written claim"))
        self.assertTrue(mo["reason"].startswith("no source: an oral claim"))
        self.assertEqual(sorted(written), sorted(oral))            # the records' keys too

    def test_classes_and_shapes_in_table_v2(self):
        got = {w: (e.get("class"), e.get("shape")) for w, e in WORDS.items()}
        self.assertEqual(got["more"], ("COMPARATIVE", "zmadu"))
        self.assertEqual(got["less"], ("COMPARATIVE", "mleca"))
        self.assertEqual(got["efficient"], ("COMPARATIVE", None))
        self.assertEqual(got["better"], ("JUDGMENT", "xagmau"))
        self.assertEqual(got["appropriate"], ("JUDGMENT", "mapti"))
        self.assertEqual((got["hostile"][1], got["safe"][1], got["warm"][1]),
                         ("le'onmo", "snura", "glare"))
        self.assertEqual((got["warm"][0], got["hostile"][0], got["safe"][0]),
                         ("EMOTIVE", "EMOTIVE", "FEAR"))
        self.assertIsNone(TABLE["holder"])
        self.assertEqual([s["name"] for s in WORDS["more"]["slots"]], ["x1", "x2", "x3", "x4"])
        r = claim("more", {"x1": "this pump"})
        self.assertEqual((r["verdict"], r["missing_required"]), ("DEGRADED", ["x2", "x3"]))
        r = claim("less", {"x1": "this machine", "x2": "the old one",
                           "x3": "litres per hour"})
        self.assertEqual(r["verdict"], "PASS")                    # x4, by what amount, optional
        r = claim("better", {"x1": "a", "x2": "b", "x3": "c"})    # xagmau: the standard is x4
        self.assertEqual((r["verdict"], r["missing_required"]), ("DEGRADED", ["x4"]))
        r = claim("appropriate", {"x1": "the tool", "x2": "the job", "x3": "torque range"})
        self.assertEqual(r["verdict"], "PASS")
        r = claim("hostile", {"x1": "the dog", "x2": "strangers"}, reading="SOCIAL")
        self.assertEqual(r["verdict"], "PASS")                    # le'onmo: two places
        r = claim("hostile", {"x1": "the dog", "x2": "strangers", "x3": "by bite count"},
                  reading="SOCIAL")
        self.assertIn("undeclared slot for 'hostile': x3", r["void_reason"])
        t = copy.deepcopy(TABLE)
        t["words"]["more"]["class"] = "VIBES"
        self.assertIsNotNone(check_all([{"word": "more"}], t)["table_void"])

    def test_safe_needs_its_sense(self):
        r = claim("safe", FULL, sense=None)
        self.assertEqual((r["verdict"], r["missing_required"]), ("DEGRADED", ["sense", "x4"]))
        self.assertIn("PROTECTED or NOT_PERILOUS", r["degraded"]["missing"][0]["reason"])
        self.assertEqual(r["usable"]["slots"], FULL)               # what is filled is kept
        # with no sense, the sense comes first, then each sense's empty slots under its name
        r = claim("safe", {"x1": "the bridge", "x3": "pedestrians"}, sense=None)
        self.assertEqual(r["missing_required"], ["sense", "x2", "x4"])

    def test_no_sense_safe_lists_sense_shared_then_each_sense_grouped(self):
        r = claim("safe", {"x1": "the bridge"}, sense=None)
        self.assertEqual(r["verdict"], "DEGRADED")
        m = r["degraded"]["missing"]
        self.assertEqual([(x["name"], x["sense"]) for x in m],
                         [("sense", None), ("x3", None), ("x2", "PROTECTED"),
                          ("x4", "NOT_PERILOUS")])
        self.assertEqual([x["kind"] for x in m], ["field", "slot", "slot", "slot"])
        self.assertEqual([x["role"] for x in m[1:]],
                         ["for whom", "from threat", "under conditions"])
        self.assertEqual(m[2]["reason"], "required under sense PROTECTED; no sense given")
        self.assertEqual(r["missing_by_sense"],
                         {"required": ["sense"], "shared": ["x3"],
                          "by_sense": {"PROTECTED": ["x2"], "NOT_PERILOUS": ["x4"]}})
        self.assertEqual(r["located_error"]["slot"], "sense")     # the first thing to settle
        self.assertEqual(r["senses"], ["PROTECTED", "NOT_PERILOUS"])
        # a missing source is shared too, and stays ahead of the per-sense groups
        r = claim("safe", {"x1": "the bridge"}, sense=None, source_id=None)
        self.assertEqual(r["missing_required"], ["sense", "source_id", "x3", "x2", "x4"])
        self.assertEqual(r["missing_by_sense"]["shared"], ["source_id", "x3"])
        # warm's sense is its reading: the same grouping
        r = claim("warm", {"x1": "the room"})
        self.assertEqual([(x["name"], x["sense"]) for x in r["degraded"]["missing"]],
                         [("reading", None), ("x2", "PHYSICAL"), ("x3", "SOCIAL"),
                          ("x4", "SOCIAL")])
        # a word with no senses: every missing item carries sense null, nothing grouped
        r = claim("near", {"x1": "the shop"})
        self.assertEqual([(x["name"], x["sense"]) for x in r["degraded"]["missing"]],
                         [("x2", None)])
        self.assertIsNone(r["missing_by_sense"])

    def test_protected_safe_missing_x2_lists_only_x2(self):
        r = claim("safe", {"x1": "the bridge", "x3": "pedestrians"}, sense="PROTECTED")
        self.assertEqual((r["verdict"], r["missing_required"]), ("DEGRADED", ["x2"]))
        m = r["degraded"]["missing"]
        self.assertEqual([(x["name"], x["sense"], x["reason"]) for x in m],
                         [("x2", "PROTECTED", "required slot empty")])
        self.assertIsNone(r["missing_by_sense"])                  # a sense was given
        r = claim("safe", {"x1": "the bridge"}, sense="PROTECTED")   # slot order kept
        self.assertEqual([(x["name"], x["sense"]) for x in r["degraded"]["missing"]],
                         [("x2", "PROTECTED"), ("x3", None)])
        r = claim("safe", {"x1": "the bridge"}, sense="NOT_PERILOUS")
        self.assertEqual([(x["name"], x["sense"]) for x in r["degraded"]["missing"]],
                         [("x3", None), ("x4", "NOT_PERILOUS")])
        r = claim("safe", FULL, sense="PROTECTED")                 # snura: from threat x2
        self.assertEqual((r["verdict"], r["sense"], r["sense_predicate"]),
                         ("PASS", "PROTECTED", "snura"))
        r = claim("safe", {"x1": "the bridge", "x3": "pedestrians"}, sense="PROTECTED")
        self.assertEqual((r["verdict"], r["missing_required"]), ("DEGRADED", ["x2"]))
        # NOT_PERILOUS (ckape): no threat place; for whom is asked in both senses
        r = claim("safe", {"x1": "the bridge", "x3": "pedestrians", "x4": "in a dry summer"},
                  sense="NOT_PERILOUS")
        self.assertEqual((r["verdict"], r["sense_predicate"]), ("PASS", "ckape"))
        self.assertEqual((r["slots"][1]["slot_state"], r["slots"][1]["in_sense"]),
                         ("VOID", False))                          # kept as a void slot
        r = claim("safe", {"x1": "the bridge"}, sense="NOT_PERILOUS")
        self.assertEqual(r["missing_required"], ["x3", "x4"])
        r = claim("safe", FULL, sense="PROTECTED")                 # conditions: not asked here
        self.assertEqual((r["verdict"], r["slots"][3]["in_sense"]), ("PASS", False))

    def test_safe_not_perilous_missing_conditions_is_degraded_naming_it(self):
        r = claim("safe", {"x1": "the bridge", "x3": "pedestrians"}, sense="NOT_PERILOUS")
        self.assertEqual((r["verdict"], r["pass_equivalent"], r["missing_required"]),
                         ("DEGRADED", False, ["x4"]))
        m = r["degraded"]["missing"][0]
        self.assertEqual((m["name"], m["role"], m["reason"]),
                         ("x4", "under conditions", "required slot empty"))
        self.assertEqual(r["slots"][3]["source_predicate"], "ckape")
        self.assertEqual(r["degraded"]["kept"], ["x1", "x3"])
        r = claim("safe", FULL, sense="SAFE_ENOUGH")               # a bad tag
        self.assertEqual(r["verdict"], "VOID")
        self.assertIn("sense 'SAFE_ENOUGH' is not one of PROTECTED, NOT_PERILOUS",
                      r["void_reason"])
        r = claim("safe", FULL, sense="P" * 13)                    # X(12)
        self.assertIn("would truncate", r["void_reason"])
        # a word with no sense slot refuses one; warm's sense is its reading
        r = claim("near", {"x1": "a", "x2": "b"}, sense="PROTECTED")
        self.assertIn("'near' has no sense slot", r["void_reason"])
        r = claim("warm", {"x1": "a"}, sense="PHYSICAL")
        self.assertIn("its sense is given in reading", r["void_reason"])

    def test_warm_sense_is_the_existing_reading(self):
        self.assertEqual((WORDS["warm"]["sense_field"], WORDS["warm"]["senses"]),
                         ("reading", {"PHYSICAL": "glare", "SOCIAL": "xendo"}))
        r = warm("295")
        self.assertEqual((r["sense"], r["sense_predicate"]), ("PHYSICAL", "glare"))
        self.assertEqual([x["in_sense"] for x in r["slots"]], [None, True, False, False])
        r = claim("warm", {"x1": "the host"}, reading="SOCIAL")    # xendo: to whom, in what
        self.assertEqual((r["verdict"], r["missing_required"], r["sense_predicate"]),
                         ("DEGRADED", ["x3", "x4"], "xendo"))
        r = claim("warm", {"x1": "the room"}, reading="PHYSICAL", magnitude={"value": "295",
                                                                             "unit": "K"})
        self.assertEqual(r["missing_required"], ["x2"])            # glare: by standard

    def test_evidentials_baa_and_sua(self):
        for ev, status in (("ba'a", "PROPOSED"), ("su'a", "PROPOSED"), ("ba'anai", "OBSERVED")):
            r = claim("safe", FULL, evidential=ev)
            self.assertEqual((r["verdict"], r["claim_status"], r["source_kind"]),
                             ("PASS", status, "written"), ev)
            r = claim("safe", FULL, evidential=ev, source_id=None)  # a written route
            self.assertEqual(r["missing_required"], ["source_id"], ev)
        r = claim("safe", FULL, evidential="ba'anai")
        self.assertEqual(r["claim_provenance"]["basis"], "memory")
        self.assertIsNone(claim("safe", FULL, evidential="ba'a")["claim_provenance"])
        self.assertIsNone(claim("safe", FULL, evidential="su'a")["claim_provenance"])
        # ba'acu'i is self-scoped exactly as se'o
        a = claim("warm", None, evidential="ba'acu'i", speaker="Ana", source_id=None)
        b = claim("warm", None, evidential="se'o", speaker="Ana", source_id=None)
        self.assertEqual((a["verdict"], a["claim_status"], a["scope"], a["source_kind"]),
                         ("PASS", "OBSERVED", "speaker's own state only", "self"))
        skip = ("evidential",)
        self.assertEqual({k: v for k, v in a.items() if k not in skip},
                         {k: v for k, v in b.items() if k not in skip})
        r = claim("hostile", {"x1": "she"}, evidential="ba'acu'i", speaker="Ana")
        self.assertEqual(r["verdict"], "DEGRADED")
        self.assertIn("ba'acu'i covers the speaker's own state only", 
                      r["degraded"]["missing"][0]["reason"])
        r = claim("safe", None, evidential="ba'acu'i", speaker="Ana", sense=None)
        self.assertEqual((r["verdict"], r["waived_by_self_report"]),
                         ("PASS", ["x3", "sense"]))
        r = claim("safe", FULL, evidential="ba'acu'i", oral_record=self.ORAL)
        self.assertEqual(r["verdict"], "VOID")                     # oral_record is ka'u's

    def test_fixed_width_guard(self):
        ok40, long41 = "s" * 40, "s" * 41
        r = claim("safe", dict(FULL, x1=ok40))
        self.assertEqual(r["verdict"], "PASS")
        r = claim("safe", dict(FULL, x1=long41))                   # 41 characters into X(40)
        self.assertEqual((r["verdict"], r["status"]), ("VOID", None))
        self.assertIn("would truncate", r["void_reason"])
        self.assertIn("41 characters, the field is X(40)", r["void_reason"])
        self.assertIsNone(r["slots"])                              # nothing was cut and kept
        r = claim("safe", dict(FULL, x1={"text": long41}))
        self.assertIn("would truncate", r["void_reason"])
        whole = {"x1": "the tank", "x2": "the gauge"}
        r = claim("warm", whole, reading="PHYSICAL", magnitude={"value": "1234567", "unit": "K"})
        self.assertNotEqual(r["verdict"], "VOID")
        r = claim("warm", whole, reading="PHYSICAL", magnitude={"value": "12345678", "unit": "K"})
        self.assertEqual(r["verdict"], "VOID")                     # 12345678 into S9(7)
        self.assertIn("would truncate: magnitude 12345678 is beyond S9(7)V9(4)",
                      r["void_reason"])
        r = claim("warm", whole, reading="PHYSICAL", magnitude={"value": "-12345678"})
        self.assertEqual(r["verdict"], "VOID")
        r = claim("warm", whole, reading="PHYSICAL", magnitude={"value": "1.23456", "unit": "K"})
        self.assertIn("more than 4 decimal places", r["void_reason"])
        r = claim("warm", whole, reading="PHYSICAL", magnitude={"value": "1.2345", "unit": "K"})
        self.assertNotEqual(r["verdict"], "VOID")
        for field, n in (("source_id", 40), ("speaker", 40), ("source_path", 80)):
            self.assertEqual(claim("safe", FULL, **{field: "a" * n})["verdict"], "PASS")
            r = claim("safe", FULL, **{field: "a" * (n + 1)})
            self.assertIn("would truncate", r["void_reason"], field)
        r = claim("warm", whole, reading="PHYSICAL",
                  magnitude={"value": "1", "unit": "kilometres-per-hour"})
        self.assertIn("X(12)", r["void_reason"])
        self.assertIn("would truncate", check_claim({"word": "w" * 21}, WORDS)["void_reason"])


class TestRanges(unittest.TestCase):
    def test_in_range_out_of_range(self):
        r = warm("295")
        self.assertEqual((r["verdict"], r["status"]), ("PASS", "DERIVED"))
        g = r["ranges"][0]
        self.assertEqual((g["slot"], g["range"], g["state"]), ("x2", "room", "IN_RANGE"))
        self.assertEqual((g["numcheck"]["verdict"], g["numcheck"]["rigorous"]), ("HOLDS", True))
        r = warm("305")
        self.assertEqual((r["verdict"], r["status"]), ("FAIL", "DERIVED"))
        e = r["located_error"]
        self.assertEqual((e["slot"], e["range"]), ("x2", "room"))
        self.assertEqual(e["bounds"], {"lo": "291", "hi": "299", "unit": "K"})
        self.assertEqual(warm("310", rng="body")["verdict"], "PASS")   # another named range
        self.assertEqual(warm("291")["verdict"], "PASS")               # the edge is inside
        self.assertEqual(warm("299.0001")["verdict"], "FAIL")

    def test_interval_value(self):
        self.assertEqual(warm(["292", "298"])["verdict"], "PASS")
        r = warm(["298", "301"])                       # partly in, partly out
        self.assertEqual((r["verdict"], r["status"]), ("UNDECIDED", "DERIVED"))
        self.assertEqual(r["ranges"][0]["state"], "MIXED")
        self.assertEqual(warm(["300", "301"])["verdict"], "FAIL")

    def test_units_first(self):
        r = warm("295", unit="m")                      # a length against a temperature range
        self.assertEqual(r["verdict"], "VOID")
        self.assertIn("numcheck VOID", r["void_reason"])
        self.assertIn("units FAIL", r["void_reason"])
        self.assertEqual(warm("295", unit=None)["verdict"], "VOID")

    def test_unchecked_is_not_a_pass_of_the_bound(self):
        r = claim("near", {"x1": "the room", "x2": "the stairs", "x3": "a few steps"})
        self.assertEqual(r["verdict"], "PASS")                       # the slots are filled
        self.assertEqual(r["ranges"][0]["state"], "UNCHECKED")
        r = claim("warm", {"x1": "the room", "x2": {"text": "room standard", "is": "room"},
                           "x3": "the guests", "x4": "the welcome"}, reading="SOCIAL")
        self.assertEqual(r["verdict"], "PASS")       # x2 is out of the SOCIAL sense, and kept
        self.assertEqual((r["slots"][1]["slot_state"], r["slots"][1]["in_sense"]),
                         ("FILLED", False))
        self.assertEqual(r["ranges"][0]["state"], "UNCHECKED")       # the bound was not checked
        self.assertIsNone(r["ranges"][0]["numcheck"])
        r = claim("warm", {"x1": "the room", "x2": {"text": "std", "value": "295", "unit": "K",
                                                    "is": "sauna"}}, reading="PHYSICAL")
        self.assertEqual(r["verdict"], "VOID")
        self.assertIn("range 'sauna' is not declared", r["void_reason"])
        # plain bounds on a slot are checked without naming them
        r = claim("near", {"x1": "a", "x2": "b", "x3": {"value": "250", "unit": "m"}})
        self.assertEqual((r["verdict"], r["located_error"]["range"]), ("FAIL", "bounds"))
        r = claim("near", {"x1": "a", "x2": "b", "x3": {"value": "25", "unit": "m"}})
        self.assertEqual(r["verdict"], "PASS")


class TestCli(unittest.TestCase):
    def cli(self, *args):
        return subprocess.run([sys.executable, "-m", "wordslots", *args], cwd=ROOT,
                              capture_output=True, text=True)

    def test_exit_codes(self):
        r = self.cli("check", "claims.json", "--json")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(json.loads(r.stdout)["counts"],
                         {"PASS": 5, "DEGRADED": 5, "FAIL": 1, "UNDECIDED": 0, "VOID": 2})
        self.assertEqual(self.cli().returncode, 2)
        self.assertEqual(self.cli("check", "nope.json").returncode, 2)
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "c.json"
            ok = {"word": "safe", "slots": FULL, "sense": "PROTECTED",
                  "source_id": "report 12"}
            f.write_text(json.dumps([ok]))
            self.assertEqual(self.cli("check", str(f)).returncode, 0)
            f.write_text(json.dumps([{"word": "safe", "slots": FULL,
                                      "sense": "PROTECTED"}]))               # no source
            r = self.cli("check", str(f))
            self.assertEqual(r.returncode, 3)
            self.assertIn("missing: source_id (no source: a written claim", r.stdout)
            f.write_text(json.dumps([ok, {"word": "safe", "slots": {"x1": "a"},
                                          "sense": "PROTECTED", "source_id": "report 12"}]))
            r = self.cli("check", str(f))
            self.assertEqual(r.returncode, 3)
            self.assertIn("missing: x2[PROTECTED] (required slot empty); x3 (required slot empty)",
                          r.stdout)
            self.assertIn("DEGRADED", r.stdout)
            t = Path(d) / "t.json"
            t.write_text(json.dumps({"words": {"tall": {"status": "OBSERVED", "slots": [
                {"name": "x1", "role": "who", "required": True, "status": "OBSERVED",
                 "source_predicate": "physics_def"}]}}}))
            f.write_text(json.dumps([{"word": "tall", "slots": {"x1": "the tower"},
                                      "source_id": "survey"}]))
            r = self.cli("check", str(f), "--table", str(t), "--json")
            self.assertEqual(r.returncode, 0)
            self.assertEqual(json.loads(r.stdout)["records"][0]["table_entry_status"], "OBSERVED")
            self.assertEqual(self.cli("check", str(f)).returncode, 3)    # not in the default table
            self.assertEqual(self.cli("check", str(f), "--table", "nope.json").returncode, 2)


if __name__ == "__main__":
    unittest.main()
