"""Tests for kernel snapshots (branch 2a). Co-authored. Hand-written databases."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from kernel import prefix_sha256, run_file  # noqa: E402
from kernel import snapshot as snap  # noqa: E402
from kernel.mm import VERSION  # noqa: E402

PROP = (ROOT / "tests" / "data" / "prop.mm").read_text()
# one more theorem after idd, citing idd
EXTRA = PROP + "\nidd2 $p |- ( R -> ( Q -> ( P -> P ) ) ) $= wq wp wp wi wi wr wp wq idd a1i $.\n"


def verdicts(rep):
    return {r["label"]: (r["verdict"], tuple(r["rests_on_non_pass"]))
            for r in rep["theorem_records"]}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.store = self.d / "snapshots.json"

    def tearDown(self):
        self.tmp.cleanup()

    def db(self, text, name="x.mm"):
        p = self.d / name
        p.write_text(text)
        return p

    def snapshot_at(self, path, label):
        written, refused, _ = snap.write(path, [label], store=self.store)
        return written, refused

    def stored(self, label=None):
        rec, why = snap.select(snap.load(self.store), label)
        self.assertIsNone(why)
        return rec


class TestWrite(Base):
    def test_record_fields(self):
        p = self.db(EXTRA)
        written, refused = self.snapshot_at(p, "idc")
        self.assertEqual(refused, [])
        r = self.stored("idc")
        self.assertEqual(r["statement"], "|- ( P -> P )")
        self.assertEqual(r["axioms_used"], ["ax-1", "ax-2", "mp", "wi"])
        self.assertEqual(r["kernel_version"], VERSION)
        self.assertEqual((r["verdict"], r["status"], r["theorem_index"]), ("PASS", "DERIVED", 2))
        self.assertEqual(r["prefix_sha256"], prefix_sha256(p, r["prefix_lines"]))
        self.assertIsNone(r["human_interest"])
        self.assertIsNone(r["ai_interest"])

    def test_axioms_used_is_transitive(self):
        p = self.db(EXTRA)
        self.snapshot_at(p, "idd")
        # idd cites id and a1i only; their axioms come through them
        self.assertEqual(self.stored("idd")["axioms_used"], ["ax-1", "ax-2", "mp", "wi"])

    def test_refused_unless_pass(self):
        bad = EXTRA.replace("  wp wp ax-1\n", "  wp wq ax-1\n", 1)       # id FAILs
        p = self.db(bad)
        written, refused = self.snapshot_at(p, "id")
        self.assertEqual(written, [])
        self.assertIn("verdict FAIL", refused[0])
        self.assertFalse(self.store.exists())                          # nothing written
        self.assertIn("not read", self.snapshot_at(p, "nosuch")[1][0])
        void = self.db(EXTRA.replace("mp mp $.", "mp ? $."), "v.mm")    # id VOID
        self.assertIn("verdict VOID", self.snapshot_at(void, "id")[1][0])
        fv = self.db(EXTRA.replace("idd $p", "$x idd $p"), "f.mm")      # file VOID before idd
        self.assertIn("not read", self.snapshot_at(fv, "idd")[1][0])

    def test_rests_on_non_pass_is_carried(self):
        # 4: idd PASSes while citing id, which FAILs -> the snapshot says so
        bad = EXTRA.replace("  wp wp ax-1\n", "  wp wq ax-1\n", 1)
        p = self.db(bad)
        written, refused = self.snapshot_at(p, "idd")
        self.assertEqual(refused, [])
        r = self.stored("idd")
        self.assertEqual(r["rests_on_non_pass"], ["id"])
        self.assertEqual(r["prefix_non_pass"]["id"]["verdict"], "FAIL")
        self.assertEqual(r["prefix_counts"], {"PASS": 3, "FAIL": 1, "VOID": 0})
        rep, _ = run_file(p, snapshot=r, spot=0)
        t = {x["label"]: x for x in rep["theorem_records"]}
        self.assertEqual(t["id"]["verdict"], "FAIL")                    # kept, not promoted
        self.assertFalse(t["id"]["verified_here"])
        self.assertEqual(t["id"]["located_error"]["step"], 40)          # reason carried too
        self.assertEqual(t["idd"]["rests_on_non_pass"], ["id"])
        self.assertEqual(verdicts(rep), verdicts(run_file(p)[0]))
        # sampled, id re-verifies FAIL as carried: no mismatch, run stands
        rep, _ = run_file(p, snapshot=r, spot=3, seed=0)
        self.assertEqual(rep["snapshot"]["state"], "MATCHED")
        self.assertIn({"index": 1, "label": "id", "role": "spot", "verdict": "FAIL",
                       "carried": "FAIL"}, rep["snapshot"]["spot"]["checked"])


class TestFromSnapshot(Base):
    def test_only_after_is_verified_and_verdicts_identical(self):
        p = self.db(EXTRA)
        for label in ("id", "idc", "a1i", "idd"):
            self.snapshot_at(p, label)
        full = run_file(p)[0]
        for label, n in (("id", 1), ("idc", 2), ("a1i", 3), ("idd", 4)):
            rep, _ = run_file(p, snapshot=self.stored(label), spot=0)
            self.assertEqual(rep["snapshot"]["state"], "MATCHED")
            # the snapshot theorem is always re-verified; spot 0 adds none
            self.assertEqual((rep["carried_from_snapshot"], rep["verified_here"]),
                             (n - 1, 6 - n))
            self.assertEqual(verdicts(rep), verdicts(full), label)
            for r in rep["theorem_records"][:n - 1]:
                self.assertFalse(r["verified_here"])
                self.assertEqual(r["carried_from_snapshot"], label)
            self.assertEqual(rep["theorem_records"][n - 1]["rechecked_for_snapshot"],
                             "snapshot theorem")

    def test_edit_after_the_prefix_is_still_checked(self):
        p = self.db(EXTRA)
        self.snapshot_at(p, "idd")
        p.write_text(EXTRA.replace("wq idd a1i $.", "wr idd a1i $."))
        rep, _ = run_file(p, snapshot=self.stored("idd"))
        self.assertEqual(rep["snapshot"]["state"], "MATCHED")
        self.assertEqual(rep["theorem_records"][-1]["verdict"], "FAIL")

    def test_stale_hash_is_void(self):
        # 6a: the prefix was edited after the snapshot was written
        p = self.db(EXTRA)
        self.snapshot_at(p, "idd")
        for edit in (EXTRA.replace("  wp wp ax-1\n", "  wp wq ax-1\n", 1),   # a proof
                     EXTRA.replace("Implication only", "Implication alone"),  # a comment
                     EXTRA.replace("\n", "\r\n")):                            # line endings
            p.write_text(edit, newline="")
            rep, _ = run_file(p, snapshot=self.stored("idd"))
            self.assertEqual(rep["snapshot"]["state"], "VOID")
            self.assertIn("do not hash", rep["file_void"]["reason"])
            self.assertEqual(rep["theorem_records"], [])                 # nothing verified
            self.assertEqual(rep["provable_statements"], 0)

    def test_short_file_and_kernel_version_are_void(self):
        p = self.db(EXTRA)
        self.snapshot_at(p, "idd")
        r = self.stored("idd")
        p.write_text("$c a $.\n")
        self.assertEqual(run_file(p, snapshot=r)[0]["snapshot"]["state"], "VOID")
        p.write_text(EXTRA)
        other = dict(r, kernel_version="kernel other")
        rep, _ = run_file(p, snapshot=other)
        self.assertEqual(rep["snapshot"]["state"], "VOID")
        self.assertIn("kernel version", rep["file_void"]["reason"])
        notpass = dict(r, verdict="FAIL")
        self.assertEqual(run_file(p, snapshot=notpass)[0]["snapshot"]["state"], "VOID")

    def test_statement_not_where_the_snapshot_says_is_void(self):
        p = self.db(EXTRA)
        self.snapshot_at(p, "idd")
        r = dict(self.stored("idd"), theorem_index=3)       # hash matches, position does not
        rep, _ = run_file(p, snapshot=r)
        self.assertIsNotNone(rep["file_void"])
        self.assertTrue(all(x["verdict"] == "VOID" for x in rep["theorem_records"]
                            if not x["verified_here"]))

    def test_forged_snapshot_of_a_mutated_theorem_is_void_on_load(self):
        # round 2, 1a: the snapshot theorem itself is re-verified on every load
        mut = EXTRA.replace("id $p |- ( P -> P ) $=", "id $p |- ( Q -> P ) $=")
        p = self.db(mut)
        self.db(EXTRA, "good.mm")
        snap.write(self.d / "good.mm", ["id"], store=self.store)
        good = self.stored("id")
        forged = dict(good, statement="|- ( Q -> P )",
                      prefix_sha256=prefix_sha256(p, good["prefix_lines"]))
        rep, _ = run_file(p, snapshot=forged, spot=0)
        self.assertEqual(rep["snapshot"]["state"], "VOID")
        self.assertIn("id (position 1, snapshot theorem) re-verified FAIL",
                      rep["file_void"]["reason"])
        self.assertTrue(all(x["verdict"] != "PASS" for x in rep["theorem_records"]))

    def test_forged_prefix_theorem_not_sampled_fails_downstream(self):
        # 6b: id's statement changed; the honest writer refuses it, so a snapshot at
        # a1i is forged by hand with the mutated prefix's hash. With no spot check
        # id is carried as PASS (the store cannot tell), and idd, which cites id,
        # FAILs.
        mut = EXTRA.replace("id $p |- ( P -> P ) $=", "id $p |- ( Q -> P ) $=")
        p = self.db(mut)
        written, refused = self.snapshot_at(p, "id")
        self.assertEqual(written, [])
        self.assertIn("verdict FAIL", refused[0])
        self.assertEqual(run_file(p)[0]["theorem_records"][0]["verdict"], "FAIL")
        self.db(EXTRA, "good.mm")
        snap.write(self.d / "good.mm", ["a1i"], store=self.store)
        good = self.stored("a1i")
        forged = dict(good, prefix_sha256=prefix_sha256(p, good["prefix_lines"]))
        rep, _ = run_file(p, snapshot=forged, spot=0)
        t = {x["label"]: x for x in rep["theorem_records"]}
        self.assertEqual(rep["snapshot"]["state"], "MATCHED")
        self.assertEqual((t["id"]["verdict"], t["id"]["verified_here"]), ("PASS", False))
        self.assertEqual(t["idd"]["verdict"], "FAIL")                 # downstream
        self.assertTrue(t["idd"]["verified_here"])
        self.assertEqual(t["idc"]["verdict"], "PASS")                 # does not cite id


HEAD = PROP.split("$( P -> P, in five lines")[0]
IDC = "( wi ax-1 ax-2 mp ) AAABZBFAACAFABBAFBFBAFCAFADEE"


def many(n, bad=None):
    """n copies of the compressed P -> P proof; copy `bad` has a wrong statement.
    Nothing cites any of them."""
    out = [HEAD]
    for i in range(1, n + 1):
        stmt = "|- ( P -> Q )" if i == bad else "|- ( P -> P )"
        out.append(f"t{i} $p {stmt} $= {IDC} $.\n")
    return "".join(out)


class TestSpotCheck(Base):
    def forged(self, n, bad, at):
        good = self.db(many(n), "good.mm")
        snap.write(good, [f"t{at}"], store=self.store)
        rec = self.stored(f"t{at}")
        p = self.db(many(n, bad), "bad.mm")
        return p, dict(rec, prefix_sha256=prefix_sha256(p, rec["prefix_lines"]))

    def test_sample_and_seed_are_recorded(self):
        p = self.db(many(30))
        snap.write(p, ["t20"], store=self.store)
        rep, _ = run_file(p, snapshot=self.stored("t20"), spot=5, seed=7)
        sp = rep["snapshot"]["spot"]
        self.assertEqual((sp["k"], sp["seed"], sp["pool"]), (5, 7, 19))
        self.assertEqual(len(sp["sample_positions"]), 5)
        self.assertEqual(len(sp["checked"]), 6)                       # 5 spot + the theorem
        self.assertEqual(sp["checked"][-1]["role"], "snapshot theorem")
        self.assertEqual(rep["carried_from_snapshot"], 14)
        again, _ = run_file(p, snapshot=self.stored("t20"), spot=5, seed=7)
        self.assertEqual(again["snapshot"]["spot"]["sample_positions"],
                         sp["sample_positions"])                       # seed reproduces
        fresh, _ = run_file(p, snapshot=self.stored("t20"), spot=5)
        self.assertIsInstance(fresh["snapshot"]["spot"]["seed"], int)  # drawn, logged
        big, _ = run_file(p, snapshot=self.stored("t20"), spot=99, seed=0)
        self.assertEqual(big["carried_from_snapshot"], 0)              # k > pool: all

    def test_forged_uncited_prefix_theorem_caught_at_about_k_over_pool(self):
        # t13 is wrong and cited by nothing; a snapshot at t41 is forged over it.
        p, forged = self.forged(41, 13, 41)
        k, pool, loads = 5, 40, 200
        caught = 0
        for seed in range(loads):
            rep, _ = run_file(p, snapshot=forged, spot=k, seed=seed)
            if rep["snapshot"]["state"] == "VOID":
                caught += 1
                self.assertIn("t13 (position 13, spot) re-verified FAIL",
                              rep["file_void"]["reason"])
            else:
                self.assertEqual({x["label"]: x["verdict"] for x in rep["theorem_records"]}
                                 ["t13"], "PASS")                    # missed: carried
        rate = caught / loads
        self.assertAlmostEqual(rate, k / pool, delta=0.07)           # 0.125 expected
        self.assertEqual(caught, 32)                    # seeds 0..199, pinned: 0.160 (sd 0.023)

    def test_spot_zero_misses_it(self):
        p, forged = self.forged(41, 13, 41)
        rep, _ = run_file(p, snapshot=forged, spot=0, seed=0)
        self.assertEqual(rep["snapshot"]["state"], "MATCHED")


class TestStoreAndCli(Base):
    def cli(self, *args):
        return subprocess.run([sys.executable, "-m", "kernel", *args], cwd=ROOT,
                              capture_output=True, text=True)

    def test_store_replaces_same_theorem_and_hash(self):
        p = self.db(EXTRA)
        self.snapshot_at(p, "idc")
        self.snapshot_at(p, "idc")
        self.snapshot_at(p, "idd")
        data = json.loads(self.store.read_text())
        self.assertEqual(data["schema"], "kernel-snapshot-store/1")
        self.assertEqual([s["theorem"] for s in data["snapshots"]], ["idc", "idd"])
        self.assertIn("name one", snap.select(data)[1])

    def test_fraction_targets(self):
        p = self.db(EXTRA)
        written, refused, _ = snap.write(p, fractions=[0.25, 0.5, 0.75], store=self.store)
        self.assertEqual([r["theorem"] for r in written], ["id", "idc", "idd"])   # of 5: round(1.25, 2.5, 3.75) = 1, 2, 4

    def test_exit_codes(self):
        p = self.db(EXTRA)
        st = str(self.store)
        self.assertEqual(self.cli("snapshot", str(p), "--at", "idc", "--store", st).returncode, 0)
        self.assertEqual(self.cli("snapshot", str(p), "--store", st).returncode, 2)
        bad = self.db(EXTRA.replace("  wp wp ax-1\n", "  wp wq ax-1\n", 1), "b.mm")
        self.assertEqual(self.cli("snapshot", str(bad), "--at", "id", "--store", st).returncode, 1)
        r = self.cli("check", str(p), "--from-snapshot", st, "--snap", "idc")
        self.assertEqual(r.returncode, 0)
        self.assertIn("snapshot idc: MATCHED", r.stdout)
        p.write_text(EXTRA.replace("Implication only", "Implication alone"))
        r = self.cli("check", str(p), "--from-snapshot", st, "--snap", "idc")
        self.assertEqual(r.returncode, 3)
        self.assertIn("VOID", r.stdout)
        self.assertEqual(self.cli("check", str(p), "--from-snapshot", st, "--snap", "x")
                         .returncode, 2)
        m = self.db(many(30), "m.mm")
        self.cli("snapshot", str(m), "--at", "t20", "--store", st)
        r = self.cli("check", str(m), "--from-snapshot", st, "--snap", "t20", "--spot", "4",
                     "--seed", "11")
        self.assertEqual(r.returncode, 0)
        self.assertIn("spot k 4, seed 11", r.stdout)
        m.write_text(many(30, 20))                     # the snapshot theorem itself wrong
        rec = snap.select(snap.load(st), "t20")[0]
        rec["prefix_sha256"] = prefix_sha256(m, rec["prefix_lines"])
        rec["statement"] = "|- ( P -> Q )"
        snap.add(st, [rec])
        r = self.cli("check", str(m), "--from-snapshot", st, "--snap", "t20")
        self.assertEqual(r.returncode, 2)              # two records for t20: name one
        bad = self.d / "forged.json"
        bad.write_text(json.dumps({"schema": "kernel-snapshot-store/1", "snapshots": [rec]}))
        r = self.cli("check", str(m), "--from-snapshot", str(bad))
        self.assertEqual(r.returncode, 3)              # VOID, though the re-check FAILed
        self.assertIn("t20 (position 20, snapshot theorem) re-verified FAIL", r.stdout)


if __name__ == "__main__":
    unittest.main()


class TestParseCache(Base):
    def setUp(self):
        super().setUp()
        self.p = self.db(many(30))
        written, _, _ = snap.write(self.p, ["t20"], store=self.store, cache_dir=self.d)
        self.rec = written[0]

    def V(self, rep):
        return {r["label"]: (r["verdict"], tuple(r["rests_on_non_pass"]), r["verified_here"])
                for r in rep["theorem_records"]}

    def test_recorded_and_used_with_identical_verdicts(self):
        pc = self.rec["parse_cache"]
        self.assertEqual(pc["key"], [self.rec["prefix_sha256"], VERSION])
        self.assertTrue((self.d / pc["file"]).exists())
        for spot in (0, 4, 25):
            a, _ = run_file(self.p, snapshot=self.rec, spot=spot, seed=3, cache_dir=self.d)
            b, _ = run_file(self.p, snapshot=self.rec, spot=spot, seed=3)
            self.assertTrue(a["parse_cache"]["used"])
            self.assertIsNone(b["parse_cache"])
            self.assertEqual(self.V(a), self.V(b))
            self.assertEqual(a["snapshot"]["spot"]["checked"], b["snapshot"]["spot"]["checked"])

    def mismatch(self, rec):
        a, _ = run_file(self.p, snapshot=rec, spot=4, seed=3, cache_dir=self.d)
        b, _ = run_file(self.p, snapshot=rec, spot=4, seed=3)
        self.assertFalse(a["parse_cache"]["used"])
        self.assertEqual(self.V(a), self.V(b))           # full parse, same verdicts
        return a["parse_cache"]["reason"]

    def test_any_mismatch_means_full_parse(self):
        import hashlib
        import marshal
        f = self.d / self.rec["parse_cache"]["file"]
        self.assertIn("names no parse cache", self.mismatch(dict(self.rec, parse_cache=None)))
        self.assertIn("No such file", self.mismatch(
            dict(self.rec, parse_cache=dict(self.rec["parse_cache"], file="gone.cache"))))
        good = f.read_bytes()
        bad = bytearray(good)
        bad[len(bad) // 2] ^= 1
        f.write_bytes(bytes(bad))
        self.assertIn("sha256 is not the one", self.mismatch(self.rec))
        f.write_bytes(good)
        blob = marshal.loads(good)
        for key, want in (([blob["key"][0], "kernel other"], "key"),
                          (["0" * 64, VERSION], "key")):
            raw = marshal.dumps(dict(blob, key=key), 4)
            (self.d / "x.cache").write_bytes(raw)
            rec = dict(self.rec, parse_cache={"file": "x.cache",
                                              "sha256": hashlib.sha256(raw).hexdigest()})
            self.assertIn(want, self.mismatch(rec))
        raw = b"not marshal"
        (self.d / "y.cache").write_bytes(raw)
        rec = dict(self.rec, parse_cache={"file": "y.cache",
                                          "sha256": hashlib.sha256(raw).hexdigest()})
        self.assertIn("unreadable", self.mismatch(rec))

    def test_forged_snapshot_theorem_still_void_with_cache(self):
        bad = self.db(many(30, 20), "bad.mm")
        rec = dict(self.rec, statement="|- ( P -> Q )",
                   prefix_sha256=prefix_sha256(bad, self.rec["prefix_lines"]))
        rep, _ = run_file(bad, snapshot=rec, spot=0, cache_dir=self.d)
        self.assertFalse(rep["parse_cache"]["used"])     # cache key is the honest hash
        self.assertEqual(rep["snapshot"]["state"], "VOID")

    def test_statements_after_the_prefix_on_its_last_line(self):
        text = many(5) + "t6 $p |- ( P -> P ) $= " + IDC + " $. t7 $p |- ( P -> P ) $= " \
            + IDC + " $.\n"
        p = self.db(text, "same.mm")
        w, _, _ = snap.write(p, ["t6"], store=self.store, cache_dir=self.d)
        a, _ = run_file(p, snapshot=w[0], spot=0, cache_dir=self.d)
        self.assertTrue(a["parse_cache"]["used"])
        self.assertEqual([r["label"] for r in a["theorem_records"]],
                         ["t1", "t2", "t3", "t4", "t5", "t6", "t7"])
        self.assertTrue(a["theorem_records"][-1]["verified_here"])
