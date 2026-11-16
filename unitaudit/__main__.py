"""python3 -m unitaudit check formulas.json [--json]
python3 -m unitaudit scan PATH [-o draft.json]

Exit: 0 every formula PASS | 1 at least one FAIL | 3 no FAIL, at least one VOID
      2 usage, unreadable input, or an output path that already exists
"""
import json
import sys
from pathlib import Path

from .check import check_all
from .scan import scan


def main(argv):
    if len(argv) < 2 or argv[0] not in ("check", "scan"):
        print(__doc__, file=sys.stderr)
        return 2
    if argv[0] == "scan":
        draft = scan(argv[1])
        text = json.dumps(draft, indent=1, ensure_ascii=False)
        if "-o" in argv:
            out = Path(argv[argv.index("-o") + 1])
            if out.exists():
                print(f"refused: {out} exists", file=sys.stderr)
                return 2
            out.write_text(text + "\n", encoding="utf-8")
            print(f"{len(draft['formulas'])} draft entries (PROPOSED) -> {out}")
        else:
            print(text)
        return 0
    try:
        data = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"cannot read {argv[1]}: {e}", file=sys.stderr)
        return 2
    report = check_all(data, argv[1])
    if "--json" in argv:
        print(json.dumps(report, indent=1, ensure_ascii=False))
    else:
        for r in report["records"]:
            d = r["dims"]
            line = f"{r['verdict']:4s} {r['formula']!s:28s}"
            if r["verdict"] == "PASS":
                line += f" [{d['lhs']['text']}]"
            elif r["verdict"] == "FAIL":
                e = r["located_error"]
                line += (f" at {e['side']} col {e['col']} `{e['text']}`: {e['rule']}: "
                         + " vs ".join(f"[{x}]" for x in e["dims"]))
            else:
                line += f" {r['void_reason']}"
            slots = " ".join(f"{k}={v['slot_state']}" for k, v in r["slots"].items())
            tags = "" if not r["symbols"] else " | units: " + " ".join(
                f"{k}:{v['status'] or 'null'}" for k, v in r["symbols"].items())
            print(line + f" | verdict status {r['status']}{tags} | slots: {slots}")
        print(report["counts"])
    c = report["counts"]
    return 1 if c["FAIL"] else (3 if c["VOID"] else 0)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
