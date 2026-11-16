"""python3 -m kernel check file.mm [--json] [--limit N] [--until LABEL] [--seconds S]
python3 -m kernel prove proposals.json [--proofs DIR] [--db FILE.mm] [--json] [--dry-run]

  --limit N     stop after N provable statements
  --until L     stop after the provable statement labelled L
  --seconds S   stop after the first provable statement that ends past S seconds
  A stopped run says so; what was not read has no verdict.

Exit: 0 every provable statement read is PASS and nothing was VOID
      1 at least one FAIL | 3 no FAIL, at least one VOID (a theorem or the file)
      2 usage or unreadable input

prove: each entry of proposals.json becomes a statement over the database (default
  tests/data/algebra.mm); a proof in DIR/<id>.mm (default: proofs/ beside the file) is
  checked. No proof is searched for. proposals.json is updated in place unless --dry-run.
  Exit: 0 every entry is DERIVED and nothing failed or was VOID | 1 a kernel FAIL
        3 no FAIL; a VOID, or an entry still PROPOSED (NO_PROOF) | 2 usage
"""
import json
import sys

from .mm import check_file


def prove_main(argv):
    from .bridge import prove

    def opt(flag):
        return argv[argv.index(flag) + 1] if flag in argv else None
    try:
        rep = prove(argv[1], opt("--proofs"), opt("--db"), write="--dry-run" not in argv)
    except IndexError:
        print(__doc__, file=sys.stderr)
        return 2
    if "--json" in argv:
        print(json.dumps(rep, indent=1))
    elif rep["file_void"]:
        print(f"VOID file: {rep['file_void']} -- nothing was read, nothing was written")
    else:
        for r in rep["records"]:
            v = r["kernel_verdict"] or r["reason"]
            line = f"{v:8s} {r['id'] or '-':16s} {r['lhs']} = {r['rhs']}"
            if r["kernel_verdict"] == "FAIL":
                e = r["located"]
                line += (f" | {e['label']} step {e['step']}"
                         f"{' ' + e['step_label'] if e['step_label'] else ''}: {e['rule']}"
                         f"\n         expected: {e['expected']}\n         got:      {e['got']}")
            elif r["kernel_verdict"] == "VOID":
                line += f" | {r['reason']}"
            line += f" | status {r['status_before']} -> {r['status_after']}"
            if r["routes"]:
                line += " | routes: " + ", ".join(r["routes"])
            print(line)
        print(rep["counts"], "| written:", rep["written"],
              "| a PASS rests on the database's axioms (given input, no verdict)")
    c = rep["counts"]
    open_ = any(r["status_after"] != "DERIVED" for r in rep["records"])
    return 1 if c["FAIL"] else (3 if rep["file_void"] or c["VOID"] or open_ else 0)


def main(argv):
    if len(argv) >= 2 and argv[0] == "prove":
        return prove_main(argv)
    if len(argv) < 2 or argv[0] != "check":
        print(__doc__, file=sys.stderr)
        return 2
    kw = {}
    try:
        for flag, key, conv in (("--limit", "limit", int), ("--until", "until", str),
                                ("--seconds", "seconds", float)):
            if flag in argv:
                kw[key] = conv(argv[argv.index(flag) + 1])
    except (IndexError, ValueError):
        print(__doc__, file=sys.stderr)
        return 2
    try:
        rep = check_file(argv[1], **kw)
    except OSError as e:
        print(f"cannot read {argv[1]}: {e}", file=sys.stderr)
        return 2
    c = rep["counts"]
    if "--json" in argv:
        print(json.dumps(rep, indent=1))
    else:
        for r in rep["theorem_records"]:
            if r["verdict"] == "FAIL":
                e = r["located_error"]
                print(f"FAIL {r['label']} (line {r['line']}) step {e['step']}"
                      f"{' ' + e['step_label'] if e['step_label'] else ''}: {e['rule']}\n"
                      f"     expected: {e['expected']}\n     got:      {e['got']}")
            elif r["verdict"] == "VOID":
                print(f"VOID {r['label']} (line {r['line']}): {r['void_reason']}")
        if rep["file_void"]:
            print(f"VOID file at line {rep['file_void']['line']}: {rep['file_void']['reason']}"
                  " -- nothing after this point was read")
        if rep["stopped"]:
            print(f"stopped: {rep['stopped']} -- the rest of the file was not read")
        print(f"provable statements {rep['provable_statements']}: PASS {c['PASS']} "
              f"FAIL {c['FAIL']} VOID {c['VOID']} (status DERIVED) | axioms "
              f"{rep['axioms']['count']} (OBSERVED, no verdict) | compressed "
              f"{rep['compressed']} | steps {rep['proof_steps']} | "
              f"{rep['seconds']:.2f} s | whole file read: {rep['whole_file_read']}")
        if rep["pass_resting_on_non_pass"]:
            print(f"note: {rep['pass_resting_on_non_pass']} PASS use a statement that is "
                  "not PASS")
    return 1 if c["FAIL"] else (3 if c["VOID"] or rep["file_void"] else 0)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
