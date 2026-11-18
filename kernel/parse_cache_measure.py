"""parse_cache_measure -- full / snapshot / snapshot+cache on a real database.

Co-authored. Not run by CI: the database (set.mm) is not in this repository.

  python3 -m kernel.parse_cache_measure path/to/set.mm [--repeats 3]

  write      one run writing snapshots and parse caches at 25 / 50 / 75 %
  timed      full; from each snapshot without the cache; with it (spot 25, seed 0).
             Wall-clock per run, median of `repeats`; the 1-minute load average is
             read before every run and reported beside the times
  identical  per statement: verdict and rests_on_non_pass, each snapshot run
             against the full run, at all three cut points
  mismatch   the cache file edited by one byte (its sha256 then differs from the
             one the snapshot records), and an intact cache rekeyed to another
             kernel version with its new sha256 recorded: both must be refused,
             logged, and the prefix parsed in full
"""
import json
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

from .mm import run_file
from . import snapshot as snap


def _load():
    return round(os.getloadavg()[0], 2)


def _v(rep):
    return {r["label"]: (r["verdict"], tuple(r["rests_on_non_pass"]))
            for r in rep["theorem_records"]}


def _timed(fn, repeats):
    ts, loads, rep = [], [], None
    for _ in range(repeats):
        loads.append(_load())
        t0 = time.perf_counter()
        rep = fn()
        ts.append(round(time.perf_counter() - t0, 2))
    return {"median": statistics.median(ts), "seconds": ts, "load_1min_before": loads}, rep


def measure(path, repeats=3):
    path = Path(path)
    out = {"input": path.name, "repeats": repeats, "cpus": os.cpu_count(),
           "human_interest": None, "ai_interest": None}
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        t0 = time.perf_counter()
        written, refused, _ = snap.write(path, fractions=[0.25, 0.5, 0.75],
                                         store=d / "s.json", spot=0, seed=0, cache_dir=d)
        out["write_seconds"] = round(time.perf_counter() - t0, 2)
        out["write_refused"] = refused
        full_t, full = _timed(lambda: run_file(path)[0], repeats)
        fv = _v(full)
        out["full"] = full_t
        rows = []
        for rec in written:
            s_t, s_rep = _timed(lambda: run_file(path, snapshot=rec, spot=25, seed=0)[0],
                                repeats)
            c_t, c_rep = _timed(lambda: run_file(path, snapshot=rec, spot=25, seed=0,
                                                 cache_dir=d)[0], repeats)
            rows.append({
                "theorem": rec["theorem"], "index": rec["theorem_index"],
                "cache_bytes": rec["parse_cache"]["bytes"],
                "cache_sha256": rec["parse_cache"]["sha256"],
                "snapshot": s_t, "snapshot_cache": c_t,
                "cache_used": c_rep["parse_cache"]["used"],
                "cache_load_seconds": c_rep["parse_cache"]["load_seconds"],
                "identical_snapshot": _v(s_rep) == fv,
                "identical_snapshot_cache": _v(c_rep) == fv,
                "statements": len(fv)})
        out["cuts"] = rows
        rec = written[-1]
        cf = d / rec["parse_cache"]["file"]
        data = bytearray(cf.read_bytes())
        data[len(data) // 2] ^= 1
        cf.write_bytes(bytes(data))
        r1 = run_file(path, snapshot=rec, spot=25, seed=0, cache_dir=d)[0]
        import hashlib
        import marshal
        good = written[1]                       # an intact cache, rekeyed
        blob = marshal.loads((d / good["parse_cache"]["file"]).read_bytes())
        blob["key"] = [blob["key"][0], "kernel other"]
        raw = marshal.dumps(blob, 4)
        (d / "rekeyed.cache").write_bytes(raw)
        other = dict(good, parse_cache={"file": "rekeyed.cache",
                                        "sha256": hashlib.sha256(raw).hexdigest()})
        r2 = run_file(path, snapshot=other, spot=25, seed=0, cache_dir=d)[0]
        out["mismatch"] = {
            "edited_byte": {"used": r1["parse_cache"]["used"],
                            "reason": r1["parse_cache"]["reason"],
                            "identical": _v(r1) == fv},
            "cache_keyed_to_other_kernel": {"used": r2["parse_cache"]["used"],
                                            "reason": r2["parse_cache"]["reason"],
                                            "identical": _v(r2) == fv}}
    return out


def main(argv):
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2
    reps = int(argv[argv.index("--repeats") + 1]) if "--repeats" in argv else 3
    print(json.dumps(measure(argv[0], reps), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
