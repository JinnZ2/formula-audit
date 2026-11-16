"""check -- a word claims nothing until its slots are filled. Co-authored. v2.

PLACE TABLE (JSON): word -> ordered slots, Lojban-style.
    warm:  x1 what is warm; PHYSICAL: x2 by standard; SOCIAL: x3 to whom, x4 in what behaviour
    safe:  x1 what is safe, x2 from threat (PROTECTED only), x3 for whom
    more:  x1 what is more, x2 than what, x3 in what property, x4 by what amount
  Each slot: name, role, required (true / false), its own status tag,
  source_predicate (the gismu or lujvo its place comes from, or "physics_def"),
  optionally numeric bounds, and optionally senses (the senses it belongs to).
  Each word: status, class (JUDGMENT / COMPARATIVE / EMOTIVE / FEAR, or null),
  shape (the Lojban word it is shaped on), and optionally senses
  {sense: source predicate} with sense_field, the claim field that picks one
  ("reading" for warm, "sense" for safe). lojban "VOID" marks a word the
  reference has no Lojban for (efficient); its slots are physics_def.
  The shapes follow a relayed reference (REFERENCES/lojban_place_structures.json),
  which this build did not re-read. A table entry is PROPOSED until the holder
  of the word confirms it; this checker never changes a tag.
  SENSE: a slot bound to senses is asked for only under one of them. A word
  with sense_field "sense" and no sense given is DEGRADED, naming sense; a
  sense the word does not declare is VOID.

CLAIM RECORD: fixed fields, declared here before any record is read
(COBOL-style: a field that was not declared is an error, not extra data),
each with a width. A value longer than its width, or a number outside its
picture, is VOID ("would truncate"): nothing is ever cut to fit.
    word        X(20)   the word claimed
    slots               {slot name: filling}; a filling is text X(40), or
                        {"text", "value", "unit", "status", "is"}
    reading     X(8)    PHYSICAL / SOCIAL; required for an EMOTIVE word
    sense       X(12)   which sense of the word, where the table declares senses
                        under sense_field "sense" (safe: PROTECTED / NOT_PERILOUS)
    magnitude           {"value": S9(7)V9(4), "unit": X(12)}
    evidential  X(10)   how the claimant knows (below)
    speaker     X(40)   who is making the claim
    oral_record         for ka'u: {shared, multi_gen, checkable, not_central}, each y / n;
                        answered_by X(40), who answered them (required);
                        checkable_ref {file, record, sha256} (optional, re-read)
    source_id   X(40)   who or what the claim comes from (see SOURCE below)
    source_path X(80)   where the claim was found
    table               which table entry status the claimant relied on

EVIDENTIAL -> STATUS of the claim, carried, never upgraded:
    observed  -> OBSERVED     concluded -> DERIVED     defined -> OBSERVED
    hearsay   -> PROPOSED     opinion   -> PROPOSED
    ja'o      -> DERIVED      (Lojban: I conclude)
    su'a      -> PROPOSED     (Lojban: I generalize)
    ba'a      -> PROPOSED     (Lojban: I expect)
    ba'anai   -> OBSERVED     (Lojban: I remember), with provenance {basis: memory}
    ba'acu'i  -> OBSERVED     (Lojban: I experience), self-scoped exactly as se'o
    se'o      -> OBSERVED     (Lojban: I know by internal experience), with
                 scope "speaker's own state only": x1 is filled with the
                 speaker, and the other places are the speaker's own and are
                 waived. se'o on anything external -> DEGRADED.
    ka'u      -> the oral-record discriminator row: four checks fixed by name,
                 shared, multi_gen, checkable, not_central, each y / n.
                 All y -> OBSERVED, with provenance {transmission: oral,
                 multi_generation: true, relay: holder}. Any n -> PROPOSED.
                 A check not answered, another name in the row, no
                 answered_by, or a checkable_ref that does not re-read ->
                 DEGRADED, naming it.            (Lojban: cultural knowledge)
  no evidential given -> the claim's status stays null.
  The glosses are those of the relayed reference; this build did not re-read
  them. The status each one maps to is this tool's rule, not Lojban's.

SOURCE: every claim names where it comes from, by one rule for all routes.
    a written claim (any evidential but se'o, ba'acu'i and ka'u, or none)   source_id
    an oral claim (ka'u)                          oral_record.answered_by
    a self-report (se'o, ba'acu'i)                the speaker, filled in
  The one that applies is required; missing -> DEGRADED, naming it, with the
  same shape whichever route it is (kind "source").

VERDICT (status DERIVED; VOID has none):
    PASS       every required slot filled, nothing undeclared, and every
               numeric bound that was checked holds
    DEGRADED   something required is missing (a slot, the reading of an
               EMOTIVE word, a magnitude, a speaker, a source, an oral-record
               check), or
               se'o is applied to something external. What is filled is kept and usable; each
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
import json
from fractions import Fraction
from pathlib import Path

from infer.ladder import record_sha
from numcheck.check import Bad, check_point, to_interval

VERSION = "wordslots branch4-5"
RECORD_FIELDS = ("word", "slots", "reading", "sense", "magnitude", "evidential", "speaker",
                 "oral_record", "source_id", "source_path", "table")
FILLING_FIELDS = ("text", "value", "unit", "status", "is")
SLOT_FIELDS = ("name", "role", "required", "status", "bounds", "ranges",
               "source_predicate", "senses")
WORD_FIELDS = ("status", "class", "shape", "slots", "magnitude_required_for",
               "senses", "sense_field", "lojban")
SENSE_FIELDS = ("reading", "sense")
STATUS = ("OBSERVED", "DERIVED", "PROPOSED")
CLASSES = ("JUDGMENT", "COMPARATIVE", "EMOTIVE", "FEAR")
READINGS = ("PHYSICAL", "SOCIAL")
EVIDENTIAL = {"observed": "OBSERVED", "concluded": "DERIVED", "hearsay": "PROPOSED",
              "opinion": "PROPOSED", "defined": "OBSERVED",
              "ja'o": "DERIVED", "se'o": "OBSERVED", "ka'u": None,
              "ba'acu'i": "OBSERVED", "ba'anai": "OBSERVED", "ba'a": "PROPOSED",
              "su'a": "PROPOSED"}
SELF_EVIDENTIALS = ("se'o", "ba'acu'i")          # the speaker's own state only
MEMORY_PROVENANCE = {"basis": "memory", "event": "past, as remembered by the speaker"}
SELF_WORDS = ("i", "me", "myself")
WIDTHS = {"word": 20, "slot_text": 40, "reading": 8, "sense": 12, "unit": 12, "evidential": 10,
          "speaker": 40, "source_id": 40, "source_path": 80, "range_name": 20,
          "answered_by": 40}
MAGNITUDE_PIC = {"picture": "S9(7)V9(4)", "integer_digits": 7, "decimal_digits": 4}
ORAL_CHECKS = ("shared", "multi_gen", "checkable", "not_central")
ORAL_EXTRA = ("answered_by", "checkable_ref")
SOURCE_REASON = "no source: {route} claim names where it comes from in {field}"
ORAL_PROVENANCE = {"transmission": "oral", "multi_generation": True, "relay": "holder"}


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
        senses = entry.get("senses")
        field = entry.get("sense_field")
        if (senses is None) != (field is None):
            raise Void(f"place table: word {word!r} declares senses and sense_field together")
        if senses is not None:
            if field not in SENSE_FIELDS:
                raise Void(f"place table: word {word!r}: sense_field is one of "
                           + ", ".join(SENSE_FIELDS))
            if not isinstance(senses, dict) or not senses or any(
                    not isinstance(v, str) or not v.strip() for v in senses.values()):
                raise Void(f"place table: word {word!r}: senses is {{sense: source predicate}}")
            if field == "reading" and any(n not in READINGS for n in senses):
                raise Void(f"place table: word {word!r}: a reading sense is one of "
                           + ", ".join(READINGS))
        if entry.get("lojban") not in (None, "VOID"):
            raise Void(f"place table: word {word!r}: lojban is VOID or absent")
        if entry.get("lojban") == "VOID" and entry.get("shape") is not None:
            raise Void(f"place table: word {word!r}: lojban VOID and a shape together")
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
            src = s.get("source_predicate")
            if not isinstance(src, str) or not src.strip():
                raise Void(f"place table: {word}.{s['name']} has no source_predicate")
            if entry.get("lojban") == "VOID" and src != "physics_def":
                raise Void(f"place table: {word}.{s['name']}: lojban is VOID for {word!r}, "
                           "so its slots are physics_def")
            if s.get("senses") is not None:
                if not isinstance(s["senses"], list) or not s["senses"] \
                        or any(n not in (senses or {}) for n in s["senses"]):
                    raise Void(f"place table: {word}.{s['name']} names a sense the word "
                               "does not declare")
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


def _find_record(report, record):
    """A record of a JSON report by index, label or id. Raises Void."""
    if not isinstance(report, dict):
        raise Void("the file is not a report")
    if isinstance(record, int) and not isinstance(record, bool):
        rows = report.get("records")
        if isinstance(rows, list) and 0 <= record < len(rows):
            return rows[record]
        raise Void(f"no record {record} in the file")
    if isinstance(record, str):
        for part, key in (("theorem_records", "label"), ("records", "id"),
                          ("hypotheses", "id"), ("proposals", "id")):
            for r in report.get(part) or []:
                if isinstance(r, dict) and r.get(key) == record:
                    return r
        raise Void(f"no record {record!r} in the file")
    raise Void("record must be an index or a name")


def read_checkable_ref(ref, base_dir):
    """Re-read the record a checkable_ref names: file opened, record found,
    sha256 compared. Returns the detail; raises Void with the reason."""
    if not isinstance(ref, dict):
        raise Void("checkable_ref is not a {file, record, sha256} record")
    extra = [k for k in ref if k not in ("file", "record", "sha256")]
    if extra:
        raise Void(f"checkable_ref has an undeclared field {extra[0]!r}")
    if not isinstance(ref.get("file"), str) or not isinstance(ref.get("sha256"), str):
        raise Void("checkable_ref needs file and sha256")
    path = Path(ref["file"])
    if not path.is_absolute():
        path = Path(base_dir or ".") / path
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Void(f"cannot read {ref['file']}: {type(e).__name__}")
    rec = _find_record(report, ref.get("record"))
    got = record_sha(rec)
    if got != ref["sha256"].lower():
        raise Void("sha256 mismatch: the record is not the one the reference names")
    return {"state": "RE_READ", "file": ref["file"], "record": ref.get("record"),
            "sha256": got, "verdict_read": rec.get("verdict", rec.get("kernel_verdict"))
            if isinstance(rec, dict) else None,
            "note": "the record exists and is unchanged; whether it bears on the account "
                    "is the claimant's statement"}


def _oral_record(rec_in, base_dir=None):
    """ka'u: the oral-record discriminator row. Four checks fixed by name, each
    y / n; answered_by, who answered them (required); checkable_ref, optional,
    re-read when given. Returns (claim status, detail, problems). A problem is
    a missing check, a missing answered_by, a name that is not declared, or a
    checkable_ref that does not re-read: the claim is then DEGRADED, naming it.
    Raises Void on a malformed record or an answer that is not y / n."""
    if rec_in is None:
        rec_in = {}
    elif not isinstance(rec_in, dict):
        raise Void("oral_record is not a {check: y / n} table")
    answered_by = rec_in.get("answered_by")
    if answered_by is not None and not isinstance(answered_by, str):
        raise Void("oral_record: answered_by is not text")
    fits(answered_by, "answered_by", "oral_record answered_by")
    checks = {n: v for n, v in rec_in.items() if n not in ORAL_EXTRA}
    for name, met in checks.items():
        if met not in ("y", "n"):
            raise Void(f"oral_record: check {name!r} is answered {met!r}, not y or n")
    other = [n for n in checks if n not in ORAL_CHECKS]
    absent = [n for n in ORAL_CHECKS if n not in checks]
    problems = [(n, "oral-record check not answered") for n in absent] \
        + [(n, "not one of the four oral-record checks: " + ", ".join(ORAL_CHECKS))
           for n in other]
    if _empty(answered_by):
        problems.append(("answered_by", "no source"))
    ref_detail = None
    if rec_in.get("checkable_ref") is not None:
        try:
            ref_detail = read_checkable_ref(rec_in["checkable_ref"], base_dir)
        except Void as v:
            ref_detail = {"state": "NOT_RE_READ", "reason": v.reason,
                          "checkable_ref": rec_in["checkable_ref"]}
            problems.append(("checkable_ref", "checkable_ref does not re-read: " + v.reason))
    unmet = [n for n in ORAL_CHECKS if checks.get(n) == "n"]
    all_met = not problems and not unmet
    detail = {"checks": {n: checks.get(n) for n in ORAL_CHECKS}, "all_met": all_met,
              "answered_by": answered_by, "checkable_ref": ref_detail,
              "not_met": unmet, "not_answered": absent, "other_names": other,
              "reason": "all four checks met" if all_met else
              "a check is not met: " + ", ".join(unmet) if unmet and not problems else
              "the discriminator row is incomplete: " + ", ".join(n for n, _ in problems)}
    return ("OBSERVED" if all_met else "PROPOSED"), detail, problems


def check_claim(claim, words, index=None, input_path=None, base_dir=None):
    get = claim.get if isinstance(claim, dict) else (lambda *_: None)
    prov = {"source_path": get("source_path"), "input": input_path, "index": index,
            "tool": VERSION}
    rec = {"word": get("word"), "verdict": "VOID", "void_reason": None,
           "located_error": None, "status": None, "pass_equivalent": False,
           "word_class": None, "shape": None,
           "lojban": None, "sense": None, "sense_field": None, "sense_predicate": None,
           "slots": None, "missing_required": [], "degraded": None, "usable": None,
           "ranges": [], "reading": get("reading"), "magnitude": get("magnitude"),
           "evidential": get("evidential"), "claim_status": None, "claim_provenance": None,
           "scope": None,
           "speaker": get("speaker"), "oral_record": None,
           "source_id": get("source_id"), "source_kind": None, "table_entry_status": None,
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
        for f in ("speaker", "source_id", "source_path", "evidential", "reading", "sense"):
            if claim.get(f) is not None and not isinstance(claim[f], str):
                raise Void(f"{f} is not text")
            fits(claim.get(f), f, f)
        if word not in words:
            raise Void(f"unknown word {word!r}: not in the place table")
        entry = words[word]
        rec.update(table_entry_status=entry["status"], word_class=entry.get("class"),
                   shape=entry.get("shape"), lojban=entry.get("lojban"),
                   sense_field=entry.get("sense_field"))
        ev = claim.get("evidential")
        if ev is not None and ev not in EVIDENTIAL:
            raise Void(f"unknown evidential {ev!r}; one of: " + ", ".join(EVIDENTIAL))
        reading = claim.get("reading")
        if reading is not None and reading not in READINGS:
            raise Void(f"reading {reading!r} is not one of " + ", ".join(READINGS))
        senses, sense_field = entry.get("senses") or {}, entry.get("sense_field")
        if claim.get("sense") is not None and sense_field != "sense":
            raise Void(f"{word!r} has no sense slot" + (
                f": its sense is given in {sense_field}" if sense_field else ""))
        sense = claim.get(sense_field) if sense_field else None
        if sense is not None and sense not in senses:
            raise Void(f"sense {sense!r} is not one of " + ", ".join(senses))
        rec.update(sense=sense, sense_predicate=senses.get(sense))
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
        if ev in SELF_EVIDENTIALS:
            speaker = claim.get("speaker")
            given = filled.get(x1)
            text = (given.get("text") if isinstance(given, dict) else given) or ""
            rec["claim_status"] = "OBSERVED"
            rec["scope"] = "speaker's own state only"
            if _empty(speaker):
                lack("speaker", "field", f"{ev} reports the speaker's own state and no "
                                         "speaker is given")
            elif _empty(given):
                filled = dict(filled, **{x1: speaker})          # auto-filled
                rec["x1_auto_filled"] = True
                self_scope = True
            elif text.strip().lower() in SELF_WORDS or text.strip() == speaker.strip():
                self_scope = True
            else:
                lack(x1, "scope", f"{ev} covers the speaker's own state only; {x1} is "
                                  f"{text.strip()!r}, not the speaker: an assessment of "
                                  "something external needs another evidential",
                     entry["slots"][0].get("role"))
        elif ev == "ka'u":
            rec["claim_status"], rec["oral_record"], problems = \
                _oral_record(claim.get("oral_record"), base_dir)
            for name, reason in problems:
                if name == "answered_by":
                    lack(name, "source", SOURCE_REASON.format(
                        route="an oral", field="oral_record.answered_by"))
                else:
                    lack(name, "oral_record", reason)
            rec["source_kind"] = "oral"
            rec["source_id"] = rec["oral_record"]["answered_by"] or claim.get("source_id")
            if rec["claim_status"] == "OBSERVED":
                rec["claim_provenance"] = dict(ORAL_PROVENANCE,
                                               answered_by=rec["oral_record"]["answered_by"])
        elif ev is not None:
            rec["claim_status"] = EVIDENTIAL[ev]              # carried as mapped, never upgraded
            if ev == "ba'anai":
                rec["claim_provenance"] = dict(MEMORY_PROVENANCE)
        if ev != "ka'u" and claim.get("oral_record") is not None:
            raise Void("oral_record is for the evidential ka'u only")
        if ev in SELF_EVIDENTIALS:
            rec["source_kind"] = "self"                    # the source is the speaker
            if _empty(claim.get("source_id")) and not _empty(claim.get("speaker")):
                rec["source_id"] = claim["speaker"]
                rec["source_auto_filled"] = True
        elif ev != "ka'u":
            rec["source_kind"] = "written"
            if _empty(claim.get("source_id")):
                lack("source_id", "source", SOURCE_REASON.format(
                    route="a written", field="source_id"))

        # ---- slots ----
        rows = []
        for s in entry["slots"]:
            f = filled.get(s["name"])
            empty = _empty(f)
            state = "VOID" if empty else "FILLED"
            in_sense = None if s.get("senses") is None else \
                None if sense is None else sense in s["senses"]
            # a slot bound to senses is asked for only under one of them; with the
            # sense not given, the sense itself is what is missing
            asked = s["required"] and (s.get("senses") is None or in_sense is True)
            if empty and asked:
                if self_scope and s["name"] != x1:
                    state = "WAIVED"
                    waived.append(s["name"])
                else:
                    lack(s["name"], "slot", "required slot empty", s.get("role"))
            rows.append({"name": s["name"], "role": s.get("role"), "required": s["required"],
                         "source_predicate": s["source_predicate"],
                         "senses": s.get("senses"), "in_sense": in_sense,
                         "slot_status": s["status"], "slot_state": state,
                         "filling": None if empty else f})
        if entry.get("class") == "EMOTIVE" and reading is None:
            if self_scope:
                waived.append("reading")
            else:
                lack("reading", "field", "an EMOTIVE word needs its reading: PHYSICAL or SOCIAL")
        if sense_field == "sense" and sense is None:
            if self_scope:
                waived.append("sense")
            else:
                lack("sense", "field", f"{word!r} needs its sense: " + " or ".join(senses))
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


def check_all(claims, table, input_path=None, table_path=None, base_dir=None):
    entries = claims.get("claims") if isinstance(claims, dict) and "claims" in claims else claims
    if not isinstance(entries, list):
        entries = [entries]
    names = ("PASS", "DEGRADED", "FAIL", "UNDECIDED", "VOID")
    try:
        words = read_table(table)
        records = [check_claim(c, words, i, input_path, base_dir)
                   for i, c in enumerate(entries)]
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
