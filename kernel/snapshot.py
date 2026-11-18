"""snapshot -- kernel snapshots: a PASS stored with the prefix it was proven in.

Co-authored. Stdlib only.

A snapshot is one record:
  theorem          label of a provable statement that read PASS
  statement        its statement, as text
  axioms_used      every $a reached through the assertions its proof cites,
                   transitively (syntax axioms included)
  prefix_sha256    sha256 of the database's first prefix_lines lines, bytes as
                   stored: the lines read up to and including the end of its proof
  prefix_lines     that line count
  theorem_index    how many provable statements the prefix holds (this one last)
  kernel_version   the kernel that read it
  rests_on_non_pass  the cited statements that were not PASS (carried, not hidden)
  prefix_non_pass  every provable statement in the prefix that was not PASS, with
                   its verdict and reason; these keep their verdict when carried
  verdict PASS, status DERIVED; human_interest / ai_interest null

Rules
  write    only after a kernel PASS for that theorem, in a run with no file-level
           VOID before it. Anything else is refused and nothing is written.
  use      --from-snapshot: the prefix is re-read and hashed first. A different
           hash, a different kernel version, or a statement that is not where the
           snapshot says -> VOID, and nothing is verified. Otherwise the snapshot
           theorem is re-verified, K more prefix theorems drawn with a logged seed
           are re-verified, and the rest of the prefix is carried (verified_here
           false). A re-verified verdict other than the carried one -> VOID,
           naming the theorem. The statements after the prefix are verified.
  limit    the store is plain JSON. A record written by hand, or edited, is not
           detected as such. A forged PASS for the snapshot theorem is caught on
           every load. A forged PASS for another prefix theorem is caught when it
           is drawn (chance K / (index - 1) per load) or when a later verified
           statement cites it; otherwise it is carried.
"""
import json
from pathlib import Path

from .mm import VERSION, run_file

SCHEMA = "kernel-snapshot/1"
STORE_SCHEMA = "kernel-snapshot-store/1"


def make(db, label, input_path=None):
    """(record, None) or (None, reason refused)."""
    verdict = db.verdict_of.get(label)
    if verdict is None:
        return None, f"{label}: not read in this run"
    if verdict != "PASS":
        return None, f"{label}: verdict {verdict}, a snapshot needs PASS"
    idx = next(i for i, r in enumerate(db.theorems, 1) if r["label"] == label)
    rec = db.theorems[idx - 1]
    if label not in db.digest_at:
        return None, f"{label}: run was not hashing (internal)"
    if db.file_void is not None and (db.file_void.get("line") is None
                                     or db.file_void["line"] <= db.digest_at[label][0]):
        return None, f"{label}: the file is VOID at or before it"
    lines, digest = db.digest_at[label]
    prefix = db.theorems[:idx]
    non_pass = {r["label"]: {"verdict": r["verdict"], "located_error": r["located_error"],
                             "void_reason": r["void_reason"]}
                for r in prefix if r["verdict"] != "PASS"}
    return {
        "schema": SCHEMA,
        "theorem": label,
        "statement": " ".join(db.assertions[label].stmt),
        "axioms_used": db.axioms_used(label),
        "prefix_sha256": digest,
        "prefix_lines": lines,
        "theorem_index": idx,
        "kernel_version": VERSION,
        "verdict": "PASS",
        "status": "DERIVED",
        "rests_on_non_pass": rec["rests_on_non_pass"],
        "prefix_non_pass": non_pass,
        "prefix_counts": {v: sum(1 for r in prefix if r["verdict"] == v)
                          for v in ("PASS", "FAIL", "VOID")},
        "prefix_verified_here": sum(1 for r in prefix if r["verified_here"]),
        "input": None if input_path is None else Path(input_path).name,
        "human_interest": None,
        "ai_interest": None,
    }, None


def load(store):
    p = Path(store)
    if not p.exists():
        return {"schema": STORE_SCHEMA, "snapshots": []}
    data = json.loads(p.read_text())
    if data.get("schema") != STORE_SCHEMA:
        raise ValueError(f"{store}: not a {STORE_SCHEMA} file")
    return data


def add(store, records):
    """Append records; one with the same theorem and prefix hash is replaced."""
    data = load(store)
    keep = [s for s in data["snapshots"]
            if not any(s["theorem"] == r["theorem"]
                       and s["prefix_sha256"] == r["prefix_sha256"] for r in records)]
    data["snapshots"] = keep + list(records)
    Path(store).write_text(json.dumps(data, indent=1) + "\n")
    return data


def select(data, label=None):
    """(record, None) or (None, reason)."""
    snaps = data["snapshots"]
    if label is not None:
        snaps = [s for s in snaps if s["theorem"] == label]
    if not snaps:
        return None, "no snapshot" + ("" if label is None else f" for {label}")
    if len(snaps) > 1:
        return None, (f"{len(snaps)} snapshots" + ("" if label is None else f" for {label}")
                      + "; name one with --snap LABEL")
    return snaps[0], None


def cut_position(n, f):
    """Position k = round(n * f), Python's round (halves to even), clamped to 1..n."""
    return max(1, min(n, round(n * f)))


def _count_provable(path):
    """Provable statements in the file, by token, before the run (for caches at
    fractions: the positions must be known while reading)."""
    from .mm import Database
    with open(path, encoding="utf-8", errors="strict", newline="") as f:
        return sum(1 for t in Database()._tokens(f) if t == "$p")


def write(path, labels=(), fractions=(), store="snapshots.json", snapshot=None, spot=25,
          seed=None, cache_dir=None):
    """Run the kernel on `path` (from `snapshot` if given) and write a snapshot for
    each named label and each fraction of the provable statements (by position).
    cache_dir: also write each snapshot's parse cache there, and record the cache
    file's sha256 in the snapshot. Returns (written records, refusals, report)."""
    cap = None
    if cache_dir is not None:
        from .parse_cache import Capture
        positions = set()
        if fractions:
            try:
                n0 = _count_provable(path)
            except Exception:
                n0 = 0
            positions = {cut_position(n0, f) for f in fractions} if n0 else set()
        cap = Capture(positions)
        cap.labels = set(labels)
    rep, db = run_file(path, hashing=True, snapshot=snapshot, spot=spot, seed=seed,
                       capture=cap)
    targets = list(labels)
    n = len(db.theorems)
    for f in fractions:
        k = cut_position(n, f)
        if n:
            targets.append(db.theorems[k - 1]["label"])
    written, refused = [], []
    if rep.get("snapshot") and rep["snapshot"]["state"] == "VOID":
        return [], [f"{t}: the run started from a VOID snapshot" for t in targets], rep
    for t in targets:
        r, why = make(db, t, path)
        if r is None:
            refused.append(why)
            continue
        if cap is not None:
            if t in cap.states:
                r["parse_cache"] = cap.write(t, r["kernel_version"], cache_dir)
            else:
                r["parse_cache"] = None
                r["parse_cache_note"] = "not captured: position not known while reading"
        written.append(r)
    if written:
        add(store, written)
    return written, refused, rep
