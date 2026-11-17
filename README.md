# formula-audit

Status: branch 1 (unit audit) is implemented and passes its own tests within
tested scope. Its slots (limit, sign, magnitude range) are recorded, NOT
checked. Its scanner is a placeholder. Branch 2a (proof kernel) is implemented
and passes its own tests within tested scope; it reads Metamath databases
only. Branch 2b (data points and intersections) is implemented and passes its
own tests within tested scope; only its interval tier is rigorous. Branch 3 is
not built and is not specified in this repository yet. Three known blind spots of branch 1 are listed below
and are not built.

License: CC0 1.0. Co-authored (human + AI). Stdlib only, phone-runnable.

In plain words: three small checkers for formulas. `unitaudit` asks whether
both sides of a formula have the same physical dimensions. `kernel` checks
Metamath proofs step by step. `numcheck` asks whether a formula holds at given
values, and lets only exact interval arithmetic decide. Each one records what it
could not establish (VOID, UNDECIDED) instead of guessing.

Try it (Python 3, nothing to install):

```sh
python3 -m unittest discover -s tests
python3 -m unitaudit check formulas.json
python3 -m numcheck check checks.json
```

Before relying on a result, read [READING_NOTES.md](READING_NOTES.md): it lists
the misreads a careful outside reader has already made.

## Three branches

```text
branch 1   unit audit      unitaudit/   BUILT: dimension check, PASS / FAIL / VOID
branch 2a  proof kernel    kernel/      BUILT: Metamath .mm reader and proof verifier,
                                         snapshots (verify only what comes after a PASS)
branch 2b  data points     numcheck/     BUILT: interval arithmetic, three tiers, point
                                         checks, intersections over a box
branch 3   VOID            not named or specified here
```

A void branch stays void. It is not filled in to make the list look complete.

## Branch 1: unit audit

```text
formulas.json --> symbols -> dims (7 Fractions: L M T I Theta N J)
                  formula -> ast -> a dimension per node
                                |
          +---------------------+----------------------+
          v                     v                      v
        PASS                  FAIL                   VOID
   lhs dim == rhs dim    located node + dims    unknown symbol / unit /
                                                function / syntax: reason
                                                kept, never PASS
```

```sh
python3 -m unitaudit check formulas.json [--json]   # exit 0 all PASS | 1 any FAIL | 3 VOID, no FAIL | 2 usage
python3 -m unitaudit scan PATH [-o draft.json]      # placeholder; draft entries PROPOSED, units null
python3 -m unittest discover -s tests               # prints its own count
```

Rules

```text
a + b, a - b, lhs = rhs    equal dimensions
a * b, a / b               dimensions multiply / divide
a ** k                     k dimensionless; on a base with a dimension, k must be a
                           literal number, else VOID (the result cannot be computed)
exp log sin cos tan (x)    x dimensionless
sqrt(x), abs(x)            x ** (1/2); dimension of x
unknown anything           VOID with the reason; an internal error is VOID too
```

Input entry: `{formula, symbols, source_path, slots, status?}` where each
symbol is `"unit"` or `{"unit": ..., "status": ...}`.
Output record: `verdict, void_reason, located_error, dims, status, symbols,
provenance, slots, human_interest (null), ai_interest (null)`.

Status tags

```text
verdict        DERIVED, always: it follows from the supplied unit table.
               VOID has no status (null). A verdict is never OBSERVED.
symbol's unit  its own tag, given in the input:
               OBSERVED   read straight from a source
               PROPOSED   from the scanner, or a guess
               null       not given; never filled in
               an entry-level "status" is the default for its untagged symbols
```

Slots: limit, sign, magnitude_range

```text
slot_state VOID        not given
slot_state UNCHECKED   given, and NOT checked: no values to evaluate it with.
                       UNCHECKED is not a pass. No slot is ever checked here.
```

## Branch 2a: proof kernel

Written from the Metamath language specification, not from an existing
verifier. Normal and compressed proofs.

```text
file.mm --> tokens --> statements in scope ($c $v $f $e $d $a $p ${ $})
                              |
                 each $p: proof steps on a stack
                 hypothesis -> push | assertion -> substitute, check $e, check $d
                              |
          +-------------------+--------------------+
          v                   v                    v
        PASS                FAIL                 VOID
   stack ends as       step number, label,   "?" step, undecodable compressed
   the statement       expected vs got       proof, internal error; file level:
                                             unknown keyword, include, malformed
                                             statement -> reading STOPS, nothing
                                             after it gets a verdict
```

```sh
python3 -m kernel check file.mm [--json] [--limit N] [--until LABEL] [--seconds S]
# exit 0 all read PASS | 1 any FAIL | 3 VOID (theorem or file), no FAIL | 2 usage
```

```text
status      PASS / FAIL are DERIVED. Axioms ($a) are given input: OBSERVED, no
            verdict; nothing here promotes or checks them. VOID has no status.
rests on    a PASS that uses a statement which is itself FAIL or VOID says so
            (rests_on_non_pass); it is counted, not hidden
stopped     --limit / --until / --seconds stop early and say so; what was not
            read has no verdict and whole_file_read is false
```

Snapshots (branch 2a)

```text
python3 -m kernel snapshot file.mm (--at L1,L2 | --at-fraction 0.25,0.5) [--store snapshots.json]
python3 -m kernel check file.mm --from-snapshot snapshots.json [--snap LABEL]
python3 -m kernel.snapshot_measure path/to/set.mm [--repeats 3]   # by hand, not CI

snapshot    {theorem, statement, axioms_used (transitive, syntax axioms included),
             prefix_sha256 of the lines read through its proof, prefix_lines,
             theorem_index, kernel_version, rests_on_non_pass, prefix_non_pass}
write       only after a kernel PASS for that theorem; anything else is refused
            and nothing is stored for it
use         the prefix is re-read and hashed first; a different hash (any byte,
            a comment, line endings), kernel version, or a statement not where the
            snapshot says -> VOID, nothing verified. Else the prefix's statements
            are carried (verified_here false, PASS unless listed in
            prefix_non_pass, which keep their verdict and reason) and only the
            statements after it are verified
saved       only proof checking: the prefix is still read, hashed and parsed
limit       the store is plain JSON; a forged or edited record that claims PASS
            is caught only by later statements that cite the theorem (they FAIL),
            and not at all if none does
```

Limits of branch 2a

```text
PASS            the proof follows from the database's axioms by the Metamath rules.
                It says nothing about whether those axioms are true or consistent.
not supported   include statements ($[ $]): file-level VOID
not checked     comment markup, label character rules, line length, the
                "definition soundness" conventions of set.mm
tests           hand-written databases only (tests/data/prop.mm, dv.mm and inline);
                set.mm is not in this repository and not run by CI
planted faults  python3 -m kernel.setmm_check path/to/set.mm  (by hand, not CI):
                one-letter proof mutations and single $d deletions on a slice;
                a deletion that still reads PASS is listed, not hidden: a $d can
                be stated without the proof needing it
phone           no phone timing was taken; see the run notes in the commit that
                added this section for timings on the build machine
```

## Branch 2b: data points and intersections

```text
checks.json --> branch 1 on the formula ---- not PASS ----> VOID (with branch 1's reason)
                      | PASS
                      v
      float, Decimal(prec)  = TRIAGE: a predicted_verdict each, or "too close to call"
                      v
      Fraction intervals    = CONFIRMS: every HOLDS / FAILS is decided here (rigorous;
                              sqrt exp ln sin cos as outward enclosures, precision
                              doubling to max_precision). Predicted is recorded beside
                              confirmed; a mismatch is listed and counted.
                      |  straddles, and an input is an interval?
                      v
      bisect the inputs, widest first, to the depth limit:
        every piece HOLDS -> HOLDS
        a piece where it fails at every point -> FAILS, that piece located
        else -> UNDECIDED

        HOLDS  lhs - rhs inside [-t, t]      FAILS  wholly outside (everywhere, or on
        UNDECIDED  straddles after the above        a located piece of interval inputs)
        VOID  no value on these inputs (division by an interval containing 0, ...)
```

```sh
python3 -m numcheck check checks.json [--json] [--fast]
# exit 0 all HOLDS / BOTH_HOLD | 1 any FAILS / ONE_FAILS | 3 VOID or UNDECIDED, none failed | 2 usage
```

```text
values        a number or an interval [lo, hi], with a unit and its own status tag
              (OBSERVED / DERIVED / PROPOSED, or null: never filled in). Numbers
              are read exactly as written: 0.1 is one tenth.
tolerance     t >= 0, a plain number in the units of the formula's two sides
tiers         the interval tier confirms. The record lists every tier with its role
              (triage / confirms), each predicted_verdict beside the confirmed one,
              and the mismatches; the report counts them.
--fast        (or "fast": true on a check) skips the confirmation when triage gives a
              prediction. Not rigorous: such a record carries rigorous: false.
status        HOLDS / FAILS / UNDECIDED are DERIVED; VOID has none
intersection  two formulas and a box. BOTH_HOLD: both hold on every subbox reached.
              ONE_FAILS: one fails at every point of a located subbox.
              UNDECIDED: neither at the depth limit. Bisection along the widest side.
slots         as branch 1: VOID (absent) or UNCHECKED (given, not checked)
```

Limits of branch 2b

```text
fast          a triage prediction rests on a margin rule (1e-9, or 10^-(prec/2),
              times the largest magnitude met). It is a heuristic with no bound
              over a long chain of steps. Example (tests/test_numcheck.py):
              y = ((a + b) - a)*c with a = 1e16, b = 3, c = 1e10, y = 3e10 holds
              exactly, but binary64 reads (1e16 + 3) - 1e16 as 4 and the float tier
              predicts FAILS; Decimal predicts HOLDS, the interval tier confirms
              HOLDS and the float miss is logged. Only --fast lets a prediction
              stand, marked rigorous: false.
constants     a number-only expression is folded to an exact Fraction from the
              source text before any tier runs, so (1e16 + 1) - 1e16 = 1 is exact
              at every tier (HOLDS, rigorous; no prediction). The cancellation
              hazard needs symbols; without the factor c the guard reads
              (a + b) - a as "too close to call" instead of mispredicting.
tolerance 0   on interval inputs an identity still reads UNDECIDED: x*x = x**2 on
              x in [0, 1] is UNDECIDED at tolerance 0 (the two enclosures differ; the
              dependency problem), since bisection narrows the gap without closing it.
              With a tolerance > 0 it reads HOLDS via bisection, if the depth allows.
FAILS         on interval inputs FAILS can mean "fails on a located piece of the
              given ranges" while holding on others; the record says which
              (located, bisection.holds_elsewhere)
intervals     inputs given as intervals are treated as independent ranges
ONE_FAILS     needs a whole subbox where a formula fails; a failure at single points
              only reads UNDECIDED
units         branch 1's blind spots carry over: no scale factors, so values are
              taken to be in the stated units as written (km against m is not seen)
powers        integer exponents and 1/2 only; exponent must be a literal number
sin, cos      arguments within +-1000
not built     relative tolerance, inequalities (< <=), more than two formulas
```

## Limits (branch 1)

```text
PASS                  means the dimensions agree, not that the formula is right
unit table            SI base, N J W Pa Hz V C ohm T Wb, dimensionless; anything else is VOID
scanner               placeholder: one-'=' lines and `backtick` spans that parse; misses
                      prose and LaTeX formulas, picks up ordinary assignments
formulas.json         example input; its units were typed in, not read from a source
stdlib used           ast, fractions, json, plus sys and pathlib (CLI, scanner), unittest;
                      branch 2a: time, hashlib (snapshots), statistics and tempfile
                      (snapshot_measure); branch 2b: decimal, math (isqrt, floor, float tier)
python                3.10 (floor) and 3.13 run by .github/workflows/ci.yml; see its runs
```

## Known blind spots of branch 1, not built

```text
scale                 no scale factors: km vs m, eV vs J read as the same
affine temperature    degC vs K: an offset is not a dimension; both read as Theta
angle                 rad is dimensionless here, so a dropped or extra angle factor
                      (omega*t against f*t) does not show, and a torque and an
                      energy read alike
today                 km, eV and degC are not in the unit table, so a check using
                      them comes back VOID (unknown unit), not PASS. The lines above
                      say what a table without scale factors or offsets cannot see
                      if such units are added; rad, torque and energy already read
                      alike today.
```
