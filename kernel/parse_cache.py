"""parse_cache -- the parse state of a snapshot's prefix, stored beside it.

Co-authored. Stdlib only (marshal: plain values only; loading runs no code).

A cache holds what the kernel knows at the end of a snapshot's prefix: declared
symbols, open scopes, every assertion's frame, the labels each proof cites, and,
for each provable statement in the prefix, what re-verifying it needs (its proof
tokens, the hypotheses and $d pairs and variables active where it stood). With it
a snapshot load skips parsing the prefix; the prefix is still read and hashed.

Key: (prefix_sha256, kernel version), stored inside the file. The snapshot
records the file's own sha256. On load, any of: file missing, unreadable, its
sha256 not the one recorded, its key not (the snapshot's prefix_sha256, this
kernel's version), or a schema it does not know -> the cache is not used, the
reason is logged in the report, and the prefix is parsed in full. Nothing from a
cache that failed a check is used, in part or whole.

Re-verification from a cache (the snapshot theorem, the spot sample) uses the
stored context: the hypotheses, $d pairs and variables active at that statement,
and only the assertions that come before it.
"""
import hashlib
import marshal
from pathlib import Path

SCHEMA = "kernel-parse-cache/1"


def name_for(prefix_sha256, version):
    safe = "".join(c if c.isalnum() else "-" for c in version)
    return f"{prefix_sha256}.{safe}.cache"


class Capture:
    """Attached to a Database while it reads; records each $p's context and the
    whole state at the chosen positions."""

    def __init__(self, positions):
        self.positions = set(positions)
        self.labels = set()
        self.ctx = {}               # label -> (proof, dv_id, v_id, extra hyps)
        self.dv_ids, self.v_ids = {}, {}
        self.states = {}            # label -> marshal bytes

    def _intern(self, table, items):
        key = tuple(sorted(items))
        i = table.get(key)
        if i is None:
            i = table[key] = len(table)
        return i

    def context(self, db, a, proof):
        dv = set().union(*[fr.d for fr in db.frames])
        mand = {h[1] for h in a.hyps}
        extra = {t: db.active_hyps[t] for t in proof
                 if t in db.active_hyps and t not in mand}
        self.ctx[a.label] = (tuple(proof), self._intern(self.dv_ids, dv),
                             self._intern(self.v_ids, db.active_v), extra)

    def state(self, db, label):
        lines, digest = db.digest_at[label]
        order = list(db.assertions)
        prefix = db.theorems
        blob = {
            "schema": SCHEMA, "key": [digest, None], "prefix_lines": lines,
            "tok_in_line": db.tok_in_line, "statements_read": db.statements_read,
            "constants": sorted(db.constants), "active_v": sorted(db.active_v),
            "f_of": dict(db.f_of), "active_hyps": dict(db.active_hyps),
            "frames": [(list(fr.v), list(fr.hyps), sorted(fr.d)) for fr in db.frames],
            "labels": sorted(db.labels),
            "assertions": [(x.label, x.kind, x.stmt, tuple(x.hyps), tuple(sorted(x.dv)),
                            x.line) for x in (db.assertions[k] for k in order)],
            "axioms": list(db.axioms),
            "theorems": [(r["label"], r["line"], r["proof_format"]) for r in prefix],
            "used_of": {r["label"]: tuple(sorted(db.used_of.get(r["label"], ())))
                        for r in prefix},
            "ctx": {r["label"]: self.ctx[r["label"]] for r in prefix},
            "dv_table": [list(k) for k, _ in sorted(self.dv_ids.items(), key=lambda kv: kv[1])],
            "v_table": [list(k) for k, _ in sorted(self.v_ids.items(), key=lambda kv: kv[1])],
        }
        self.states[label] = blob

    def write(self, label, version, directory):
        blob = dict(self.states[label])
        blob["key"] = [blob["key"][0], version]
        data = marshal.dumps(blob, 4)
        p = Path(directory) / name_for(blob["key"][0], version)
        p.write_bytes(data)
        return {"file": p.name, "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data), "key": blob["key"]}


def load(directory, snapshot, version):
    """(blob, None) or (None, reason not used)."""
    rec = snapshot.get("parse_cache")
    if not rec:
        return None, "the snapshot names no parse cache"
    p = Path(directory) / rec["file"]
    try:
        data = p.read_bytes()
    except OSError as e:
        return None, f"cache file {rec['file']}: {e.strerror}"
    if hashlib.sha256(data).hexdigest() != rec["sha256"]:
        return None, f"cache file {rec['file']}: sha256 is not the one the snapshot records"
    try:
        blob = marshal.loads(data)
    except (EOFError, ValueError, TypeError) as e:
        return None, f"cache file {rec['file']}: unreadable ({e})"
    if not isinstance(blob, dict) or blob.get("schema") != SCHEMA:
        return None, f"cache file {rec['file']}: not a {SCHEMA} file"
    if blob.get("key") != [snapshot["prefix_sha256"], version]:
        return None, (f"cache file {rec['file']}: key {blob.get('key')} is not "
                      f"[{snapshot['prefix_sha256']}, {version}]")
    if blob.get("prefix_lines") != snapshot["prefix_lines"] or \
            len(blob.get("theorems", ())) != snapshot["theorem_index"]:
        return None, f"cache file {rec['file']}: prefix shape does not match the snapshot"
    return blob, None


class _Before:
    """The assertions that come before a position, for re-verification."""

    def __init__(self, assertions, order, limit):
        self.a, self.order, self.limit = assertions, order, limit

    def get(self, k):
        x = self.a.get(k)
        return x if x is not None and self.order[k] < self.limit else None


def restore(db, blob, mm):
    """Rebuild a Database's state at the end of the prefix from a cache blob, and
    its prefix records: carried, except the snapshot theorem and the spot sample,
    which are re-verified with their stored context."""
    db.constants = set(blob["constants"])
    db.active_v = set(blob["active_v"])
    db.f_of = {k: tuple(v) for k, v in blob["f_of"].items()}
    db.active_hyps = {k: (v[0], tuple(v[1])) for k, v in blob["active_hyps"].items()}
    db.frames = []
    for v, hyps, d in blob["frames"]:
        fr = mm.Frame()
        fr.v, fr.hyps, fr.d = list(v), [tuple(h) for h in hyps], {tuple(x) for x in d}
        db.frames.append(fr)
    db.labels = set(blob["labels"])
    db.assertions, order = {}, {}
    for i, (label, kind, stmt, hyps, dv, line) in enumerate(blob["assertions"]):
        db.assertions[label] = mm.Assertion(label, kind, tuple(stmt),
                                            [tuple(h) for h in hyps],
                                            {tuple(x) for x in dv}, line)
        order[label] = i
    db.axioms = list(blob["axioms"])
    db.used_of = {k: set(v) for k, v in blob["used_of"].items()}
    dv_table = [{tuple(x) for x in t} for t in blob["dv_table"]]
    v_table = [set(t) for t in blob["v_table"]]
    c = db.carry
    for pos, (label, line, fmt) in enumerate(blob["theorems"], 1):
        if pos == c["index"] or pos in c["spot"]:
            a = db.assertions[label]
            proof, dv_id, v_id, extra = blob["ctx"][label]
            hyps = {h[1]: (h[0], h[2]) for h in a.hyps}
            hyps.update({k: (v[0], tuple(v[1])) for k, v in extra.items()})
            ctx = (v_table[v_id], hyps, dv_table[dv_id],
                   _Before(db.assertions, order, order[label]))
            db._recheck(a, list(proof), pos, ctx)
        else:
            np = c["non_pass"].get(label)
            verdict = "PASS" if np is None else np["verdict"]
            rests = {u for u in db.used_of[label] if db.verdict_of.get(u, "PASS") != "PASS"}
            db._record(label, line, verdict, fmt, None, rests=rests, carried=c["label"],
                       located=None if np is None else np.get("located_error"),
                       void_reason=None if np is None else np.get("void_reason"))
    db.line = blob["prefix_lines"]
    db.statements_read = blob["statements_read"]
    db.first_line, db.skip_tokens = blob["prefix_lines"], blob["tok_in_line"]
