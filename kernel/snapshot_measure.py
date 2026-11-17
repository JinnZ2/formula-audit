"""snapshot_measure -- full run against runs from snapshots, on a real database.

Co-authored. Not run by CI: the database (set.mm) is not in this repository.

  python3 -m kernel.snapshot_measure path/to/set.mm [--repeats 3] [--json]

  full       the kernel on the whole file, `repeats` times (median taken)
  snapshots  one writing run, snapshots at 25 / 50 / 75 % of the provable
             statements (by position); then a run from each, `repeats` times
  identical  per statement: verdict and rests_on_non_pass, full vs from-snapshot;
             any difference is listed
  planted    stale hash: one letter of a proof inside the 50 % prefix changed,
             snapshot not rewritten -> must be VOID with nothing verified
             mutated theorem: the statement just before the 50 % cut that the
             most later statements cite has its first "->" changed to "<->";
             the honest writer must refuse it; a snapshot forged by hand with
             the mutated prefix's hash carries it as PASS, and the statements
             after it that cite it must FAIL
Times are wall-clock on whatever machine runs this; they include re-reading and
hashing the prefix, and parsing it (only proof checking is skipped).
"""
import json
import re
import statistics
import sys
import tempfile
import time
from pathlib import Path

from .mm import prefix_sha256, run_file
from . import snapshot as snap


def _timed(path, rec=None):
    t0 = time.perf_counter()
    rep, db = run_file(path, snapshot=rec)
    return time.perf_counter() - t0, rep, db


def _verdicts(rep):
    return {r["label"]: (r["verdict"], tuple(r["rests_on_non_pass"]))
            for r in rep["theorem_records"]}


def measure(path, repeats=3):
    path = Path(path)
    out = {"input": path.name, "input_sha256": prefix_sha256(path, sum(1 for _ in
                                                                         open(path, newline=""))),
           "repeats": repeats, "human_interest": None, "ai_interest": None}
    times, full = [], None
    for _ in range(repeats):
        t, full, fdb = _timed(path)
        times.append(t)
    out["full"] = {"seconds_median": round(statistics.median(times), 2),
                   "seconds": [round(x, 2) for x in times], "counts": full["counts"],
                   "provable_statements": full["provable_statements"]}
    fv = _verdicts(full)
    with tempfile.TemporaryDirectory() as d:
        store = Path(d) / "snapshots.json"
        t0 = time.perf_counter()
        written, refused, _ = snap.write(path, fractions=[0.25, 0.5, 0.75], store=store)
        out["write_run_seconds"] = round(time.perf_counter() - t0, 2)
        out["write_refused"] = refused
        rows = []
        for rec in written:
            ts, rep = [], None
            for _ in range(repeats):
                t, rep, _db = _timed(path, rec)
                ts.append(t)
            sv = _verdicts(rep)
            diff = sorted(k for k in set(fv) | set(sv) if fv.get(k) != sv.get(k))
            med = statistics.median(ts)
            rows.append({"theorem": rec["theorem"], "theorem_index": rec["theorem_index"],
                         "prefix_lines": rec["prefix_lines"],
                         "prefix_sha256": rec["prefix_sha256"],
                         "axioms_used": len(rec["axioms_used"]),
                         "carried": rep["carried_from_snapshot"],
                         "verified_here": rep["verified_here"],
                         "seconds_median": round(med, 2), "seconds": [round(x, 2) for x in ts],
                         "saved_seconds": round(out["full"]["seconds_median"] - med, 2),
                         "saved_fraction": round(1 - med / out["full"]["seconds_median"], 3),
                         "verdicts_identical": not diff, "differences": diff[:20]})
        out["from_snapshot"] = rows
        out["planted"] = planted(path, fdb, [r for r in written if abs(r["theorem_index"]
                                 - round(len(fdb.theorems) * 0.5)) <= 1][0], Path(d))
    return out


def planted(path, fdb, mid, d):
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    res = {}
    # stale hash: one letter of a compressed proof inside the prefix
    t = fdb.theorems[len(fdb.theorems) // 10]
    i = t["line"] - 1
    while i < mid["prefix_lines"] and not re.search(r"\) [A-Z]", lines[i]) and \
            not re.match(r"\s+[A-Z]{8,}", lines[i]):
        i += 1
    m = re.search(r"[A-Y]", lines[i].split(")")[-1])
    off = len(lines[i]) - len(lines[i].split(")")[-1]) + m.start()
    ch = lines[i][off]
    lines2 = list(lines)
    lines2[i] = lines[i][:off] + ("B" if ch != "B" else "C") + lines[i][off + 1:]
    p = d / "stale.mm"
    p.write_text("".join(lines2), encoding="utf-8", newline="")
    rep, _ = run_file(p, snapshot=mid)
    full_mut = run_file(p)[0]["counts"]
    res["stale_hash"] = {"edited_line": i + 1, "snapshot": mid["theorem"],
                         "state": rep["snapshot"]["state"],
                         "verified": rep["provable_statements"],
                         "reason": rep["file_void"]["reason"] if rep["file_void"] else None,
                         "full_check_of_edited_file": full_mut}
    # mutated theorem just before the cut, cited by later statements
    idx = mid["theorem_index"]
    labels = [r["label"] for r in fdb.theorems]
    after = labels[idx:]
    cites = {}
    for lab in after:
        for u in fdb.used_of.get(lab, ()):
            cites[u] = cites.get(u, 0) + 1
    cand = [lab for lab in labels[max(0, idx - 2000):idx]
            if cites.get(lab) and "->" in fdb.assertions[lab].stmt]
    x = max(cand, key=lambda lab: (cites[lab], labels.index(lab)))
    xi = labels.index(x) + 1
    xr = fdb.theorems[xi - 1]
    j = xr["line"] - 1
    tok = re.compile(r"(?<=\s)->(?=\s)")          # the token "->", not "-cn->" or "-->"
    m = tok.search(lines[j])
    while m is None:
        j += 1
        m = tok.search(lines[j])
    lines3 = list(lines)
    lines3[j] = lines[j][:m.start()] + "<->" + lines[j][m.end():]
    p3 = d / "mutated.mm"
    p3.write_text("".join(lines3), encoding="utf-8", newline="")
    store = d / "mut.json"
    written, refused, rep_w = snap.write(p3, [x], store=store)
    good, _, _ = snap.write(path, [x], store=d / "good.json")       # honest, unmutated
    rec_good = good[0]
    st = list(fdb.assertions[x].stmt)
    st[st.index("->")] = "<->"
    forged = dict(rec_good, statement=" ".join(st),
                  prefix_sha256=prefix_sha256(p3, rec_good["prefix_lines"]))
    rep, db = run_file(p3, snapshot=forged)
    t = {r["label"]: r for r in rep["theorem_records"]}
    citing = [lab for lab in labels[xi:] if x in fdb.used_of.get(lab, ())]
    res["mutated_theorem"] = {
        "theorem": x, "theorem_index": xi, "cited_by_later": len(citing),
        "honest_writer": {"written": len(written), "refused": refused},
        "full_check_verdict": rep_w and {r["label"]: r["verdict"]
                                         for r in rep_w["theorem_records"]}.get(x),
        "forged_snapshot_state": rep["snapshot"]["state"],
        "carried_verdict": t[x]["verdict"], "carried_verified_here": t[x]["verified_here"],
        "citing_fail": sum(1 for lab in citing if t.get(lab, {}).get("verdict") == "FAIL"),
        "citing_pass": sum(1 for lab in citing if t.get(lab, {}).get("verdict") == "PASS"),
        "counts": rep["counts"]}
    return res


def main(argv):
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2
    reps = int(argv[argv.index("--repeats") + 1]) if "--repeats" in argv else 3
    out = measure(argv[0], reps)
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
