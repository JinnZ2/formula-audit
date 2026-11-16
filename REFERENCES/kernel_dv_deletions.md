# Seven $d deletions that still read PASS

Status: OBSERVED run, plus a reading of the database text for each of the
seven. All seven are confirmed by reading the text; none rests on the
kernel's own disjoint-variable check. Co-authored. Observer slots null.

```text
database    set.mm, fetched 2026-11-16, 51,952,199 bytes, sha256 099864b6785c45be...
            not in this repository; line numbers below are that file's
run         python3 -m kernel.setmm_check set.mm      (seed 0, kernel at 9b388b8)
slice       2,998 provable statements, all PASS before any fault was planted
planted     200 single "$d ... $." statements deleted, one per run, drawn from
            841 candidates (a $d inside a ${ $} block that holds a $p)
result      193 FAIL, each located as a disjoint-variable step
              7 PASS, listed here
```

A `$d` on a theorem is a restriction the theorem states. Deleting one makes
the theorem claim more; the proof fails only if some step needed the pair.
A PASS after deletion is right when the pair is stated again elsewhere in
scope, or when no step needs it.

| theorem | line | deleted | why PASS is right | how read |
|---|---|---|---|---|
| aev2 | 17566 | `$d w s $.` | line 17565 has `$d w s z $.`: the pair is stated twice | text |
| cbvex4v | 21496 | `$d w x y z $.` | each of its six pairs is in another `$d` of lines 21495-21496: w x, x z in `$d u w x z`; w y, y z in `$d v w y z`; w z in `$d u v w z`; x y in `$d x y ps` | text |
| ax6v | 16600 | `$d x y $.` | the proof is `ax-6` alone, which has no `$d`. set.mm's comment (lines 16608-16615) says the `$d` is added on purpose and "does not propagate backwards" | text |
| ax9v1 | 18380 | `$d x z $.` | the proof is `ax9v` alone, whose only `$d` is x y | text |
| ax9v2 | 18389 | `$d y z $.` | the same | text |
| hbsbw | 18972 | `$d ph w $.` | the proof's label list is `wsb wal sbimi sbal sylib`: `vw`, the `$f` of w, is not in it, and w is in neither the statement nor its hypotheses, so w never enters the proof | text |
| dvelimdc | 27556 | `$d w A $.` | no statement the proof uses turns a `$d` into the pair (w, A); see below | text |

## dvelimdc, step by step

`$d` statements in scope for each statement its proof uses, by a plain text
scan of set.mm (scopes counted from `${` and `$}`, comments blanked; not the
kernel):

```text
nfv        16025:   $d x ph $.
nfcrd      27244:   $d x y $.
nfcd       27234:   $d x y $.  $d y A $.
eleq2      (26557)  none: its statement is outside every scope; the block
                    26522-26548 with "$d x A $. $d x B $. $d x C $. $d x ph $."
                    closes before it
dvelimdf   (21861)  none in its scope (opened 21851)
syl6, imp, ex                              none
weq wal wn wnfc wa wcel cv wnf wceq wb     none
```

The proof's 14 essential steps and their substitutions (step list from the
kernel's decoder; the pairs are read off the `$d` lines above):

```text
step  label      substitution                                  $d of the label -> pairs asked    (w, A)?
  1   nfv        ph := ( ph /\ -. A. x x = y ), x := w          x ph  -> w ph, w x, w y            n
  5   nfcrd      ph := ph, x := x, y := w, A := A              x y   -> x w                       n
  7   nfcrd      ph := ph, x := z, y := w, A := B              x y   -> z w                       n
  9   eleq2      A := A, B := B, C := w                        none                               n
 10   syl6       no setvar or class variable of its own $d     none                               n
 11   dvelimdf   ps := w e. A, ch := w e. B, x y z as named    none                               n
 12   imp                                                      none                               n
 13   nfcd       ph := ( ph /\ -. A. x x = y ), x := x,        x y   -> x w                       n
                 y := w, A := B                                y A   -> w B
 14   ex                                                       none                               n
  2, 3, 4, 6, 8  the theorem's own hypotheses                  -                                  n
```

In step 5, A is substituted for nfcrd's A, and nfcrd has no `$d` naming A.
In steps 9 and 11, w and A meet inside one expression (`w e. A`), but eleq2
and dvelimdf carry no `$d` at all. The pairs asked for are w with ph, x, y,
z, B, which are the other five `$d` of line 27556. (w, A) is never asked.

Not established here: whether set.mm's maintainers regard `$d w A` on
dvelimdc as intended or as a leftover.
