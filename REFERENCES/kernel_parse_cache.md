# Kernel snapshots, round 3: where parse time goes, and a parse cache

Status: OBSERVED runs on one machine (the build container, 4 CPUs, otherwise
idle: the 1-minute load average before each run is in the json and stayed at or
below 1.00, which is this single-threaded run itself). Co-authored. Observer
slots null. Output: `kernel_parse_split.json`, `kernel_parse_cache.json`.

```text
database    set.mm, sha256 099864b6785c45be66026cf19ec3f3a77c9cac15d586eb954d8de205ea2fa52b
            (as in rounds 1 and 2); not in this repository
```

1. Parse time on a 75 % snapshot load, prefix only (snapshot wl-sbcom2d-lem2,
index 36,293, 627,075 lines, 3,528,875 tokens; median of 3)

| part | seconds |
|---|---|
| (a) tokenizing the prefix (timed alone) | 0.67 |
| (b) building records for carried statements | 0.20 |
| (c) reading cited labels from carried proofs | 0.24 |
| the rest: statement handling (collecting statement tokens, frames of assertions, scopes) | 1.61 |
| prefix parse, total | 2.76 |

(b) + (c) = 0.44 s, 16 % of prefix parse: they do not dominate, so step 2
(carried statements skip reading proof text) was not done. A profile of the
same run puts the most time in the token generator and in collecting each
statement's tokens, then in building each assertion's frame.

2. Parse cache. Totals, median of 3, spot 25 seed 0 (full run: 18.54 s)

| cut | cache MB | snapshot s | snapshot + cache s | cache load s | verdicts identical (both) |
|---|---|---|---|---|---|
| 25 % (1lt9) | 7.9 | 17.30 | 16.62 | 0.12 | yes, 48,391 / 48,391 |
| 50 % (reipcl) | 23.6 | 14.37 | 13.83 | 0.38 | yes |
| 75 % (wl-sbcom2d-lem2) | 42.6 | 9.43 | 8.03 | 0.51 | yes |

The cache saves 0.5 to 1.4 s against a prefix parse of 2.76 s at 75 %: loading
the file (0.51 s) and rebuilding the state and the carried records take the rest.
The rebuild was not timed apart from the whole load. Writing three snapshots
with caches: 22.9 s (one full run, hashing and capturing each statement's
context).

Mismatches (both refused, logged, prefix parsed in full, verdicts identical)

```text
one byte of the 75 % cache flipped    "sha256 is not the one the snapshot records"
an intact cache rekeyed to "kernel    "key [..., 'kernel other'] is not [..., kernel branch2a-0]"
  other", its new sha256 recorded
```
