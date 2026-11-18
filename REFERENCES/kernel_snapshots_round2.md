# Kernel snapshots, round 2: re-verify on load, forgery catch rates, profile

Status: OBSERVED run on one machine (the build container, shared with other
work, so times move between runs). Co-authored. Observer slots null. Full
output: `kernel_snapshots_round2.json` beside this file.

```text
database    set.mm, 51,952,199 bytes, sha256 099864b6785c45be66026cf19ec3f3a77c9cac15d586eb954d8de205ea2fa52b
            (the bytes of kernel_snapshots_setmm.md); not in this repository
run         python3 -m kernel.snapshot_round2 set.mm   (loads 200, k 25, Python 3.13)
```

On load (kernel/mm.py `_recheck`): the snapshot theorem is always re-verified,
and K prefix theorems drawn with a seed are re-verified. A verdict other than
the one carried makes the run VOID, naming the theorem.

Forged snapshot, theorem cited by nothing

```text
theorem     fineqvpow (position 33,888), cited by no statement; its statement negated
            (|- X -> |- -. X), snapshot forged with the edited prefix's hash
result      VOID: "fineqvpow (position 33888, snapshot theorem) re-verified FAIL;
            the snapshot carries PASS"
```

Forged prefix theorem, cited by nothing: 200 loads, seeds 0..199, K 25

| snapshot | index | victim | caught | rate | expected K/(index-1) | binomial sd |
|---|---|---|---|---|---|---|
| jarr | 101 | pm2.83 | 43 | 0.215 | 0.250 | 0.031 |
| pm4.45 | 1001 | pm5.36 | 7 | 0.035 | 0.025 | 0.011 |

Every catch named the victim. Each victim reads FAIL in a full check of the
edited file. Each load read only the prefix (--until the snapshot theorem).
Both rates are within 1.2 sd of K/(index-1). At a 75 % cut (index 36,293) the
same chance per load is 25/36,292 = 0.0007.

Profile (median of 3; seconds; lines already read into memory before parse)

| run | read | hash | parse | verify | total |
|---|---|---|---|---|---|
| full | 0.09 | 0.00 | 3.24 | 17.06 | 20.39 |
| from 75 % snapshot (wl-sbcom2d-lem2), spot 25, seed 0 | 0.09 | 0.08 | 4.27 | 4.63 | 9.16 |

read = file to lines; hash = sha256 of the lines the run hashes (none for a full
check, the 627,075-line prefix for a load); parse = everything but proof
checking; verify = proof checking (12,124 statements on the load: 12,098 after
the cut, the snapshot theorem, 25 spot). Parse is higher on the load than on the
full run: a carried statement still builds its record and reads its cited
labels from the proof text. Totals here are higher than the 16.57 s of round 1
(same code path for a full check); the container was busier. No optimization
was done in this round.

Two defects in the measuring script, found by running it

```text
1  the first edit swapped "->" for "<->". Early in set.mm "<->" is not yet
   declared, so the file went VOID at that line instead of the victim FAILing:
   200 of 200 loads at index 101 were VOID for that file-level reason, a rate of
   1.0 that measured nothing. Repaired: the edit inserts "-." (declared at the
   top), and a victim is used only if a full check of it reads FAIL.
2  in the tests, renaming P to Q throughout a statement (|- ( Q -> Q )) is not a
   fault: the compressed proof's first hypothesis becomes wq and the proof
   still holds. The planted fault there is |- ( P -> Q ).
```
