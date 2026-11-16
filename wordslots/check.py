"""check -- a word claims nothing until its slots are filled. Co-authored. v1.

PLACE TABLE (JSON): word -> ordered slots, Lojban-style.
    warm:  x1 what is warm, x2 by standard
    safe:  x1 what is safe, x2 from threat, x3 for whom
    more:  x1 what is more, x2 than what, x3 in what property, x4 by what amount
  Each slot: name, role, required (true / false), its own status tag, and
  optionally numeric bounds. Each word: status, class (JUDGMENT / COMPARATIVE /
  EMOTIVE / FEAR, or null), shape (the Lojban root it is shaped on; recalled,
  not checked against a Lojban source). A table entry is PROPOSED until the
  holder of the word confirms it; this checker never changes a tag.

CLAIM RECORD: fixed fields, declared here before any record is read
(COBOL-style: a field that was not declared is an error, not extra data),
each with a width. A value longer than its width, or a number outside its
picture, is VOID ("would truncate"): nothing is ever cut to fit.
    word        X(20)   the word claimed
    slots               {slot name: filling}; a filling is text X(40), or
                        {"text", "value", "unit", "status", "is"}
    reading     X(8)    PHYSICAL / SOCIAL; required for an EMOTIVE word
    magnitude           {"value": S9(7)V9(4), "unit": X(12)}
    evidential  X(10)   how the claimant knows (below)
    speaker     X(40)   who is making the claim
    oral_record         for ka'u: exactly four checks, each {"name", "met": "y" / "n"}
    source      X(40)   who or what the claim comes from
    source_path X(80)   where the claim was found
    table               which table entry status the claimant relied on

EVIDENTIAL -> STATUS of the claim, carried, never upgraded:
    observed  -> OBSERVED     concluded -> DERIVED     defined -> OBSERVED
    hearsay   -> PROPOSED     opinion   -> PROPOSED
    ja'o      -> DERIVED      (Lojban: I conclude)
    se'o      -> OBSERVED     (Lojban: I know by internal experience), with
                 scope "speaker's own state only": x1 is filled with the
                 speaker, and the other places are the speaker's own and are
                 waived. se'o on anything external -> DEGRADED.
    ka'u      -> CARRIED if all four oral-record checks are met; any "n", or
                 no oral_record -> PROPOSED      (Lojban: cultural knowledge)
  no evidential given -> the claim's status stays null.
  The meanings of se'o, ja'o and ka'u are recalled, not checked against a
  Lojban source here.

VERDICT (status DERIVED; VOID has none):
    PASS       every required slot filled, nothing undeclared, and every
               numeric bound that was checked holds
    DEGRADED   something required is missing (a slot, the reading of an
               EMOTIVE word, a magnitude, a speaker), or se'o is applied to
               something external. What is filled is kept and usable; each
               missing item is listed with its name, its reason and where it
               came from. DEGRADED is not PASS and must not be read as one.
    FAIL       a numeric slot value lies outside its declared bounds (located)
    UNDECIDED  a numeric slot value straddles its bounds
    VOID       unknown word; an undeclared field or slot; a bad tag (unknown
               evidential, reading, status, class); a value that would
               truncate; a bad table entry; numcheck VOID on a bound;
               internal error
  Order when several apply: VOID, then FAIL, then DEGRADED, then UNDECIDED.

LEVEL-88 STYLE RANGES: a slot may declare "bounds" {lo, hi, unit} and / or
named "ranges" {name: {lo, hi, unit}}. A filling that carries a numeric
value, or the claim's magnitude when the filling carries none, is handed to
numcheck: value = midpoint within tolerance half-width, units first. A
filling's "is" names which range it claims. No numeric value given -> the
bound is UNCHECKED, which is not a pass of the bound.
"""
from fractions import Fraction

from numcheck.check import Bad, check_point, to_interval

VERSION = "wordslots branch4-1"
RECORD_FIELDS = ("word", "slots", "reading", "magnitude", "evidential", "speaker",
                 "oral_record", "source", "source_path", "table")
FILLING_FIELDS = ("text", "value", "unit", "status", "is")
SLOT_FIELDS = ("name", "role", "required", "status", "bounds", "ranges")
WORD_FIELDS = ("status", "class", "shape", "slots", "magnitude_required_for")
STATUS = ("OBSERVED", "DERIVED", "PROPOSED")
CLASSES = ("JUDGMENT", "COMPARATIVE", "EMOTIVE", "FEAR")
READINGS = ("PHYSICAL", "SOCIAL")
EVIDENTIAL = {"observed": "OBSERVED", "concluded": "DERIVED", "hearsay": "PROPOSED",
              "opinion": "PROPOSED", "defined": "OBSERVED",
              "ja'o": "DERIVED", "se'o": "OBSERVED", "ka'u": None}
SELF_WORDS = ("i", "me", "myself")
WIDTHS = {"word": 20, "slot_text": 40, "reading": 8, "unit": 12, "evidential": 10,
          "speaker": 40, "source": 40, "source_path": 80, "range_name": 20}
MAGNITUDE_PIC = {"picture": "S9(7)V9(4)", "integer_digits": 7, "decimal_digits": 4}
ORAL_CHECKS = 4


class Void(Exception):
    def __init__(self, reason, slot=None):
        super().__init__(reason)
        self.reason, self.slot = reason, slot


def fits(value, field, what):
    """A text value against its declared width. Raises Void; never cuts."""
    width = WIDTHS[field]
    if isinstance(value, str) and len(value) > width:
        raise Void(f"would truncate: {what} has {len(value)} characters, "
                   f"the field is X({width})")


def fits_number(value, what):
    """A number against S9(7)V9(4): at most 7 integer and 4 decimal digits."""
    if isinstance(value, bool) or value is None or isinstance(value, float):
        raise Void(f"{what}: not an exact number")
    try:
        f = Fraction(str(value).strip())
    except (ValueError, ZeroDivisionError):
        raise Void(f"{what}: cannot read {value!r} as a number")
    pic = MAGNITUDE_PIC
    if abs(f) >= 10 ** pic["integer_digits"]:
        raise Void(f"would truncate: {what} {value} is beyond {pic['picture']} "
                   f"({pic['integer_digits']} integer digits)")
    if (f * 10 ** pic["decimal_digits"]).denominator != 1:
        raise Void(f"would truncate: {what} {value} has more than "
                   f"{pic['decimal_digits']} decimal places ({pic['picture']})")
    return f


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
        extra = [k for k in entry if k not in WORD_FIELDS]
        if extra:
            raise Void(f"place table: word {word!r} has undeclared field {extra[0]!r}")
        if entry.get("status") not in STATUS:
            raise Void(f"place table: word {word!r} has no status tag")
        if entry.get("class") is not None and entry["class"] not in CLASSES:
            raise Void(f"place table: word {word!r} has class {entry['class']!r}, not one of "
                       + ", ".join(CLASSES))
        need = entry.get("magnitude_required_for") or []
        if not isinstance(need, list) or any(r not in READINGS for r in need):
            raise Void(f"place table: word {word!r}: magnitude_required_for lists readings")
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


def _range_check(word, slot, filling, magnitude, source_path):
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
               "reason": "no numeric value given; nothing was checked", "numcheck": None,
               "value_from": None}
        value = filling.get("value") if isinstance(filling, dict) else None
        unit = filling.get("unit") if isinstance(filling, dict) else None
        status = filling.get("status") if isinstance(filling, dict) else None
        rec["value_from"] = "the filling" if value is not None else None
        if value is None and magnitude is not None:
            value, unit, status = magnitude["value"], magnitude.get("unit"), None
            rec["value_from"] = "the claim's magnitude"
        if value is not None:
            try:
                iv = to_interval([rng.get("lo"), rng.get("hi")], f"bounds of {slot['name']}")
            except Bad as e:
                raise Void(f"slot {slot['name']}: {e}", slot["name"])
            mid, half = (iv.lo + iv.hi) / 2, (iv.hi - iv.lo) / 2
            n = check_point({"formula": "v = m", "tolerance": str(half),
                             "source_path": source_path,
                             "values": {"v": {"value": value, "unit": unit, "status": status},
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


def _oral_record(rec_in):
    """ka'u: exactly four checks, each named and met y / n. Returns
    (claim status, detail). Raises Void on a malformed record."""
    if rec_in is None:
        return "PROPOSED", {"given": False, "checks": None, "all_met": False,
                            "reason": "no oral_record: the four checks were not made"}
    if not isinstance(rec_in, list) or len(rec_in) != ORAL_CHECKS:
        raise Void(f"oral_record needs exactly {ORAL_CHECKS} checks")
    names = []
    for c in rec_in:
        if not isinstance(c, dict) or not isinstance(c.get("name"), str) \
                or not c["name"].strip() or c.get("met") not in ("y", "n") \
                or any(k not in ("name", "met", "note") for k in c):
            raise Void("oral_record: each check needs name and met y / n")
        names.append(c["name"])
    if len(set(names)) != ORAL_CHECKS:
        raise Void("oral_record: the four checks must be four different checks")
    unmet = [c["name"] for c in rec_in if c["met"] == "n"]
    return ("CARRIED" if not unmet else "PROPOSED"), {
        "given": True, "checks": rec_in, "all_met": not unmet, "not_met": unmet,
        "reason": "all four checks met: carried as it came" if not unmet
        else "a check is not met: " + ", ".join(unmet)}


def check_claim(claim, words, index=None, input_path=None):
    get = claim.get if isinstance(claim, dict) else (lambda *_: None)
    prov = {"source_path": get("source_path"), "input": input_path, "index": index,
            "tool": VERSION}
    rec = {"word": get("word"), "verdict": "VOID", "void_reason": None,
           "located_error": None, "status": None, "pass_equivalent": False,
           "word_class": None, "shape": None,
           "slots": None, "missing_required": [], "degraded": None, "usable": None,
           "ranges": [], "reading": get("reading"), "magnitude": get("magnitude"),
           "evidential": get("evidential"), "claim_status": None, "scope": None,
           "speaker": get("speaker"), "oral_record": None,
           "source": get("source"), "table_entry_status": None,
           "provenance": prov, "human_interest": None, "ai_interest": None}
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
        fits(word, "word", "word")
        for f in ("speaker", "source", "source_path", "evidential", "reading"):
            if claim.get(f) is not None and not isinstance(claim[f], str):
                raise Void(f"{f} is not text")
            fits(claim.get(f), f, f)
        if word not in words:
            raise Void(f"unknown word {word!r}: not in the place table")
        entry = words[word]
        rec.update(table_entry_status=entry["status"], word_class=entry.get("class"),
                   shape=entry.get("shape"))
        ev = claim.get("evidential")
        if ev is not None and ev not in EVIDENTIAL:
            raise Void(f"unknown evidential {ev!r}; one of: " + ", ".join(EVIDENTIAL))
        reading = claim.get("reading")
        if reading is not None and reading not in READINGS:
            raise Void(f"reading {reading!r} is not one of " + ", ".join(READINGS))
        magnitude = claim.get("magnitude")
        if magnitude is not None:
            if not isinstance(magnitude, dict) or magnitude.get("value") is None \
                    or any(k not in ("value", "unit") for k in magnitude):
                raise Void("magnitude needs value (and unit)")
            fits_number(magnitude["value"], "magnitude")
            if magnitude.get("unit") is not None and not isinstance(magnitude["unit"], str):
                raise Void("magnitude unit is not text")
            fits(magnitude.get("unit"), "unit", "magnitude unit")
        filled = claim.get("slots")
        if filled is None:
            filled = {}
        if not isinstance(filled, dict):
            raise Void("slots is not a {slot name: filling} table")
        declared = [s["name"] for s in entry["slots"]]
        stray = [k for k in filled if k not in declared]
        if stray:
            raise Void("undeclared slot" + ("s" if len(stray) > 1 else "") + f" for {word!r}: "
                       + ", ".join(stray), stray[0])
        for s in entry["slots"]:
            f = filled.get(s["name"])
            if isinstance(f, dict):
                bad = [k for k in f if k not in FILLING_FIELDS]
                if bad:
                    raise Void(f"slot {s['name']}: undeclared field {bad[0]!r}", s["name"])
                if f.get("status") is not None and f["status"] not in STATUS:
                    raise Void(f"slot {s['name']}: status {f['status']!r} is not one of "
                               + ", ".join(STATUS), s["name"])
                fits(f.get("text"), "slot_text", f"slot {s['name']}")
                fits(f.get("unit"), "unit", f"slot {s['name']} unit")
                fits(f.get("is"), "range_name", f"slot {s['name']} range name")
                if f.get("value") is not None and not isinstance(f["value"], (list, dict)):
                    fits_number(f["value"], f"slot {s['name']} value")
            elif f is not None and not isinstance(f, str):
                raise Void(f"slot {s['name']}: a filling is text or a record", s["name"])
            else:
                fits(f, "slot_text", f"slot {s['name']}")

        # ---- evidential: the claim's own status, and the scope of se'o ----
        missing, waived, self_scope = [], [], False

        def lack(name, kind, reason, role=None):
            missing.append({"name": name, "kind": kind, "role": role, "reason": reason,
                            "provenance": {"source_path": prov["source_path"],
                                           "input": input_path, "index": index,
                                           "declared_in": "place table" if kind == "slot"
                                           else "claim record"}})
        x1 = entry["slots"][0]["name"]
        if ev == "se'o":
            speaker = claim.get("speaker")
            given = filled.get(x1)
            text = (given.get("text") if isinstance(given, dict) else given) or ""
            rec["claim_status"] = "OBSERVED"
            rec["scope"] = "speaker's own state only"
            if _empty(speaker):
                lack("speaker", "field", "se'o reports the speaker's own state and no "
                                         "speaker is given")
            elif _empty(given):
                filled = dict(filled, **{x1: speaker})          # auto-filled
                rec["x1_auto_filled"] = True
                self_scope = True
            elif text.strip().lower() in SELF_WORDS or text.strip() == speaker.strip():
                self_scope = True
            else:
                lack(x1, "scope", f"se'o covers the speaker's own state only; {x1} is "
                                  f"{text.strip()!r}, not the speaker: an assessment of "
                                  "something external needs another evidential",
                     entry["slots"][0].get("role"))
        elif ev == "ka'u":
            rec["claim_status"], rec["oral_record"] = _oral_record(claim.get("oral_record"))
        elif ev is not None:
            rec["claim_status"] = EVIDENTIAL[ev]              # carried as mapped, never upgraded
        if ev != "ka'u" and claim.get("oral_record") is not None:
            raise Void("oral_record is for the evidential ka'u only")

        # ---- slots ----
        rows = []
        for s in entry["slots"]:
            f = filled.get(s["name"])
            empty = _empty(f)
            state = "VOID" if empty else "FILLED"
            if empty and s["required"]:
                if self_scope and s["name"] != x1:
                    state = "WAIVED"
                    waived.append(s["name"])
                else:
                    lack(s["name"], "slot", "required slot empty", s.get("role"))
            rows.append({"name": s["name"], "role": s.get("role"), "required": s["required"],
                         "slot_status": s["status"], "slot_state": state,
                         "filling": None if empty else f})
        if entry.get("class") == "EMOTIVE" and reading is None:
            if self_scope:
                waived.append("reading")
            else:
                lack("reading", "field", "an EMOTIVE word needs its reading: PHYSICAL or SOCIAL")
        has_value = magnitude is not None or any(
            isinstance(filled.get(n), dict) and filled[n].get("value") is not None
            for n in declared)                       # a filling's value is a magnitude too
        if reading in (entry.get("magnitude_required_for") or []) and not has_value:
            if self_scope:
                waived.append("magnitude")
            else:
                lack("magnitude", "field", f"a {reading} reading of {word!r} needs a "
                                           "magnitude with its unit")
        rec["slots"] = rows                               # void slots are kept, not dropped
        rec["missing_required"] = [m["name"] for m in missing]
        rec["waived_by_self_report"] = waived
        rec["usable"] = {"slots": {r["name"]: r["filling"] for r in rows
                                   if r["slot_state"] == "FILLED"},
                         "reading": reading, "magnitude": magnitude}
        if missing:
            rec["degraded"] = {"missing": missing, "kept": sorted(rec["usable"]["slots"]),
                               "note": "what is filled is kept and usable; this record is "
                                       "not a PASS and must not be read as one"}
        # ---- numeric bounds on what is filled ----
        for s, row in zip(entry["slots"], rows):
            if row["slot_state"] == "FILLED":
                rec["ranges"] += _range_check(word, s, row["filling"], magnitude,
                                              get("source_path"))
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
        elif missing:
            rec.update(verdict="DEGRADED", status="DERIVED",
                       located_error={"slot": missing[0]["name"],
                                      "rule": missing[0]["reason"]})
        elif any(x in ("MIXED", "UNDECIDED") for x in states):
            r = next(x for x in rec["ranges"] if x["state"] in ("MIXED", "UNDECIDED"))
            rec.update(verdict="UNDECIDED", status="DERIVED",
                       located_error={"slot": r["slot"], "range": r["range"],
                                      "rule": "value straddles the declared bounds",
                                      "bounds": r["bounds"]})
        else:
            rec.update(verdict="PASS", status="DERIVED", pass_equivalent=True)
            if self_scope:
                rec["scope"] = "speaker's own state only"
    except Void as v:
        rec.update(verdict="VOID", void_reason=v.reason, status=None, pass_equivalent=False,
                   located_error={"slot": v.slot} if v.slot else None)
    except Exception as e:                       # fail closed
        rec.update(verdict="VOID", void_reason=f"internal: {type(e).__name__}: {e}",
                   status=None, pass_equivalent=False)
    return rec


def check_all(claims, table, input_path=None, table_path=None):
    entries = claims.get("claims") if isinstance(claims, dict) and "claims" in claims else claims
    if not isinstance(entries, list):
        entries = [entries]
    names = ("PASS", "DEGRADED", "FAIL", "UNDECIDED", "VOID")
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
