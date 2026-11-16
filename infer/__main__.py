"""python3 -m infer rank case.json [--json] [--log FILE]
python3 -m infer ref 2a|2b REPORT.json RECORD

  ref   prints the check_ref for one record of a branch 2a / 2b JSON report (RECORD: the
        record's index for 2b; the theorem label or entry id for 2a), with its sha256.
        A file named by a check_ref is looked for beside the case file.

  --log FILE   write the update log to FILE (refused if FILE exists)

Exit: 0 ranked, every evidence record usable | 3 the case is VOID, or an evidence
      record is VOID | 2 usage or unreadable input.  (1 is not used: nothing here FAILS.)
"""
import json
import sys
from pathlib import Path

from .ladder import rank, read_json


def ref_main(argv):
    from .ladder import Void, find_record, record_sha
    if len(argv) != 4 or argv[1] not in ("2a", "2b"):
        print(__doc__, file=sys.stderr)
        return 2
    try:
        report = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
        record = int(argv[3]) if argv[1] == "2b" else argv[3]
        rec, verdict, _ = find_record(report, argv[1], record)
    except (OSError, ValueError, Void) as e:
        print(f"cannot make a check_ref: {e}", file=sys.stderr)
        return 2
    print(json.dumps({"branch": argv[1], "file": argv[2], "record": record,
                      "sha256": record_sha(rec)}))
    print(f"(the record's verdict is {verdict})", file=sys.stderr)
    return 0


def main(argv):
    if argv and argv[0] == "ref":
        return ref_main(argv)
    if len(argv) < 2 or argv[0] != "rank":
        print(__doc__, file=sys.stderr)
        return 2
    try:
        case = read_json(Path(argv[1]).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"cannot read {argv[1]}: {e}", file=sys.stderr)
        return 2
    rep = rank(case, base_dir=Path(argv[1]).resolve().parent)
    if "--log" in argv:
        try:
            out = Path(argv[argv.index("--log") + 1])
        except IndexError:
            print(__doc__, file=sys.stderr)
            return 2
        if out.exists():
            print(f"refused: {out} exists", file=sys.stderr)
            return 2
        out.write_text(json.dumps({"tool": rep["tool"], "log": rep["log"]}, indent=1) + "\n",
                       encoding="utf-8")
    if "--json" in argv:
        print(json.dumps(rep, indent=1))
    elif rep["verdict"] == "VOID":
        print(f"VOID {rep['void_reason']}")
    else:
        c = rep["caps"]
        print(f"caps (PROPOSED): shadow {c['shadow']}, cross_domain {c['cross_domain']}")
        for step in rep["log"]:
            if step["op"] in ("PRIOR", "FLAT_PRIOR"):
                print(f"{step['op']:10s} {step['reason']}")
        for e in rep["evidence"]:
            print(f"{e['outcome']:10s} {e['id']:14s} {e['type'] or '?':12s} "
                  + (f"lr {e['lr_given']}" + (f" -> {e['lr_effective']}"
                                              if e["lr_effective"] not in (None, e["lr_given"])
                                              else "")
                     + f" on {', '.join(e['targets'])}" if e["targets"] else "")
                  + (f" | {e['reason']}" if e["reason"] else "")
                  + ("" if e["counts_now"] or e["outcome"] != "APPLY" else " | no longer counts"))
        for h in rep["ranking"]:
            x = next(y for y in rep["hypotheses"] if y["id"] == h["id"])
            print(f"  {h['id']:14s} posterior {h['posterior']:>12s} (~{x['posterior_approx']:.4f}) "
                  f"{h['direction']:9s} status {h['status']} | {x['direction_reason']}"
                  + "".join(f" | check {c['evidence']}: {c['state']} ({c['reason']})"
                            for c in x["checks"]))
        print(rep["counts"], "| replay from the log matches:", rep["replay_matches"])
    return 3 if rep["verdict"] == "VOID" or rep["counts"]["VOID"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
