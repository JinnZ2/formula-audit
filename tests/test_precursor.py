"""glyph/precursor.py: its own selftest, and the glyph table entry. Co-authored.

The file was filed verbatim (sha256 d2cdb8d71df9...); one line has changed
since: its docstring's run line now reads "python3 -m glyph.precursor". The
sha256 of the file as it stands is pinned here.
"""
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from glyph import TABLE_V0  # noqa: E402
from glyph.environment import read_event_log  # noqa: E402
from glyph.glyph_operator import candidate_key  # noqa: E402
from glyph.precursor import check  # noqa: E402
from glyph.tools import apply_tool  # noqa: E402
from infer.ladder import Void  # noqa: E402
from tests.test_glyph import Base  # noqa: E402

SHA = "d1eab08effbc5b4b40b24969797763abf99f31b54e630da3dd6117e8f9f5e537"
DEC = {"tau": 3.0, "window": 4, "streak_limit": 3, "trend_limit": 0.5}
FAILS = {"events": [{"t": t, "outcome": o} for t, o in
                    enumerate(["FAIL", "FAIL", "FAIL", "PASS"])], "declare": DEC}


class TestPrecursor(unittest.TestCase):
    def test_file_is_the_delivered_one(self):
        data = (ROOT / "glyph" / "precursor.py").read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), SHA)

    def test_selftest_runs(self):
        p = subprocess.run([sys.executable, "-m", "glyph.precursor", "--selftest"],
                           cwd=ROOT, capture_output=True, text=True)
        self.assertEqual((p.returncode, p.stdout.strip()), (0, "selftest: 10 of 10 passed"))

    def test_table_entry_six(self):
        t = TABLE_V0[5]
        self.assertEqual((len(TABLE_V0), t["name"], t["needs"], t["status"]),
                         (6, "precursor", ["event_log"], "PROPOSED"))
        self.assertEqual(int(t["cost"]), min(int(x["cost"]) for x in TABLE_V0))      # low

    def test_output_is_readings_and_questions(self):
        kind, body = apply_tool("precursor", {"sources": [], "log": FAILS})
        self.assertEqual(kind, "question")
        r = body["reading"]
        self.assertEqual((r["status"], r["claims"]),
                         ("READ", "readings only; no correctness verdict"))
        self.assertEqual(len(body["questions"]), 3)
        self.assertEqual(len(r["relief_after_pass"]), 1)
        self.assertNotIn("verdict", r)
        json.dumps(body)                                    # goes into proposals.json

    def test_missing_declaration_is_a_void_part(self):
        r = check({"events": FAILS["events"]})
        for part in ("carried_state", "precursor", "mode_shift"):
            self.assertEqual(r[part]["status"], "VOID")
        self.assertEqual(r["status"], "READ")               # the rest is still read

    def test_event_log_shape(self):
        self.assertIsNone(read_event_log(None))
        for bad in ([], {"events": "x"}, {"events": [], "declare": 3},
                    {"events": [], "extra": 1}):
            with self.assertRaises(Void):
                read_event_log(bad)
        a = candidate_key("precursor", {"sources": [], "log": FAILS})
        b = candidate_key("precursor", {"sources": [], "log": {"events": FAILS["events"]}})
        self.assertNotEqual(a, b)                           # a changed log: a new candidate


class TestPrecursorStep(Base):
    def test_no_event_log_the_tool_is_closed(self):
        r = self.w.run(self.w.case(tools=[TABLE_V0[5]]))
        o = r["log"][1]["options"][0]
        self.assertEqual((o["open"], o["why_not"], r["log"][1]["chosen"]),
                         (False, "feature not in the environment: event_log", "inaction"))

    def test_one_step_writes_one_question_then_closes(self):
        c = self.w.case(tools=[TABLE_V0[5]], event_log=FAILS)
        r = self.w.run(c, steps=2)
        self.assertEqual([e["chosen"] for e in r["log"][1:]], ["precursor", "inaction"])
        q = self.w.proposals()["questions"][-1]
        self.assertEqual((q["status"], q["glyph"]["tool"], q["reading"]["mode_shift"]["shift"]),
                         ("PROPOSED", "precursor", False))
        self.assertEqual((q["human_interest"], q["ai_interest"]), (None, None))

    def test_a_malformed_event_log_is_void(self):
        r = self.w.run(self.w.case(tools=[TABLE_V0[5]], event_log={"events": "x"}))
        self.assertEqual(r["verdict"], "VOID")


if __name__ == "__main__":
    unittest.main()
