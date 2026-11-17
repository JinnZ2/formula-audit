"""python3 -m wordslots check claims.json [--table places.json] [--json]

  --table FILE   the place table (default: the PROPOSED example table shipped in
                 wordslots/places.json)

Exit: 0 every claim PASS | 1 at least one FAIL
      3 no FAIL, at least one DEGRADED, VOID or UNDECIDED | 2 usage or unreadable input
"""
import json
import sys
from pathlib import Path

from numcheck import read_json

from .check import check_all

DEFAULT_TABLE = Path(__file__).with_name("places.json")


def main(argv):
    if len(argv) < 2 or argv[0] != "check":
        print(__doc__, file=sys.stderr)
        return 2
    try:
        tpath = Path(argv[argv.index("--table") + 1]) if "--table" in argv else DEFAULT_TABLE
        claims = read_json(Path(argv[1]).read_text(encoding="utf-8"))
        table = read_json(tpath.read_text(encoding="utf-8"))
    except (OSError, ValueError, IndexError) as e:
        print(f"cannot read input: {e}", file=sys.stderr)
        return 2
    rep = check_all(claims, table, argv[1], str(tpath), Path(argv[1]).resolve().parent)
    if "--json" in argv:
        print(json.dumps(rep, indent=1, default=str))
    else:
        for r in rep["records"]:
            line = f"{r['verdict']:9s} {r['word']!s:6s}"
            if r["slots"]:
                line += " " + " ".join(
                    f"{s['name']}={s['slot_state'].lower() if s['slot_state'] != 'VOID' else 'VOID'}"
                    for s in r["slots"])
            if r["verdict"] == "VOID":
                line += f" | {r['void_reason']}"
            elif r["verdict"] == "DEGRADED":
                line += " | missing: " + "; ".join(
                    f"{m['name']}" + (f"[{m['sense']}]" if m.get("sense") else "")
                    + f" ({m['reason']})" for m in r["degraded"]["missing"]) \
                    + " | kept: " + (", ".join(r["degraded"]["kept"]) or "nothing")
            elif r["located_error"] and "range" in r["located_error"]:
                e = r["located_error"]
                line += f" | slot {e['slot']} range {e['range']}: {e['rule']}"
            for g in r["ranges"]:
                line += f" | {g['slot']} {g['range']}: {g['state']}"
            line += (f" | verdict status {r['status']} | claim: {r['evidential'] or 'null'}"
                     f" -> {r['claim_status'] or 'null'}"
                     + (f" ({r['scope']})" if r.get("scope") else "")
                     + f" | class {r.get('word_class') or 'null'} | table entry "
                     f"{r['table_entry_status'] or 'null'}")
            print(line)
        print(rep["counts"])
    c = rep["counts"]
    return 1 if c["FAIL"] else (3 if c["VOID"] or c["UNDECIDED"] or c["DEGRADED"] else 0)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
