"""snapshot_round2 -- spot checks on load, forgery catch rates, and a profile.

Co-authored. Not run by CI: the database (set.mm) is not in this repository.

  python3 -m kernel.snapshot_round2 path/to/set.mm [--loads 200] [--k 25] [--json]

  forged snapshot   an uncited theorem's statement negated (|- X -> |- -. X) and a
                    snapshot at it forged with the mutated prefix's hash; one load
                    -> must be VOID (the snapshot theorem is always re-verified)
  forged prefix     the same edit on an uncited theorem inside the prefix of an
                    honest snapshot, whose hash is then forged; `loads` loads with
                    seeds 0 .. loads-1 and spot k; each load reads only the prefix
                    (--until the snapshot theorem). Caught = VOID naming it.
                    Expected rate k / (index - 1). Two cut points: index 101, 1001.
  profile           full run and a run from a 75 % snapshot (spot k, seed 0), from
                    lines already in memory: read (file -> lines), hash (sha256 of
                    the lines the run hashes: none for a full check, the prefix
                    for a snapshot load), parse (reading and statement handling,
                    everything but proof checking), verify (proof checking).
"""
import hashlib
import json
import math
import re
import sys
import tempfile
import time
from pathlib import Path

from .mm import Database, make_carry, prefix_sha256, run_file
from . import snapshot as snap

TURNSTILE = re.compile(r"\$p\s+\|-\s")


def _lines(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(f)


def _mutate(lines, rec_line):
    """Negate the statement: "$p |- X" -> "$p |- -. X" on the theorem's $p line.
    -. is declared at the top of set.mm, so the file stays readable and only the
    statement changes. (A first version swapped "->" for "<->", which is not yet
    declared early in set.mm: the file went VOID instead of the theorem FAILing.)"""
    j = rec_line - 1
    m = TURNSTILE.search(lines[j])
    if m is None:
        return None, None
    out = list(lines)
    out[j] = lines[j][:m.end()] + "-. " + lines[j][m.end():]
    return out, j + 1


def _negated(stmt):
    st = list(stmt)
    return " ".join(st[:1] + ["-."] + st[1:])


def _pick(path, lines, cands, store_dir, name):
    """First candidate whose negation reads FAIL in a full check up to it, with no
    file-level VOID."""
    for r in cands:
        mut, line = _mutate(lines, r["line"])
        if mut is None:
            continue
        p = store_dir / name
        p.write_text("".join(mut), encoding="utf-8", newline="")
        rep = run_file(p, until=r["label"])[0]
        last = rep["theorem_records"][-1] if rep["theorem_records"] else None
        if rep["file_void"] is None and last and last["label"] == r["label"] \
                and last["verdict"] == "FAIL":
            return r, p, line
    raise RuntimeError("no candidate")


def _uncited(db):
    cited = set()
    for u in db.used_of.values():
        cited |= u
    return [r for r in db.theorems if r["label"] not in cited
            and db.assertions[r["label"]].stmt[0] == "|-"]


def forged_prefix(path, lines, fdb, store_dir, at_index, k, loads):
    labels = [r["label"] for r in fdb.theorems]
    snap_label = labels[at_index - 1]
    good, _, _ = snap.write(path, [snap_label], store=store_dir / f"g{at_index}.json",
                            spot=0, seed=0)
    rec = good[0]
    cand = [r for r in _uncited(fdb) if r["label"] != snap_label
            and labels.index(r["label"]) < at_index - 1]
    mid = len(cand) // 2
    victim, p, line = _pick(path, lines, cand[mid:] + cand[:mid], store_dir,
                            f"prefix{at_index}.mm")
    own = run_file(p, until=victim["label"])[0]["theorem_records"][-1]
    forged = dict(rec, prefix_sha256=prefix_sha256(p, rec["prefix_lines"]))
    caught, wrong_name = 0, 0
    t0 = time.perf_counter()
    for seed in range(loads):
        rep, _ = run_file(p, snapshot=forged, spot=k, seed=seed, until=snap_label)
        if rep["snapshot"]["state"] == "VOID":
            caught += 1
            if f"{victim['label']} (position" not in rep["file_void"]["reason"]:
                wrong_name += 1
    pool = at_index - 1
    expect = min(k, pool) / pool
    rate = caught / loads
    return {"snapshot": snap_label, "index": at_index, "pool": pool, "k": k,
            "victim": victim["label"], "victim_line_edited": line,
            "victim_full_check": own["verdict"], "loads": loads, "seeds": f"0..{loads - 1}",
            "caught": caught, "rate": round(rate, 4), "expected": round(expect, 4),
            "binomial_sd": round(math.sqrt(expect * (1 - expect) / loads), 4),
            "caught_naming_another": wrong_name,
            "seconds_all_loads": round(time.perf_counter() - t0, 2)}


def forged_snapshot(path, lines, fdb, store_dir):
    labels = [r["label"] for r in fdb.theorems]
    unc = _uncited(fdb)
    mid = len(unc) // 2
    victim, p, line = _pick(path, lines, unc[mid:] + unc[:mid], store_dir, "fsnap.mm")
    idx = labels.index(victim["label"]) + 1
    good, _, _ = snap.write(path, [victim["label"]], store=store_dir / "fs.json",
                            spot=0, seed=0)
    rec = good[0]
    forged = dict(rec, statement=_negated(fdb.assertions[victim["label"]].stmt),
                  prefix_sha256=prefix_sha256(p, rec["prefix_lines"]))
    rep, _ = run_file(p, snapshot=forged, spot=25, seed=0)
    return {"snapshot": victim["label"], "index": idx, "cited_by": 0,
            "line_edited": line, "state": rep["snapshot"]["state"],
            "reason": rep["file_void"]["reason"] if rep["file_void"] else None,
            "verified_here": rep["verified_here"]}


def profile(path, rec=None, k=25):
    t0 = time.perf_counter()
    lines = _lines(path)
    t_read = time.perf_counter() - t0
    t_hash = 0.0
    db = Database()
    if rec is not None:
        t0 = time.perf_counter()
        h = hashlib.sha256()
        for ln in lines[:rec["prefix_lines"]]:
            h.update(ln.encode("utf-8"))
        ok = h.hexdigest() == rec["prefix_sha256"]
        t_hash = time.perf_counter() - t0
        assert ok
        db.carry = make_carry(rec, k, 0)
    t0 = time.perf_counter()
    db.read(lines)
    t_loop = time.perf_counter() - t0
    rep = db.report(str(path), t_loop)
    return {"read": round(t_read, 2), "hash": round(t_hash, 2),
            "parse": round(t_loop - db.t_verify, 2), "verify": round(db.t_verify, 2),
            "total": round(t_read + t_hash + t_loop, 2),
            "counts": rep["counts"], "verified_here": rep["verified_here"],
            "carried": rep["carried_from_snapshot"]}


def main(argv):
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2
    loads = int(argv[argv.index("--loads") + 1]) if "--loads" in argv else 200
    k = int(argv[argv.index("--k") + 1]) if "--k" in argv else 25
    path = Path(argv[0])
    lines = _lines(path)
    _, fdb = run_file(path)
    out = {"input": path.name, "input_sha256": prefix_sha256(path, len(lines)),
           "k": k, "human_interest": None, "ai_interest": None}
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        out["forged_snapshot"] = forged_snapshot(path, lines, fdb, d)
        out["forged_prefix"] = [forged_prefix(path, lines, fdb, d, i, k, loads)
                                for i in (101, 1001)]
        n = len(fdb.theorems)
        w75, _, _ = snap.write(path, fractions=[0.75], store=d / "p75.json", spot=0, seed=0)
        out["profile"] = {"full": [profile(path) for _ in range(3)],
                          "from_75": [profile(path, w75[0], k) for _ in range(3)],
                          "snapshot_75": {"theorem": w75[0]["theorem"],
                                          "index": w75[0]["theorem_index"], "of": n}}
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
