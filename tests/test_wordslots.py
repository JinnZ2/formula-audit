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
                                                    "is": rng}})


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
    def test_safe_with_no_x2_x3_is_void_naming_both(self):
        r = claim("safe", {"x1": "the bridge"})
        self.assertEqual((r["verdict"], r["status"]), ("VOID", None))
        self.assertEqual(r["missing_required"], ["x2", "x3"])
        self.assertIn("x2 (from threat)", r["void_reason"])
        self.assertIn("x3 (for whom)", r["void_reason"])
        # the void slots are kept on the record, not dropped
        self.assertEqual([(s["name"], s["slot_state"]) for s in r["slots"]],
                         [("x1", "FILLED"), ("x2", "VOID"), ("x3", "VOID")])
        for empty in ("", "   ", None, {"text": ""}, {"text": None}):
            r = claim("safe", dict(FULL, x3=empty))
            self.assertEqual((r["verdict"], r["missing_required"]), ("VOID", ["x3"]), empty)
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
                          for e in EVIDENTIAL},
                         {"observed": "OBSERVED", "concluded": "DERIVED", "hearsay": "PROPOSED",
                          "opinion": "PROPOSED", "defined": "OBSERVED"})
        r = claim("safe", FULL)                                    # none given: stays null
        self.assertEqual((r["verdict"], r["claim_status"]), ("PASS", None))
        r = claim("safe", {"x1": "the bridge"}, evidential="hearsay")
        self.assertEqual((r["verdict"], r["claim_status"]), ("VOID", "PROPOSED"))

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
                         {"word", "slots", "evidential", "source", "source_path", "table"})

    def test_optional_slot_may_stay_void(self):
        r = claim("near", {"x1": "the shop", "x2": "the station"})
        self.assertEqual(r["verdict"], "PASS")
        self.assertEqual(r["slots"][2]["slot_state"], "VOID")        # kept, and not required
        self.assertEqual(r["ranges"], [])


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
        r = claim("warm", {"x1": "the room", "x2": {"text": "room standard", "is": "room"}})
        self.assertEqual(r["verdict"], "PASS")                       # the slots are filled
        self.assertEqual(r["ranges"][0]["state"], "UNCHECKED")       # the bound was not checked
        self.assertIsNone(r["ranges"][0]["numcheck"])
        r = claim("warm", {"x1": "the room", "x2": {"text": "std", "value": "295", "unit": "K",
                                                    "is": "sauna"}})
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
                         {"PASS": 3, "FAIL": 1, "UNDECIDED": 0, "VOID": 3})
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
            self.assertIn("x2 (from threat), x3 (for whom)", r.stdout)
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
