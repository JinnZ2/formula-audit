# Kernel snapshots on set.mm: time saved, verdicts, planted faults

Status: OBSERVED run on one machine (the build container). Co-authored.
Observer slots null. Full output: `kernel_snapshots_setmm.json` beside this file.

```text
database    set.mm, fetched 2026-11-17 from github.com/metamath/set.mm (develop),
            51,952,199 bytes, sha256 099864b6785c45be66026cf19ec3f3a77c9cac15d586eb954d8de205ea2fa52b
            (the same bytes as the 2026-11-16 fetch in kernel_dv_deletions.md);
            not in this repository
run         python3 -m kernel.snapshot_measure set.mm --repeats 3   (Python 3.13)
full        48,391 provable statements, all PASS; median 16.57 s (16.33 16.57 16.93)
write run   one run writing snapshots at 25 / 50 / 75 %: 17.4 s, none refused
```

| snapshot | position | carried | verified here | median s | saved s | saved | verdicts identical |
|---|---|---|---|---|---|---|---|
| 1lt9 | 12,098 (25 %) | 12,098 | 36,293 | 15.82 | 0.75 | 4.5 % | yes, 48,391 of 48,391 |
| reipcl | 24,196 (50 %) | 24,196 | 24,195 | 12.17 | 4.40 | 26.6 % | yes |
| wl-sbcom2d-lem2 | 36,293 (75 %) | 36,293 | 12,098 | 7.93 | 8.64 | 52.1 % | yes |

Identical = per statement, verdict and rests_on_non_pass, from-snapshot against
full. The time saved is well under the fraction carried: the prefix is still
read, hashed and parsed, and the early part of set.mm holds shorter proofs than
the later part, so a statement carried at 25 % saves less than one at 75 %.

Planted faults

```text
stale hash      one letter of a compressed proof on line 47,001 changed (inside the
                50 % prefix); snapshot reipcl not rewritten
                -> VOID: "the first 353583 lines do not hash to the stored sha256";
                   0 statements verified. A full check of the edited file: 1 FAIL.
mutated theorem cncff (position 23,916, cited by 127 later statements): its first
                "->" token changed to "<->"
                honest writer: refused ("verdict FAIL, a snapshot needs PASS")
                forged record (mutated statement, mutated prefix's hash):
                -> MATCHED; cncff carried as PASS (the store cannot tell);
                   127 of 127 citing statements FAIL; nothing else changed
                   (PASS 48,264, FAIL 127)
```

One defect in the measuring script, found by running it: the first forged
record replaced "->" as text, which also hit the "->" inside "-cn->", so the
record's statement did not match the file. The kernel's in-place check read
that as a snapshot not where it says and made every carried statement VOID
(23,916 VOID). Repaired to replace the token "->". The VOID was the kernel
doing its job on a record the script got wrong.
