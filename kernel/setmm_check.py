"""setmm_check -- two planted-fault runs on a slice of a real database.

Co-authored. Not run by CI: the database (set.mm) is not in this repository.

  python3 -m kernel.setmm_check path/to/set.mm [--theorems 3000] [--mutations 300]
                                               [--dv 200] [--seed 0] [--json]

  slice      the file up to the end of the N-th "$p ... $= ... $." (found by
             pattern, so the count the verifier reports can differ by a few).
  mutations  one letter of one compressed proof replaced by another capital
             letter; verdict of the run: FAIL / VOID / PASS. Every VOID's
             reason and every PASS are listed.
  dv         one "$d ... $." statement deleted. Only $d statements that sit
             inside a ${ $} block holding a $p are drawn. FAIL = some proof
             that passed before now fails: it needed it. PASS = no proof in the slice needed it; each PASS is
             listed with its text so it can be looked at.
A planted fault that still reads PASS is the reading that matters here.
"""
import json
import random
import re
import sys

from .mm import check_lines

PROOF = re.compile(r"\$p\b[^$]*\$=[^$]*\$\.")
COMPRESSED = re.compile(r"\$=\s*\(([^)]*)\)([A-Z\s]+)\$\.")
DV = re.compile(r"\$d\s[^$]*\$\.")
LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def take_slice(text, n):
    ends = [m.end() for m in PROOF.finditer(text)]
    return text[:ends[n - 1]] if len(ends) >= n else text


def verdict(text, known=frozenset()):
    """Verdict of a run, counting only what is new against `known`: the labels
    that were already not PASS before the fault was planted."""
    rep = check_lines(text.splitlines()).report()
    bad = [r for r in rep["theorem_records"]
           if r["verdict"] != "PASS" and r["label"] not in known]
    kind = ("FILE_VOID" if rep["file_void"] else
            "FAIL" if any(r["verdict"] == "FAIL" for r in bad) else
            "VOID" if bad else "PASS")
    return kind, rep, bad


def not_pass(text):
    return frozenset(r["label"] for r in check_lines(text.splitlines()).report()
                     ["theorem_records"] if r["verdict"] != "PASS")


def mutations(pre, n, rng):
    proofs = list(COMPRESSED.finditer(pre))
    known = not_pass(pre)
    out = {"FAIL": 0, "VOID": 0, "PASS": 0, "FILE_VOID": 0}
    voids, passes = [], []
    for k in range(n):
        m = rng.choice(proofs)
        body = m.group(2)
        i = rng.choice([j for j, ch in enumerate(body) if ch.isalpha()])
        old = body[i]
        new = rng.choice([x for x in LETTERS if x != old])
        at = m.start(2) + i
        kind, rep, bad = verdict(pre[:at] + new + pre[at + 1:], known)
        out[kind] += 1
        row = {"mutation": k, "from": old, "to": new,
               "context": body[max(0, i - 8):i + 9].replace("\n", " ")}
        if kind == "VOID":
            voids.append({**row, "theorem": bad[0]["label"], "line": bad[0]["line"],
                          "void_reason": bad[0]["void_reason"]})
        elif kind == "FILE_VOID":
            voids.append({**row, "file_void": rep["file_void"]})
        elif kind == "PASS":
            passes.append(row)
    return {"n": n, "counts": out, "voids": voids, "passes": passes}


def dv_deletions(pre, n, rng):
    # $d statements inside a block that also holds a $p
    cands, depth_start = [], []
    for m in re.finditer(r"\$\{|\$\}|\$\(.*?\$\)", pre, re.S):
        if m.group() == "${":
            depth_start.append(m.end())
        elif m.group() == "$}" and depth_start:
            a, b = depth_start.pop(), m.start()
            block = pre[a:b]
            if "$p" in block and "${" not in block:
                clean = re.sub(r"\$\(.*?\$\)", lambda c: " " * len(c.group()), block, flags=re.S)
                for d in DV.finditer(clean):
                    if "$p" in clean[d.end():]:
                        cands.append((a + d.start(), a + d.end()))
    rng.shuffle(cands)
    known = not_pass(pre)
    out = {"FAIL": 0, "VOID": 0, "PASS": 0, "FILE_VOID": 0}
    fails, passes, other = [], [], []
    for a, b in cands[:n]:
        text = pre[a:b]
        kind, rep, bad = verdict(pre[:a] + " " * (b - a) + pre[b:], known)
        out[kind] += 1
        line = pre.count("\n", 0, a) + 1
        if kind == "FAIL":
            e = bad[0]["located_error"]
            fails.append({"deleted": " ".join(text.split()), "line": line,
                          "theorem": bad[0]["label"], "step": e["step"],
                          "step_label": e["step_label"], "rule": e["rule"],
                          "expected": e["expected"], "got": e["got"]})
        elif kind == "PASS":
            passes.append({"deleted": " ".join(text.split()), "line": line})
        else:
            other.append({"deleted": " ".join(text.split()), "line": line, "kind": kind,
                          "file_void": rep["file_void"]})
    return {"candidates_in_slice": len(cands), "n": min(n, len(cands)), "counts": out,
            "fail_rules": sorted({f["rule"].split()[0] + " " + f["rule"].split()[1]
                                  for f in fails}),
            "fails_not_located_as_disjoint_variables":
                [f for f in fails if not f["rule"].startswith("disjoint variables")],
            "first_fails": fails[:5], "passes": passes, "other": other}


def main(argv):
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2

    def opt(flag, default):
        return int(argv[argv.index(flag) + 1]) if flag in argv else default
    with open(argv[0], encoding="utf-8") as f:
        text = f.read()
    pre = take_slice(text, opt("--theorems", 3000))
    kind, rep, _ = verdict(pre)
    seed = opt("--seed", 0)
    out = {"input": argv[0], "slice_bytes": len(pre), "seed": seed,
           "baseline": {"verdict": kind, "counts": rep["counts"],
                        "provable_statements": rep["provable_statements"]},
           "mutations": mutations(pre, opt("--mutations", 300), random.Random(seed)),
           "dv_deletions": dv_deletions(pre, opt("--dv", 200), random.Random(seed)),
           "human_interest": None, "ai_interest": None}
    if "--json" in argv:
        print(json.dumps(out, indent=1))
    else:
        print("baseline", out["baseline"])
        m, d = out["mutations"], out["dv_deletions"]
        print("mutations", m["n"], m["counts"])
        for v in m["voids"]:
            print("  VOID", v)
        for p in m["passes"]:
            print("  PASS", p)
        print("dv deletions", d["n"], "of", d["candidates_in_slice"], "candidates", d["counts"],
              "| rules:", d["fail_rules"])
        for f in d["first_fails"]:
            print("  FAIL", f)
        for p in d["passes"]:
            print("  PASS", p)
        for o in d["other"] + d["fails_not_located_as_disjoint_variables"]:
            print("  OTHER", o)
    planted_pass = out["mutations"]["counts"]["PASS"]
    return 1 if planted_pass else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
