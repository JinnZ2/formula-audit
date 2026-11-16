"""The relayed Lojban reference, and the place table set beside it. Co-authored.

The reference was pasted in by the repository owner; this build could not
reach lojban.org and re-read nothing. These tests check the file's shape and
record where the shipped place table differs from it. They do not check Lojban.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

REF = json.loads((ROOT / "REFERENCES" / "lojban_place_structures.json").read_text())
DATA = REF["data"]
TABLE = json.loads((ROOT / "wordslots" / "places.json").read_text())["words"]
BY = {p["english"]: p for p in DATA["place_structures"]}


class TestReference(unittest.TestCase):
    def test_shape(self):
        self.assertFalse(REF["re_read_in_this_build"])
        self.assertEqual((len(DATA["place_structures"]), len(DATA["evidentials"])), (30, 11))
        for p in DATA["place_structures"] + DATA["evidentials"]:
            self.assertEqual(p["retrieved"], "2026-11-17")
            self.assertTrue(p["source_url"].startswith("https://"))
            if p["structure_status"] == "VOID":           # a gap stays a gap
                self.assertIsNone(p["gismu"])
                self.assertIsNone(p["place_structure_verbatim"])
                self.assertEqual(p["mapping_status"], "VOID")
            else:
                self.assertEqual(p["structure_status"], "OBSERVED")
                self.assertTrue(p["place_structure_verbatim"])
        self.assertEqual(sorted(p["english"] for p in DATA["place_structures"]
                                if p["structure_status"] == "VOID"),
                         ["cold", "efficient", "imminent"])

    def test_recall_checks(self):
        checks = [p for p in DATA["place_structures"] if p["class"] == "recall_check"]
        self.assertEqual(sorted(p["gismu"] for p in checks),
                         ["glare", "jibni", "snura", "xamgu", "zmadu"])
        for p in checks:                                  # worded differently, same places
            self.assertEqual(p["mapping_status"], "DIFFERS")
            self.assertIn("same place count", p["mapping_reason"])

    def test_evidentials_used_by_wordslots_are_in_the_reference(self):
        from wordslots.check import EVIDENTIAL
        cmavo = {e["gismu"] for e in DATA["evidentials"]}
        for used in ("se'o", "ja'o", "ka'u"):
            self.assertIn(used, EVIDENTIAL)
            self.assertIn(used, cmavo)
        self.assertEqual({e["gismu"] for e in DATA["evidentials"] if not e["in_user_list"]},
                         {"ba'a", "su'a"})

    def test_where_the_place_table_differs_from_the_reference(self):
        # the table was realigned to the reference; what still differs stays here as a
        # record. The table is PROPOSED either way: the holder has confirmed nothing.
        slots = {w: len(e["slots"]) for w, e in TABLE.items()}
        # KEPT by the union rule: safe keeps "for whom", which snura does not have
        self.assertEqual((slots["safe"], BY["safe"]["gismu"]), (3, "snura"))       # snura: 2
        self.assertIn("from threat x2", BY["safe"]["place_structure_verbatim"])
        self.assertEqual(TABLE["safe"]["slots"][2]["role"], "for whom")
        self.assertEqual(TABLE["safe"]["slots"][2]["source_predicate"], "ckape")
        self.assertIn("harmful to x2", BY["dangerous"]["place_structure_verbatim"])
        # KEPT: efficient has no Lojban word in the reference, and the table says so
        self.assertEqual((TABLE["efficient"]["shape"], BY["efficient"]["gismu"]), (None, None))
        self.assertEqual((TABLE["efficient"]["lojban"], BY["efficient"]["structure_status"]),
                         ("VOID", "VOID"))
        # KEPT: warm's shape is still glare; the reference's xendo is its SOCIAL sense
        self.assertEqual((TABLE["warm"]["shape"], BY["warm"]["gismu"]), ("glare", "xendo"))
        self.assertEqual(TABLE["warm"]["senses"], {"PHYSICAL": "glare", "SOCIAL": "xendo"})

    def test_where_the_place_table_now_agrees_with_the_reference(self):
        slots = {w: len(e["slots"]) for w, e in TABLE.items()}
        self.assertEqual((slots["hostile"], TABLE["hostile"]["shape"]), (2, BY["hostile"]["gismu"]))
        self.assertEqual(TABLE["better"]["shape"], BY["better"]["gismu"])          # xagmau
        self.assertEqual([s["role"] for s in TABLE["better"]["slots"]],
                         ["what is better", "than what", "for whom", "by what standard",
                          "by what amount"])
        self.assertIn("better than z2 for xa2 by standard xa3, by amount z4",
                      BY["better"]["place_structure_verbatim"])
        self.assertEqual((TABLE["appropriate"]["shape"], slots["appropriate"]),
                         (BY["appropriate"]["gismu"], 3))                          # mapti
        for w, g in (("more", "zmadu"), ("less", "mleca"), ("near", "jibni")):
            self.assertEqual((BY[w]["gismu"], TABLE[w]["shape"]), (g, g))
        self.assertEqual((slots["more"], slots["less"], slots["near"]), (4, 4, 3))
        self.assertEqual(slots["warm"], 4)            # glare's 2 places + xendo's x2, x3

    def test_every_source_predicate_is_in_the_reference_or_physics_def(self):
        known = {p["gismu"] for p in DATA["place_structures"]
                 if p["structure_status"] == "OBSERVED"}
        for w, e in TABLE.items():
            for s in e["slots"]:
                self.assertTrue(s["source_predicate"] in known
                                or s["source_predicate"] == "physics_def", (w, s["name"]))
            for g in (e.get("senses") or {}).values():
                self.assertIn(g, known, w)

    def test_new_evidentials_follow_the_reference_scale(self):
        from wordslots.check import EVIDENTIAL, SELF_EVIDENTIALS
        baa = next(e for e in DATA["evidentials"] if e["gismu"] == "ba'a")
        for form in ("ba'acu'i", "ba'anai"):                       # the scale is quoted there
            self.assertIn(form, baa["place_structure_verbatim"])
        self.assertEqual({k: EVIDENTIAL[k] for k in ("ba'a", "ba'acu'i", "ba'anai", "su'a")},
                         {"ba'a": "PROPOSED", "ba'acu'i": "OBSERVED", "ba'anai": "OBSERVED",
                          "su'a": "PROPOSED"})
        self.assertEqual(SELF_EVIDENTIALS, ("se'o", "ba'acu'i"))

if __name__ == "__main__":
    unittest.main()
