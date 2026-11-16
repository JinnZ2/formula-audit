"""python3 -m glyph step case.json [--steps N] [--json] [--dry-run]
python3 -m glyph ref BRANCH REPORT.json RECORD [AT]

  step   run N steps (default 1). Candidates go to proposals.json beside the case
         (or the file the case names). --dry-run writes nothing.
  ref    print the environment reference of one record of a branch report
         (BRANCH 1 2a 2b 4 5; RECORD: index, label or id), with its sha256.

Exit: 0 every step done | 3 a step is VOID | 2 usage or unreadable input
"""
import json
import sys
from pathlib import Path

from infer.ladder import Void, read_json, record_sha

from .environment import read_record
from .operator import run


def ref_main(argv):
    if len(argv) not in (4, 5):
        print(__doc__, file=sys.stderr)
        return 2
    try:
        report = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
        record = int(argv[3]) if argv[1] in ("1", "2b", "4") else argv[3]
        rec = read_record(report, argv[1], record)
    except (OSError, ValueError, Void) as e:
        print(f"cannot make a reference: {e}", file=sys.stderr)
        return 2
    print(json.dumps({"branch": argv[1], "file": argv[2], "record": record,
                      "sha256": record_sha(rec), "at": argv[4] if len(argv) == 5 else None}))
    return 0


def main(argv):
    if argv and argv[0] == "ref":
        return ref_main(argv)
    if len(argv) < 2 or argv[0] != "step":
        print(__doc__, file=sys.stderr)
        return 2
    try:
        steps = int(argv[argv.index("--steps") + 1]) if "--steps" in argv else 1
        if steps < 1:
            raise ValueError
        case = read_json(Path(argv[1]).read_text(encoding="utf-8"))
    except (OSError, ValueError, IndexError) as e:
        print(f"cannot run: {e}", file=sys.stderr)
        return 2
    rep = run(case, Path(argv[1]).resolve().parent, steps, write="--dry-run" not in argv)
    if "--json" in argv:
        print(json.dumps(rep, indent=1))
    else:
        for e in rep["log"]:
            if e["verdict"] == "INIT":
                continue
            if e["verdict"] == "VOID":
                print(f"step {e['step']}: VOID {e['void_reason']}")
                continue
            print(f"step {e['step']}: {e['mode']} ({e['gate']['gate']})")
            used = e["options"][-1].get("default_rate_used_for")
            if used:
                print(f"   FLAG   default drift rate used for environment references {used}")
            for o in e["options"]:
                print(f"   option {o['name']:20s} cost {o['cost']:>6s} "
                      + ("open" if o["open"] else f"closed: {o['why_not']}"))
            for r in e["rivals"]:
                if r.get("score") is None:
                    continue
                if r.get("kind") == "inaction":
                    print(f"   rival  {r['name']:20s} - drift {r['cost']} = {r['score']}")
                else:
                    print(f"   rival  {r['name']:20s} posterior {r['posterior']} x gain "
                          f"{r['gain']} - cost {r['cost']} = {r['score']}")
            c = e["candidate"]
            print(f"   chosen {e['chosen']} ({e['choice_reason']})" + (
                f" -> {c['kind']} {c['key']} in {c['written_to']}, status {c['status']}, "
                f"tag {c['tag']}" if c else ""))
            m = e.get("margin") or {}
            if m.get("margin_required"):
                print(f"   FLAG   margin_required: {m['reason']}: "
                      + ", ".join(m["void_slots"]))
            s = e["state_after"]
            print(f"   state  energy {s['energy_available']} time {s['time_available']} "
                  f"now {s['now']}")
        if rep["verdict"] == "VOID" and not rep["log"]:
            print(f"VOID {rep['void_reason']}")
        print(f"{rep['verdict']}: {rep.get('steps_done', 0)} of {rep['steps_asked']} steps; "
              f"ceiling: {rep['ceiling']}; replay: "
              f"{(rep.get('replay') or {}).get('verdict')}"
              f" ({(rep.get('replay') or {}).get('infer_logs_rerun')} branch 5 logs run again)")
    return 0 if rep["verdict"] == "STEPPED" else 3


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
