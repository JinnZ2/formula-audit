"""check -- data points and intersections. Co-authored.

Units first: every formula goes through branch 1 (unitaudit). Unless that
verdict is PASS, the numeric check is VOID with branch 1's reason.

A data point: "lhs = rhs", a value per symbol (a number, or an interval
[lo, hi]; with its unit and its own status tag) and a tolerance t >= 0.
With D an enclosure of lhs - rhs:
  HOLDS      D lies inside [-t, t]
  FAILS      D lies wholly outside [-t, t]
  UNDECIDED  D straddles the edge at the last tier
  VOID       units not PASS, a missing or unreadable value, no value on
             these inputs (division by an interval containing 0, ...),
             unsupported syntax, internal error
The verdict comes from the interval tier: Fraction intervals, with sqrt exp
ln sin cos as outward enclosures (precision doubling up to max_precision
when one was used). It is the only rigorous tier. float and Decimal run
first as TRIAGE: each gives a predicted_verdict or says "too close to
call". Every HOLDS / FAILS is confirmed at the interval tier, and the record
sets predicted beside confirmed; a mismatch is listed on the record and
counted in the report. The margin rule behind a prediction is a heuristic
with no bound over a long chain of steps, so a prediction is never the
verdict, unless the check asks for fast (entry "fast": true, or --fast):
then confirmation is skipped, the prediction is the verdict, and the record
carries rigorous: false.

A straddle on interval inputs is bisected (the inputs are split, widest
first, to the depth limit) before UNDECIDED is given:
  every piece HOLDS                          -> HOLDS
  a piece where it fails at every point      -> FAILS, with that piece located
                                                (it may hold on other pieces)
  pieces still straddling at the depth limit -> UNDECIDED

An intersection: two formulas and a region (a box: an interval per region
variable). On a subbox, both formulas HOLD (enclosure inside tolerance:
true at every point of the subbox), or one FAILS (enclosure outside: false
at every point of it), or the subbox is bisected along its widest side, to
a depth limit.
  BOTH_HOLD   every subbox reached: both hold
  ONE_FAILS   a subbox on which one formula fails everywhere (located)
  UNDECIDED   neither, at the depth limit
  VOID        as above; or a subbox with no value at the depth limit
"""
import ast
from decimal import Decimal
from fractions import Fraction

from unitaudit.check import check_formula as unit_check
from unitaudit.check import slot_record, split_sides, Void as UnitVoid, STATUS

from .interval import Interval
from .tiers import DecSys, FloatSys, IntSys, NumVoid, TierCannot, evaluate

VERSION = "numcheck branch2b-2"
DEFAULTS = {"decimal_precision": 50, "precision": 30, "max_precision": 120, "depth": 8}
MAX_SUBBOXES = 20000


class Bad(Exception):
    pass


def to_fraction(x, what):
    if isinstance(x, bool) or x is None:
        raise Bad(f"{what}: not a number")
    if isinstance(x, (int, Fraction)):
        return Fraction(x)
    if isinstance(x, Decimal):
        if not x.is_finite():
            raise Bad(f"{what}: not finite")
        return Fraction(x)
    if isinstance(x, float):
        raise Bad(f"{what}: a binary float reached the checker; give numbers as JSON "
                  "numbers read with read_json, or as strings")
    if isinstance(x, str):
        try:
            return Fraction(x.strip())
        except (ValueError, ZeroDivisionError):
            raise Bad(f"{what}: cannot read {x!r} as a number")
    raise Bad(f"{what}: not a number")


def to_interval(v, what):
    if isinstance(v, dict) and ("lo" in v or "hi" in v):
        v = [v.get("lo"), v.get("hi")]
    if isinstance(v, (list, tuple)):
        if len(v) != 2:
            raise Bad(f"{what}: an interval needs two bounds")
        lo, hi = to_fraction(v[0], what), to_fraction(v[1], what)
        if lo > hi:
            raise Bad(f"{what}: interval bounds out of order")
        return Interval(lo, hi)
    return Interval(to_fraction(v, what))


def _blank(kind, entry, index, input_path):
    get = entry.get if isinstance(entry, dict) else (lambda *_: None)
    return {"kind": kind, "verdict": "VOID", "void_reason": None, "status": None,
            "deciding_tier": None, "precision": None, "rigorous": None, "fast": None,
            "tiers": [], "triage": None, "located": None,
            "intervals": None, "inputs": None, "units": None,
            "provenance": {"source_path": get("source_path"), "input": input_path,
                           "index": index, "tool": VERSION},
            "slots": slot_record(get("slots")),
            "human_interest": None, "ai_interest": None}


def _units(formula, values):
    """Branch 1 on the formula. Returns (record summary, reason or None)."""
    symbols = {}
    for name, spec in (values or {}).items():
        symbols[name] = {"unit": spec.get("unit"), "status": spec.get("status")} \
            if isinstance(spec, dict) else {"unit": None}
    r = unit_check({"formula": formula, "symbols": symbols})
    summary = {"verdict": r["verdict"], "status": r["status"], "dims": r["dims"],
               "located_error": r["located_error"], "void_reason": r["void_reason"]}
    if r["verdict"] == "PASS":
        return summary, None
    if r["verdict"] == "FAIL":
        e = r["located_error"]
        return summary, (f"units FAIL: {e['rule']}: " + " vs ".join(e["dims"])
                         + (f" at `{e['text']}`" if e.get("text") else ""))
    return summary, f"units VOID: {r['void_reason']}"


def _parse(formula):
    try:
        lhs, rhs = (s.strip() for s in split_sides(formula))
    except UnitVoid as e:
        raise Bad(e.reason)
    try:
        return (lhs, ast.parse(lhs, mode="eval").body), (rhs, ast.parse(rhs, mode="eval").body)
    except SyntaxError as e:
        raise Bad(f"formula does not parse: {e.msg}")


def _names(tree):
    funcs = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Name)}
    return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} - funcs


def _inputs(values, needed, region=None):
    """name -> Interval, and the input records (each keeps its own tag)."""
    env, recs = {}, {}
    region = region or {}
    for name in sorted(needed):
        spec = values.get(name) if isinstance(values, dict) else None
        if not isinstance(spec, dict):
            raise Bad(f"no value given for symbol {name!r}")
        status = spec.get("status")
        if status is not None and status not in STATUS:
            raise Bad(f"symbol {name!r}: status {status!r} is not one of {', '.join(STATUS)}")
        if name in region:
            iv = to_interval(region[name], f"region {name!r}")
        elif spec.get("value") is None:
            raise Bad(f"no value given for symbol {name!r}")
        else:
            iv = to_interval(spec["value"], f"value of {name!r}")
        env[name] = iv
        recs[name] = {"value": iv.as_record(), "unit": spec.get("unit"), "status": status,
                      "from_region": name in region}
    return env, recs


def _difference(sides, env, S):
    senv = {k: (v if S.name == "interval" else S.const(v.lo)) for k, v in env.items()}
    (ls, lt), (rs, rt) = sides
    lhs = evaluate(lt, ls, senv, S)
    rhs = evaluate(rt, rs, senv, S)
    return lhs, rhs, S.sub(lhs, rhs)


def _bisect_point(sides, tol, env, prec, depth_limit):
    """A straddle on interval inputs: split the inputs (widest first) and look
    again. The enclosure of x*x - x**2 on a wide x is wide only because x is
    counted twice; on narrow pieces it closes. Returns (verdict or None, detail).
      a piece on which the formula fails at every point -> FAILS, located
      every piece HOLDS                                 -> HOLDS
      pieces still straddling at the depth limit        -> None (UNDECIDED)"""
    if depth_limit < 0 or 2 ** depth_limit > MAX_SUBBOXES:
        raise Bad(f"depth must be between 0 and {MAX_SUBBOXES.bit_length() - 1}")
    names = sorted(n for n, v in env.items() if not v.is_point)
    stack = [({n: env[n] for n in names}, 0)]
    counts = {"examined": 0, "hold": 0, "straddle_at_depth_limit": 0}
    deepest, first_open, located = 0, None, None
    while stack and located is None:
        box, depth = stack.pop()
        counts["examined"] += 1
        deepest = max(deepest, depth)
        _, _, d = _difference(sides, dict(env, **box), IntSys(prec))
        v, _ = IntSys(prec).judge(d, tol)
        sub = {n: box[n].as_record() for n in names}
        if v == "HOLDS":
            counts["hold"] += 1
        elif v == "FAILS":
            located = {"subbox": sub, "depth": depth, "difference": d.as_record(),
                       "tolerance": str(tol)}
        elif depth >= depth_limit:
            counts["straddle_at_depth_limit"] += 1
            first_open = first_open or {"subbox": sub, "difference": d.as_record()}
        else:
            widest = max(names, key=lambda n: box[n].width)
            a, b = box[widest].split()
            stack.append((dict(box, **{widest: b}), depth + 1))
            stack.append((dict(box, **{widest: a}), depth + 1))
    verdict = "FAILS" if located else (None if counts["straddle_at_depth_limit"] else "HOLDS")
    return verdict, {**counts, "depth_limit": depth_limit, "deepest": deepest,
                     "variables_split": names,
                     "stopped_at_first_failure": located is not None,
                     "holds_elsewhere": bool(located and counts["hold"]),
                     "reading": ("fails at every point of the located piece of the inputs"
                                 + ("; holds on other pieces" if located and counts["hold"]
                                    else "") if located else
                                 "holds on every piece" if verdict else
                                 "pieces still straddle at the depth limit"),
                     "located": located, "first_straddling_piece": first_open}


def check_point(entry, index=None, input_path=None, fast=False):
    rec = _blank("point", entry, index, input_path)
    try:
        if not isinstance(entry, dict) or not isinstance(entry.get("formula"), str):
            raise Bad("no formula string")
        formula = entry["formula"]
        rec["formula"] = formula
        rec["units"], reason = _units(formula, entry.get("values"))
        if reason:
            raise Bad(reason)
        sides = _parse(formula)
        tol = to_fraction(entry.get("tolerance", 0), "tolerance")
        if tol < 0:
            raise Bad("tolerance is negative")
        env, rec["inputs"] = _inputs(entry.get("values"),
                                     _names(sides[0][1]) | _names(sides[1][1]))
        opt = {k: entry.get(k, d) for k, d in DEFAULTS.items()}
        fast = bool(entry.get("fast", fast))
        rec["fast"] = fast
        points = all(v.is_point for v in env.values())
        tiers = rec["tiers"]
        verdict = None
        # float and Decimal are TRIAGE: each predicts the verdict or says "too close
        # to call". Neither is an enclosure. They decide only under fast.
        for S in (FloatSys(), DecSys(int(opt["decimal_precision"]))):
            if not points:
                tiers.append({"tier": S.name, "role": "triage", "outcome": "skipped",
                              "predicted_verdict": None, "reason": "an input is an interval"})
                continue
            guess = None
            try:
                _, _, d = _difference(sides, env, S)
                guess, detail = S.judge(d, tol)
                tiers.append({"tier": S.name, "role": "triage", "precision": S.precision,
                              "outcome": "predicts" if guess else "too close to call",
                              "predicted_verdict": guess,
                              **{k: (v if isinstance(v, str) else repr(v))
                                 for k, v in detail.items()}})
            except (TierCannot, NumVoid) as e:
                tiers.append({"tier": S.name, "role": "triage", "precision": S.precision,
                              "outcome": "cannot run", "predicted_verdict": None, "reason": str(e)})
            if guess and fast:
                verdict = guess
                tiers[-1]["role"] = "decided (fast)"
                rec.update(verdict=verdict, deciding_tier=S.name, precision=S.precision,
                           rigorous=False, status="DERIVED")
                break
        if not verdict:
            prec = int(opt["precision"])
            while True:
                S = IntSys(prec)
                lhs, rhs, d = _difference(sides, env, S)
                verdict, _ = S.judge(d, tol)
                exact = not S.used_enclosure
                tiers.append({"tier": "interval", "role": "confirms", "predicted_verdict": None,
                              "precision": "exact" if exact else prec,
                              "outcome": "decided" if verdict else "straddles the tolerance edge"})
                rec["intervals"] = {"lhs": lhs.as_record(), "rhs": rhs.as_record(),
                                    "difference": d.as_record(), "tolerance": str(tol)}
                if verdict or exact or prec * 2 > int(opt["max_precision"]):
                    break
                prec *= 2
            rec["bisection"] = None
            if not verdict and not points:
                verdict, rec["bisection"] = _bisect_point(sides, tol, env, prec,
                                                          int(opt["depth"]))
                rec["located"] = rec["bisection"]["located"]
            rec.update(verdict=verdict or "UNDECIDED", deciding_tier="interval",
                       precision="exact" if exact else prec, rigorous=True, status="DERIVED")
        confirmed = rec["verdict"] if rec["rigorous"] else None
        per_tier = [{"tier": t["tier"], "predicted_verdict": t["predicted_verdict"],
                     "confirmed_verdict": confirmed,
                     "match": None if confirmed is None else t["predicted_verdict"] == confirmed}
                    for t in tiers if t.get("predicted_verdict")]
        rec["triage"] = {"predictions": per_tier,
                         "confirmed_verdict": confirmed,
                         "confirmed_at": "interval" if confirmed else None,
                         "mismatches": [x["tier"] for x in per_tier if x["match"] is False],
                         "note": None if confirmed else
                         "fast: the prediction was taken as the verdict, not confirmed"}
    except (Bad, NumVoid) as e:
        rec.update(verdict="VOID", void_reason=str(e), status=None)
    except Exception as e:                       # fail closed
        rec.update(verdict="VOID", void_reason=f"internal: {type(e).__name__}: {e}", status=None)
    return rec


def check_intersection(entry, index=None, input_path=None):
    rec = _blank("intersection", entry, index, input_path)
    try:
        forms = entry.get("formulas") if isinstance(entry, dict) else None
        if not isinstance(forms, list) or len(forms) != 2:
            raise Bad("an intersection needs exactly two formulas")
        region = entry.get("region")
        if not isinstance(region, dict) or not region:
            raise Bad("an intersection needs a region: {variable: [lo, hi]}")
        values = entry.get("values")
        parsed, rec["units"], rec["formulas"] = [], [], []
        needed = set()
        for i, f in enumerate(forms):
            if not isinstance(f, dict) or not isinstance(f.get("formula"), str):
                raise Bad(f"formula {i + 1}: no formula string")
            u, reason = _units(f["formula"], values)
            rec["units"].append(u)
            rec["formulas"].append(f["formula"])
            if reason:
                raise Bad(f"formula {i + 1}: {reason}")
            sides = _parse(f["formula"])
            tol = to_fraction(f.get("tolerance", 0), f"tolerance {i + 1}")
            if tol < 0:
                raise Bad(f"tolerance {i + 1} is negative")
            parsed.append((sides, tol))
            needed |= _names(sides[0][1]) | _names(sides[1][1])
        for name in region:
            if name not in needed:
                raise Bad(f"region variable {name!r} is in neither formula")
        env, rec["inputs"] = _inputs(values, needed, region)
        prec = int(entry.get("precision", DEFAULTS["precision"]))
        depth_limit = int(entry.get("depth", DEFAULTS["depth"]))
        if depth_limit < 0 or 2 ** depth_limit > MAX_SUBBOXES:
            raise Bad(f"depth must be between 0 and {MAX_SUBBOXES.bit_length() - 1}")
        names = sorted(region)
        stack = [({n: env[n] for n in names}, 0)]
        counts = {"examined": 0, "both_hold": 0, "undecided_at_depth_limit": 0,
                  "no_value_at_depth_limit": 0}
        located, first_open, first_void, deepest = None, None, None, 0
        while stack and located is None:
            box, depth = stack.pop()
            counts["examined"] += 1
            deepest = max(deepest, depth)
            cur = dict(env, **box)
            state, void_reason, diffs = [], None, []
            for sides, tol in parsed:
                S = IntSys(prec)
                try:
                    _, _, d = _difference(sides, cur, S)
                    state.append(S.judge(d, tol)[0])
                    diffs.append(d.as_record())
                except NumVoid as e:
                    state.append("VOID")
                    diffs.append(None)
                    void_reason = str(e)
            sub = {n: box[n].as_record() for n in names}
            if "FAILS" in state:
                i = state.index("FAILS")
                located = {"subbox": sub, "depth": depth, "formula_number": i + 1,
                           "formula": rec["formulas"][i], "difference": diffs[i],
                           "tolerance": str(parsed[i][1]),
                           "other_formula_on_this_subbox": state[1 - i]}
            elif state == ["HOLDS", "HOLDS"]:
                counts["both_hold"] += 1
            elif depth >= depth_limit:
                if void_reason:
                    counts["no_value_at_depth_limit"] += 1
                    first_void = first_void or {"subbox": sub, "depth": depth,
                                                "reason": void_reason}
                else:
                    counts["undecided_at_depth_limit"] += 1
                    first_open = first_open or {"subbox": sub, "depth": depth,
                                                "states": state, "differences": diffs}
            else:
                widest = max(names, key=lambda n: box[n].width)
                if box[widest].width == 0:
                    counts["undecided_at_depth_limit"] += 1
                    first_open = first_open or {"subbox": sub, "depth": depth, "states": state,
                                                "differences": diffs}
                    continue
                a, b = box[widest].split()
                stack.append((dict(box, **{widest: b}), depth + 1))
                stack.append((dict(box, **{widest: a}), depth + 1))
        rec["subboxes"] = {**counts, "depth_limit": depth_limit, "deepest": deepest,
                           "stopped_at_first_failure": located is not None}
        rec["located"] = located
        rec["first_undecided_subbox"] = first_open
        rec["first_subbox_with_no_value"] = first_void
        rec.update(deciding_tier="interval", precision=prec, rigorous=True)
        if located:
            rec.update(verdict="ONE_FAILS", status="DERIVED")
        elif counts["no_value_at_depth_limit"]:
            rec.update(verdict="VOID", status=None,
                       void_reason="no value on a subbox at the depth limit: "
                                   + first_void["reason"])
        elif counts["undecided_at_depth_limit"]:
            rec.update(verdict="UNDECIDED", status="DERIVED")
        else:
            rec.update(verdict="BOTH_HOLD", status="DERIVED")
    except (Bad, NumVoid) as e:
        rec.update(verdict="VOID", void_reason=str(e), status=None)
    except Exception as e:                       # fail closed
        rec.update(verdict="VOID", void_reason=f"internal: {type(e).__name__}: {e}", status=None)
    return rec


def check_all(data, input_path=None, fast=False):
    entries = data.get("checks") if isinstance(data, dict) and "checks" in data else data
    if not isinstance(entries, list):
        entries = [entries]
    records = []
    for i, e in enumerate(entries):
        kind = e.get("kind", "point") if isinstance(e, dict) else "point"
        if kind == "intersection":
            records.append(check_intersection(e, i, input_path))
        elif kind == "point":
            records.append(check_point(e, i, input_path, fast))
        else:
            r = _blank(str(kind), e, i, input_path)
            r["void_reason"] = f"unknown kind {kind!r}"
            records.append(r)
    names = ("HOLDS", "FAILS", "UNDECIDED", "VOID", "BOTH_HOLD", "ONE_FAILS")
    tri = [r["triage"] for r in records if r.get("triage")]
    return {"tool": VERSION, "input": input_path, "fast": fast,
            "counts": {v: sum(1 for r in records if r["verdict"] == v) for v in names},
            "triage": {"predictions": sum(len(t["predictions"]) for t in tri),
                       "confirmed": sum(1 for t in tri for x in t["predictions"]
                                        if x["match"] is True),
                       "mismatches": sum(len(t["mismatches"]) for t in tri),
                       "not_confirmed_fast": sum(1 for t in tri for x in t["predictions"]
                                                 if x["match"] is None),
                       "mismatch_log": [{"index": r["provenance"]["index"],
                                         "formula": r.get("formula"),
                                         "tiers": r["triage"]["mismatches"],
                                         "predictions": r["triage"]["predictions"]}
                                        for r in records
                                        if r.get("triage") and r["triage"]["mismatches"]]},
            "records": records}
