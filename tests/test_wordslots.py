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
        self.assertEqual([s["name"] for s in WORDS["safe"]["slots"]], ["x1", "x2", "x3"])
        self.assertEqual([s["role"] for s in WORDS["warm"]["slots"]],
                         ["what is warm", "by standard"])

    def test_bad_tables_void_every_claim(self):
        def broken(change):
            t = copy.deepcopy(TABLE)
            change(t["words"]["safe"])
            return check_all([{"word": "safe", "slots": FULL}], t)
        for change in (lambda e: e.pop("status"),
                       lambda e: e["slots"][0].pop("required"),
                       lambda e: e["slots"][0].pop("status"),
                       lambda e: e["slots"][0].update(colour="red"),
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
                         [("x1", "FILLED"), ("x2", "VOID"), ("x3", "VOID")])
        for empty in ("", "   ", None, {"text": ""}, {"text": None}):
            r = claim("safe", dict(FULL, x3=empty))
            self.assertEqual((r["verdict"], r["missing_required"]), ("DEGRADED", ["x3"]), empty)
        self.assertEqual(claim("safe", None)["missing_required"], ["x1", "x2", "x3"])

    def test_fully_filled_passes(self):
        r = claim("safe", FULL, evidential="observed", source="inspection report 12")
        self.assertEqual((r["verdict"], r["status"]), ("PASS", "DERIVED"))
        self.assertEqual(r["missing_required"], [])
        self.assertEqual(r["source"], "inspection report 12")
        self.assertEqual(r["table_entry_status"], "PROPOSED")      # the table's tag rides along
        self.assertIsNone(r["human_interest"])
        self.assertIsNone(r["ai_interest"])

    def test_hearsay_is_carried_not_upgraded(self):
        r = claim("safe", FULL, evidential="hearsay", source="a neighbour")
        self.assertEqual(r["verdict"], "PASS")
        self.assertEqual(r["status"], "DERIVED")                   # the verdict's status
        self.assertEqual((r["evidential"], r["claim_status"]), ("hearsay", "PROPOSED"))
        self.assertNotEqual(r["claim_status"], r["status"])        # a PASS does not lift it
        self.assertEqual({e: claim("safe", FULL, evidential=e)["claim_status"]
                          for e in EVIDENTIAL if e not in ("se'o", "ka'u")},
                         {"observed": "OBSERVED", "concluded": "DERIVED", "hearsay": "PROPOSED",
                          "opinion": "PROPOSED", "defined": "OBSERVED", "ja'o": "DERIVED"})
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
        r = claim("safe", dict(FULL, x4="extra"))
        self.assertIn("undeclared slot for 'safe': x4", r["void_reason"])
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
                         {"word", "slots", "reading", "magnitude", "evidential", "speaker",
                          "oral_record", "source", "source_path", "table"})
        for bad in ({"reading": "WARMISH"}, {"evidential": "za'a'a"},
                    {"magnitude": {"value": "1", "weight": 2}}, {"oral_record": {}}):
            r = check_claim({"word": "safe", "slots": FULL, **bad}, WORDS)
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
                  source="a sign by the pool")
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
        self.assertEqual((r["verdict"], r["missing_required"]), ("DEGRADED", ["reading"]))
        r = claim("warm", {"x1": "the welcome", "x2": "local custom"}, reading="SOCIAL")
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
        self.assertEqual(r["slots"][1]["slot_state"], "WAIVED")
        self.assertEqual(r["waived_by_self_report"], ["x2", "reading"])
        for x1 in ("I", "me", "Ana"):                              # said outright: the same
            r = claim("warm", {"x1": x1}, evidential="se'o", speaker="Ana")
            self.assertEqual(r["verdict"], "PASS", x1)
        r = claim("warm", None, evidential="se'o")                 # no speaker to fill x1 with
        self.assertEqual((r["verdict"], r["missing_required"][0]), ("DEGRADED", "speaker"))

    def test_she_is_hostile_self_report_is_degraded(self):
        r = claim("hostile", {"x1": "she"}, evidential="se'o", speaker="Ana")
        self.assertEqual((r["verdict"], r["pass_equivalent"]), ("DEGRADED", False))
        m = r["degraded"]["missing"]
        self.assertEqual((m[0]["name"], m[0]["kind"]), ("x1", "scope"))
        self.assertIn("speaker's own state only", m[0]["reason"])
        self.assertIn("'she', not the speaker", m[0]["reason"])
        self.assertEqual(r["missing_required"], ["x1", "x2", "x3", "reading"])   # nothing waived
        self.assertEqual(r["waived_by_self_report"], [])
        self.assertEqual(r["usable"]["slots"], {"x1": "she"})      # kept all the same
        r = claim("safe", dict(FULL, x1="that location"), evidential="se'o", speaker="Ana")
        self.assertEqual(r["verdict"], "DEGRADED")                 # external, though all filled

    ORAL = {"shared": "y", "multi_gen": "y", "checkable": "y", "not_central": "y",
            "answered_by": "the carrier"}
    FOUR = ("shared", "multi_gen", "checkable", "not_central")
    BETTER = {"x1": "the new route", "x2": "night drivers", "x3": "hours of rest kept"}

    def test_kau_passing_all_four_is_observed_with_provenance(self):
        r = claim("better", self.BETTER, evidential="ka'u", oral_record=self.ORAL)
        self.assertEqual((r["verdict"], r["claim_status"]), ("PASS", "OBSERVED"))   # not demoted
        self.assertEqual(r["claim_provenance"], {"transmission": "oral",
                                                 "multi_generation": True, "relay": "holder",
                                                 "answered_by": "the carrier"})
        self.assertTrue(r["oral_record"]["all_met"])
        self.assertEqual(r["oral_record"]["checks"], {n: "y" for n in self.FOUR})
        self.assertIsNone(r["oral_record"]["checkable_ref"])       # none given: no change
        self.assertEqual((r["word_class"], r["shape"]), ("JUDGMENT", "xamgu"))
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
        self.assertEqual((m["name"], m["kind"]), ("answered_by", "oral_record"))
        self.assertIn("who answered the four checks", m["reason"])
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

    def test_classes_and_shapes_in_table_v0(self):
        got = {w: (e.get("class"), e.get("shape")) for w, e in WORDS.items()}
        self.assertEqual(got["more"], ("COMPARATIVE", "zmadu"))
        self.assertEqual(got["less"], ("COMPARATIVE", "zmadu"))
        self.assertEqual(got["efficient"], ("COMPARATIVE", "zmadu"))
        self.assertEqual(got["better"], ("JUDGMENT", "xamgu"))
        self.assertEqual(got["appropriate"], ("JUDGMENT", "xamgu"))
        self.assertEqual((got["warm"][0], got["hostile"][0], got["safe"][0]),
                         ("EMOTIVE", "EMOTIVE", "FEAR"))
        self.assertIsNone(TABLE["holder"])
        self.assertEqual([s["name"] for s in WORDS["more"]["slots"]], ["x1", "x2", "x3", "x4"])
        r = claim("more", {"x1": "this pump"})
        self.assertEqual((r["verdict"], r["missing_required"]), ("DEGRADED", ["x2", "x3"]))
        r = claim("efficient", {"x1": "this machine", "x2": "the old one",
                                "x3": "litres per hour"})
        self.assertEqual(r["verdict"], "PASS")                    # x4, by what amount, optional
        t = copy.deepcopy(TABLE)
        t["words"]["more"]["class"] = "VIBES"
        self.assertIsNotNone(check_all([{"word": "more"}], t)["table_void"])

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
        for field, n in (("source", 40), ("speaker", 40), ("source_path", 80)):
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
        r = claim("warm", {"x1": "the room", "x2": {"text": "room standard", "is": "room"}},
                  reading="SOCIAL")
        self.assertEqual(r["verdict"], "PASS")                       # the slots are filled
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
                         {"PASS": 4, "DEGRADED": 4, "FAIL": 1, "UNDECIDED": 0, "VOID": 2})
        self.assertEqual(self.cli().returncode, 2)
        self.assertEqual(self.cli("check", "nope.json").returncode, 2)
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "c.json"
            f.write_text(json.dumps([{"word": "safe", "slots": FULL}]))
            self.assertEqual(self.cli("check", str(f)).returncode, 0)
            f.write_text(json.dumps([{"word": "safe", "slots": FULL},
                                     {"word": "safe", "slots": {"x1": "a"}}]))
            r = self.cli("check", str(f))
            self.assertEqual(r.returncode, 3)
            self.assertIn("missing: x2 (required slot empty); x3 (required slot empty)",
                          r.stdout)
            self.assertIn("DEGRADED", r.stdout)
            t = Path(d) / "t.json"
            t.write_text(json.dumps({"words": {"tall": {"status": "OBSERVED", "slots": [
                {"name": "x1", "role": "who", "required": True, "status": "OBSERVED"}]}}}))
            f.write_text(json.dumps([{"word": "tall", "slots": {"x1": "the tower"}}]))
            r = self.cli("check", str(f), "--table", str(t), "--json")
            self.assertEqual(r.returncode, 0)
            self.assertEqual(json.loads(r.stdout)["records"][0]["table_entry_status"], "OBSERVED")
            self.assertEqual(self.cli("check", str(f)).returncode, 3)    # not in the default table
            self.assertEqual(self.cli("check", str(f), "--table", "nope.json").returncode, 2)


if __name__ == "__main__":
    unittest.main()
