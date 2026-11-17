"""python3 -m kernel check file.mm [--json] [--limit N] [--until LABEL] [--seconds S]
python3 -m kernel prove proposals.json [--proofs DIR] [--db FILE.mm] [--json] [--dry-run]
python3 -m kernel check file.mm ... [--from-snapshot STORE [--snap LABEL]]
python3 -m kernel snapshot file.mm (--at L1,L2 | --at-fraction 0.25,0.5)
                           [--store snapshots.json] [--from-snapshot STORE --snap L]

  --limit N     stop after N provable statements
  --until L     stop after the provable statement labelled L
  --seconds S   stop after the first provable statement that ends past S seconds
  A stopped run says so; what was not read has no verdict.
  --from-snapshot STORE   re-read and hash the snapshot's prefix; if it matches,
                carry the prefix's verdicts and verify only what comes after.
                No match -> VOID, nothing verified.
  snapshot      run the kernel and store a snapshot for each target that reads
                PASS; any other target is refused and nothing is stored for it.

Exit (check): 0 every provable statement read is PASS and nothing was VOID
      1 at least one FAIL | 3 no FAIL, at least one VOID (a theorem, the file, or
      the snapshot) | 2 usage or unreadable input
Exit (snapshot): 0 every target written | 1 any target refused | 3 the starting
      snapshot was VOID | 2 usage

prove: each entry of proposals.json becomes a statement over the database (default
  tests/data/algebra.mm); a proof in DIR/<id>.mm (default: proofs/ beside the file) is
  checked. No proof is searched for. proposals.json is updated in place unless --dry-run.
  Exit: 0 every entry is DERIVED and nothing failed or was VOID | 1 a kernel FAIL
        3 no FAIL; a VOID, or an entry still PROPOSED (NO_PROOF) | 2 usage
"""
import json
import sys

from .mm import run_file
from . import snapshot as snap


def _opt(argv, flag, conv=str):
    if flag in argv:
        return conv(argv[argv.index(flag) + 1])
    return None


def _from(argv):
    store = _opt(argv, "--from-snapshot")
    if store is None:
        return None, None
    rec, why = snap.select(snap.load(store), _opt(argv, "--snap"))
    return rec, why


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
    if len(argv) < 2 or argv[0] not in ("check", "snapshot"):
        print(__doc__, file=sys.stderr)
        return 2
    try:
        start, why = _from(argv)
        if why is not None:
            print(f"--from-snapshot: {why}", file=sys.stderr)
            return 2
        if argv[0] == "snapshot":
            labels = (_opt(argv, "--at") or "").split(",")
            fracs = [float(x) for x in (_opt(argv, "--at-fraction") or "").split(",") if x]
            labels = [x for x in labels if x]
            if not labels and not fracs:
                raise ValueError("no target")
            store = _opt(argv, "--store") or "snapshots.json"
        kw = {}
        for flag, key, conv in (("--limit", "limit", int), ("--until", "until", str),
                                ("--seconds", "seconds", float)):
            v = _opt(argv, flag, conv)
            if v is not None:
                kw[key] = v
    except (IndexError, ValueError) as e:
        print(f"{e}\n{__doc__}", file=sys.stderr)
        return 2
    try:
        if argv[0] == "snapshot":
            written, refused, rep = snap.write(argv[1], labels, fracs, store, start)
            for r in written:
                print(f"written {r['theorem']} (index {r['theorem_index']}, lines "
                      f"{r['prefix_lines']}, sha256 {r['prefix_sha256'][:16]}, axioms used "
                      f"{len(r['axioms_used'])}, rests on non-PASS {r['rests_on_non_pass']})")
            for w in refused:
                print(f"refused {w}")
            if rep.get("snapshot") and rep["snapshot"]["state"] == "VOID":
                return 3
            return 1 if refused else 0
        rep, _db = run_file(argv[1], snapshot=start, **kw)
    except OSError as e:
        print(f"cannot read {argv[1]}: {e}", file=sys.stderr)
        return 2
    c = rep["counts"]
    if "--json" in argv:
        print(json.dumps(rep, indent=1))
    else:
        for r in rep["theorem_records"]:
            if r["verdict"] == "FAIL" and r["verified_here"]:
                e = r["located_error"]
                print(f"FAIL {r['label']} (line {r['line']}) step {e['step']}"
                      f"{' ' + e['step_label'] if e['step_label'] else ''}: {e['rule']}\n"
                      f"     expected: {e['expected']}\n     got:      {e['got']}")
            elif r["verdict"] != "PASS":
                print(f"{r['verdict']} {r['label']} (line {r['line']}): "
                      f"{r['void_reason'] or 'carried from snapshot ' + str(r['carried_from_snapshot'])}")
        if rep["file_void"]:
            print(f"VOID file at line {rep['file_void']['line']}: {rep['file_void']['reason']}"
                  " -- nothing after this point was read")
        if rep["stopped"]:
            print(f"stopped: {rep['stopped']} -- the rest of the file was not read")
        if rep.get("snapshot"):
            s = rep["snapshot"]
            print(f"snapshot {s['theorem']}: {s['state']} | carried "
                  f"{rep['carried_from_snapshot']} | verified here {rep['verified_here']}")
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
