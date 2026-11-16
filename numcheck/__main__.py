"""python3 -m numcheck check checks.json [--json]

Exit: 0 every check HOLDS / BOTH_HOLD | 1 at least one FAILS / ONE_FAILS
      3 none failed, at least one VOID or UNDECIDED | 2 usage or unreadable input
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
    rep = check_all(data, argv[1])
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
                if r["kind"] == "point" and r["intervals"]:
                    d = r["intervals"]["difference"]["approx"]
                    line += f" | lhs - rhs in [{d[0]:.6g}, {d[1]:.6g}] tol {r['intervals']['tolerance']}"
                if r["kind"] == "intersection":
                    s = r["subboxes"]
                    line += f" | subboxes {s['examined']} both hold {s['both_hold']}" \
                            f" undecided {s['undecided_at_depth_limit']} deepest {s['deepest']}"
                    if r["located"]:
                        loc = r["located"]
                        box = ", ".join(f"{k} in [{v['approx'][0]:.6g}, {v['approx'][1]:.6g}]"
                                        for k, v in loc["subbox"].items())
                        line += f" | formula {loc['formula_number']} fails on {box}"
            slots = " ".join(f"{k}={v['slot_state']}" for k, v in r["slots"].items())
            print(line + f" | slots: {slots}")
        print({k: v for k, v in rep["counts"].items() if v})
    c = rep["counts"]
    return 1 if c["FAILS"] or c["ONE_FAILS"] else (3 if c["VOID"] or c["UNDECIDED"] else 0)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
