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
        # recorded, not repaired: the table is PROPOSED and changing a word's slots is
        # the holder's decision
        slots = {w: len(e["slots"]) for w, e in TABLE.items()}
        self.assertEqual((slots["safe"], BY["safe"]["gismu"]), (3, "snura"))       # snura: 2
        self.assertIn("from threat x2", BY["safe"]["place_structure_verbatim"])
        self.assertEqual((slots["hostile"], BY["hostile"]["gismu"]), (3, "le'onmo"))  # 2 places
        self.assertEqual((TABLE["better"]["shape"], BY["better"]["gismu"]), ("xamgu", "xagmau"))
        self.assertIn("better than z2", BY["better"]["place_structure_verbatim"])
        self.assertEqual((TABLE["appropriate"]["shape"], BY["appropriate"]["gismu"]),
                         ("xamgu", "mapti"))
        self.assertEqual((TABLE["efficient"]["shape"], BY["efficient"]["gismu"]),
                         ("zmadu", None))                                          # no valsi
        self.assertEqual((TABLE["warm"]["shape"], BY["warm"]["gismu"]), ("glare", "xendo"))
        # where they agree
        for w, g in (("more", "zmadu"), ("less", "mleca"), ("near", "jibni")):
            self.assertEqual(BY[w]["gismu"], g)
        self.assertEqual((slots["more"], slots["less"], slots["near"]), (4, 4, 3))


if __name__ == "__main__":
    unittest.main()
