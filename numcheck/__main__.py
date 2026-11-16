"""python3 -m numcheck check checks.json [--json] [--fast] [--proposals FILE]

  --fast   skip the interval confirmation when triage gives a prediction: the
           prediction is the verdict, and the record carries rigorous: false.

  --proposals FILE   add the PROPOSED identity candidates of this run to FILE (JSON).
           Entries already in FILE are kept; a candidate with the same lhs, rhs and
           domain is not added twice. Without the flag nothing is written.

Exit: 0 every check HOLDS / BOTH_HOLD | 1 at least one FAILS / ONE_FAILS
      3 none failed, at least one MIXED, UNDECIDED or VOID | 2 usage or unreadable input
"""
import json
import sys
from pathlib import Path

from . import read_json
from .check import check_all


def main(argv):
    if len(argv) < 2 or argv[0] != "check":
        print(__doc__, file=sys.stderr)
        return 2
    try:
        data = read_json(Path(argv[1]).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"cannot read {argv[1]}: {e}", file=sys.stderr)
        return 2
    rep = check_all(data, argv[1], fast="--fast" in argv)
    if "--json" in argv:
        print(json.dumps(rep, indent=1))
    else:
        for r in rep["records"]:
            name = r.get("formula") or " ; ".join(r.get("formulas") or []) or "?"
            line = f"{r['verdict']:9s} {name}"
            if r["verdict"] == "VOID":
                line += f" | {r['void_reason']}"
            else:
                line += f" | tier {r['deciding_tier']} precision {r['precision']}" \
                        f" rigorous {r['rigorous']} | status {r['status']}"
                if r["kind"] == "point" and r["triage"]:
                    t = r["triage"]
                    pred = ", ".join(f"{x['tier']} {x['predicted_verdict']}"
                                     for x in t["predictions"]) or "none"
                    line += f" | predicted: {pred}" + (
                        f" MISMATCH: {t['mismatches']}" if t["mismatches"] else "")
                if r["kind"] == "point" and r.get("bisection"):
                    b = r["bisection"]
                    line += f" | bisected: {b['examined']} looked at, hold {b['hold']} " \
                            f"fail {b['fail']} straddle {b['straddle_at_depth_limit']}: " \
                            f"{b['reading']}"
                    if r["located"]:
                        line += " (" + ", ".join(
                            f"{k} in [{v['approx'][0]:.6g}, {v['approx'][1]:.6g}]"
                            for k, v in r["located"]["subbox"].items()) + ")"
                if r["kind"] == "point" and r["intervals"]:
                    d = r["intervals"]["difference"]["approx"]
                    line += f" | lhs - rhs in [{d[0]:.6g}, {d[1]:.6g}] tol {r['intervals']['tolerance']}"
                if r["kind"] == "intersection":
                    s = r["subboxes"]
                    line += f" | subboxes {s['examined']} both hold {s['both_hold']}" \
                            f" one fails {s['one_fails']}" \
                            f" undecided {s['undecided_at_depth_limit']} deepest {s['deepest']}"
                    if r["located"]:
                        loc = r["located"]
                        box = ", ".join(f"{k} in [{v['approx'][0]:.6g}, {v['approx'][1]:.6g}]"
                                        for k, v in loc["subbox"].items())
                        line += f" | formula {loc['formula_number']} fails on {box}"
            slots = " ".join(f"{k}={v['slot_state']}" for k, v in r["slots"].items())
            print(line + f" | slots: {slots}")
        print({k: v for k, v in rep["counts"].items() if v})
        t = rep["triage"]
        print(f"triage: {t['predictions']} predictions, {t['confirmed']} confirmed, "
              f"{t['mismatches']} mismatched, {t['not_confirmed_fast']} not confirmed (fast)")
        for m in t["mismatch_log"]:
            print(f"  MISMATCH check {m['index']} {m['formula']}: " + ", ".join(
                f"{x['tier']} predicted {x['predicted_verdict']}, confirmed "
                f"{x['confirmed_verdict']}" for x in m["predictions"] if x["match"] is False))
    code = _proposals(rep, argv)
    if code:
        return code
    c = rep["counts"]
    return 1 if c["FAILS"] or c["ONE_FAILS"] else (
        3 if c["VOID"] or c["UNDECIDED"] or c["MIXED"] else 0)


def _proposals(rep, argv):
    found = rep["proposals"]
    quiet = "--json" in argv
    if "--proposals" not in argv:
        if found and not quiet:
            print(f"{len(found)} identity candidate(s), status PROPOSED, not written "
                  "(--proposals FILE writes them)")
        return 0
    try:
        path = Path(argv[argv.index("--proposals") + 1])
    except IndexError:
        print(__doc__, file=sys.stderr)
        return 2
    old = []
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            old = data["proposals"] if isinstance(data, dict) else data
            if not isinstance(old, list):
                raise ValueError("no list of proposals")
        except (OSError, ValueError, KeyError) as e:
            print(f"refused: {path} exists and is not a proposals file ({e})", file=sys.stderr)
            return 2

    def key(p):
        return json.dumps([p.get("lhs"), p.get("rhs"), p.get("domain"), p.get("fixed")],
                          sort_keys=True)
    seen = {key(p) for p in old}
    new = []
    for p in found:
        if key(p) not in seen:
            seen.add(key(p))
            new.append(p)
    path.write_text(json.dumps({
        "note": "identity candidates from numcheck: UNDECIDED at tolerance 0, the two sides "
                "agreeing at every sampled point. PROPOSED; no proof attempted.",
        "status": "PROPOSED", "proposals": old + new}, indent=1) + "\n", encoding="utf-8")
    if not quiet:
        print(f"{len(new)} new identity candidate(s) -> {path} ({len(old)} kept); PROPOSED, "
              "no proof attempted")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
