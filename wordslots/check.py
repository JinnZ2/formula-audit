"""check -- a word claims nothing until its slots are filled. Co-authored.

PLACE TABLE (JSON): word -> ordered slots, Lojban-style.
    warm:  x1 what is warm, x2 by standard
    safe:  x1 what is safe, x2 from threat, x3 for whom
  Each slot: name, role, required (true / false), its own status tag, and
  optionally numeric bounds. A table entry is PROPOSED until the holder of
  the word confirms it; this checker never changes a tag.

CLAIM RECORD: fixed fields, declared here before any record is read
(COBOL-style: a field that was not declared is an error, not extra data).
    word        the word claimed
    slots       {slot name: filling}; a filling is text, or
                {"text", "value", "unit", "status", "is"}
    evidential  how the claimant knows: observed / hearsay / concluded /
                opinion / defined
    source      who or what the claim comes from
    source_path where the claim was found
    table       (optional) which table entry status the claimant relied on

EVIDENTIAL -> STATUS of the claim, carried, never upgraded:
    observed  -> OBSERVED     concluded -> DERIVED
    hearsay   -> PROPOSED     opinion   -> PROPOSED
    defined   -> OBSERVED     (given input, like an axiom in the kernel)
  no evidential given -> the claim's status stays null.

VERDICT (status DERIVED; VOID has none):
    PASS       every required slot filled, nothing undeclared, and every
               numeric bound that was checked holds
    FAIL       a numeric slot value lies outside its declared bounds (located)
    UNDECIDED  a numeric slot value straddles its bounds (MIXED / UNDECIDED
               from numcheck)
    VOID       unknown word; a required slot empty (each one named); an
               undeclared field or slot; an unknown evidential; a bad table
               entry; numcheck VOID on a bound; internal error

LEVEL-88 STYLE RANGES: a slot may declare "bounds" {lo, hi, unit} and / or
named "ranges" {name: {lo, hi, unit}} (a name standing for a range of values,
as a COBOL 88 level does). A filling that carries a numeric value is handed
to numcheck: value = midpoint within tolerance half-width, units first. A
filling's "is" names which range it claims. No numeric value given -> the
bound is UNCHECKED, which is not a pass of the bound.
"""
from fractions import Fraction

from numcheck.check import Bad, check_point, to_interval

VERSION = "wordslots branch4-0"
RECORD_FIELDS = ("word", "slots", "evidential", "source", "source_path", "table")
FILLING_FIELDS = ("text", "value", "unit", "status", "is")
SLOT_FIELDS = ("name", "role", "required", "status", "bounds", "ranges")
STATUS = ("OBSERVED", "DERIVED", "PROPOSED")
EVIDENTIAL = {"observed": "OBSERVED", "concluded": "DERIVED", "hearsay": "PROPOSED",
              "opinion": "PROPOSED", "defined": "OBSERVED"}


class Void(Exception):
    def __init__(self, reason, slot=None):
        super().__init__(reason)
        self.reason, self.slot = reason, slot


def _empty(x):
    if x is None:
        return True
    if isinstance(x, str):
        return not x.strip()
    if isinstance(x, dict):
        return _empty(x.get("text")) and x.get("value") is None
    return False


def read_table(table):
    """Check a place table's shape. Returns {word: entry}. Raises Void."""
    words = table.get("words") if isinstance(table, dict) else None
    if not isinstance(words, dict):
        raise Void("place table has no words")
    for word, entry in words.items():
        if not isinstance(entry, dict) or not isinstance(entry.get("slots"), list) \
                or not entry["slots"]:
            raise Void(f"place table: word {word!r} has no slots")
        if entry.get("status") not in STATUS:
            raise Void(f"place table: word {word!r} has no status tag")
        seen = set()
        for s in entry["slots"]:
            if not isinstance(s, dict) or not isinstance(s.get("name"), str):
                raise Void(f"place table: word {word!r} has a slot with no name")
            extra = [k for k in s if k not in SLOT_FIELDS]
            if extra:
                raise Void(f"place table: {word}.{s['name']} has undeclared field {extra[0]!r}")
            if s["name"] in seen:
                raise Void(f"place table: {word}.{s['name']} declared twice")
            seen.add(s["name"])
            if not isinstance(s.get("required"), bool):
                raise Void(f"place table: {word}.{s['name']} does not say required true / false")
            if s.get("status") not in STATUS:
                raise Void(f"place table: {word}.{s['name']} has no status tag")
    return words


def _range_check(word, slot, filling, source_path):
    """The numeric bounds of one filled slot. Returns a list of range records."""
    named = slot.get("ranges") or {}
    claimed = filling.get("is") if isinstance(filling, dict) else None
    todo = []
    if slot.get("bounds") is not None:
        todo.append(("bounds", slot["bounds"]))
    if claimed is not None:
        if claimed not in named:
            raise Void(f"slot {slot['name']}: range {claimed!r} is not declared for "
                       f"{word}.{slot['name']}", slot["name"])
        todo.append((claimed, named[claimed]))
    out = []
    for name, rng in todo:
        rec = {"slot": slot["name"], "range": name, "bounds": rng, "state": "UNCHECKED",
               "reason": "no numeric value given; nothing was checked", "numcheck": None}
        value = filling.get("value") if isinstance(filling, dict) else None
        if value is not None:
            try:
                iv = to_interval([rng.get("lo"), rng.get("hi")], f"bounds of {slot['name']}")
            except Bad as e:
                raise Void(f"slot {slot['name']}: {e}", slot["name"])
            mid, half = (iv.lo + iv.hi) / 2, (iv.hi - iv.lo) / 2
            n = check_point({"formula": "v = m", "tolerance": str(half),
                             "source_path": source_path,
                             "values": {"v": {"value": value, "unit": filling.get("unit"),
                                              "status": filling.get("status")},
                                        "m": {"value": str(Fraction(mid)),
                                              "unit": rng.get("unit"),
                                              "status": slot.get("status")}}})
            rec.update(state={"HOLDS": "IN_RANGE", "FAILS": "OUT_OF_RANGE"}.get(
                n["verdict"], n["verdict"]), reason=n["void_reason"],
                numcheck={k: n[k] for k in ("verdict", "void_reason", "deciding_tier",
                                            "precision", "rigorous", "intervals",
                                            "status")})
        out.append(rec)
    return out


def check_claim(claim, words, index=None, input_path=None):
    get = claim.get if isinstance(claim, dict) else (lambda *_: None)
    rec = {"word": get("word"), "verdict": "VOID", "void_reason": None,
           "located_error": None, "status": None,
           "slots": None, "missing_required": [], "ranges": [],
           "evidential": get("evidential"), "claim_status": None,
           "source": get("source"), "table_entry_status": None,
           "provenance": {"source_path": get("source_path"), "input": input_path,
                          "index": index, "tool": VERSION},
           "human_interest": None, "ai_interest": None}
    try:
        if not isinstance(claim, dict):
            raise Void("claim is not a record")
        extra = [k for k in claim if k not in RECORD_FIELDS]
        if extra:
            raise Void("undeclared field" + ("s" if len(extra) > 1 else "") + ": "
                       + ", ".join(repr(k) for k in extra))
        word = claim.get("word")
        if not isinstance(word, str) or not word.strip():
            raise Void("no word")
        if word not in words:
            raise Void(f"unknown word {word!r}: not in the place table")
        entry = words[word]
        rec["table_entry_status"] = entry["status"]
        ev = claim.get("evidential")
        if ev is not None:
            if ev not in EVIDENTIAL:
                raise Void(f"unknown evidential {ev!r}; one of: " + ", ".join(EVIDENTIAL))
            rec["claim_status"] = EVIDENTIAL[ev]          # carried as mapped, never upgraded
        filled = claim.get("slots")
        if filled is None:
            filled = {}
        if not isinstance(filled, dict):
            raise Void("slots is not a {slot name: filling} table")
        declared = [s["name"] for s in entry["slots"]]
        stray = [k for k in filled if k not in declared]
        if stray:
            raise Void(f"undeclared slot" + ("s" if len(stray) > 1 else "") + f" for {word!r}: "
                       + ", ".join(stray), stray[0])
        rows, missing = [], []
        for s in entry["slots"]:
            f = filled.get(s["name"])
            if isinstance(f, dict):
                bad = [k for k in f if k not in FILLING_FIELDS]
                if bad:
                    raise Void(f"slot {s['name']}: undeclared field {bad[0]!r}", s["name"])
                if f.get("status") is not None and f["status"] not in STATUS:
                    raise Void(f"slot {s['name']}: status {f['status']!r} is not one of "
                               + ", ".join(STATUS), s["name"])
            elif f is not None and not isinstance(f, str):
                raise Void(f"slot {s['name']}: a filling is text or a record", s["name"])
            empty = _empty(f)
            rows.append({"name": s["name"], "role": s.get("role"), "required": s["required"],
                         "slot_status": s["status"],
                         "slot_state": "VOID" if empty else "FILLED",
                         "filling": None if empty else f})
            if empty and s["required"]:
                missing.append(s["name"])
        rec["slots"] = rows                               # void slots are kept, not dropped
        rec["missing_required"] = missing
        if missing:
            roles = {s["name"]: s.get("role") for s in entry["slots"]}
            raise Void("required slot" + ("s" if len(missing) > 1 else "") + " empty: "
                       + ", ".join(f"{m} ({roles[m]})" for m in missing), missing[0])
        for s, row in zip(entry["slots"], rows):
            if row["slot_state"] == "FILLED":
                rec["ranges"] += _range_check(word, s, row["filling"], get("source_path"))
        states = [r["state"] for r in rec["ranges"]]
        if "VOID" in states:
            r = next(x for x in rec["ranges"] if x["state"] == "VOID")
            raise Void(f"slot {r['slot']}, range {r['range']}: numcheck VOID: {r['reason']}",
                       r["slot"])
        if "OUT_OF_RANGE" in states:
            r = next(x for x in rec["ranges"] if x["state"] == "OUT_OF_RANGE")
            rec.update(verdict="FAIL", status="DERIVED",
                       located_error={"slot": r["slot"], "range": r["range"],
                                      "rule": "value outside the declared bounds",
                                      "bounds": r["bounds"],
                                      "value": r["numcheck"]["intervals"]["lhs"]})
        elif any(x in ("MIXED", "UNDECIDED") for x in states):
            r = next(x for x in rec["ranges"] if x["state"] in ("MIXED", "UNDECIDED"))
            rec.update(verdict="UNDECIDED", status="DERIVED",
                       located_error={"slot": r["slot"], "range": r["range"],
                                      "rule": "value straddles the declared bounds",
                                      "bounds": r["bounds"]})
        else:
            rec.update(verdict="PASS", status="DERIVED")
    except Void as v:
        rec.update(verdict="VOID", void_reason=v.reason, status=None,
                   located_error={"slot": v.slot} if v.slot else None)
    except Exception as e:                       # fail closed
        rec.update(verdict="VOID", void_reason=f"internal: {type(e).__name__}: {e}", status=None)
    return rec


def check_all(claims, table, input_path=None, table_path=None):
    entries = claims.get("claims") if isinstance(claims, dict) and "claims" in claims else claims
    if not isinstance(entries, list):
        entries = [entries]
    names = ("PASS", "FAIL", "UNDECIDED", "VOID")
    try:
        words = read_table(table)
        records = [check_claim(c, words, i, input_path) for i, c in enumerate(entries)]
        table_void = None
    except Void as v:                            # a bad table voids every claim
        table_void = v.reason
        records = []
        for i, c in enumerate(entries):
            r = check_claim(c, {}, i, input_path)
            r["void_reason"] = f"place table VOID: {v.reason}"
            records.append(r)
    return {"tool": VERSION, "input": input_path, "table": table_path,
            "table_void": table_void,
            "counts": {v: sum(1 for r in records if r["verdict"] == v) for v in names},
            "records": records}
