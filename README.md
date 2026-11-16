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

## Three branches

```text
branch 1   unit audit      unitaudit/   BUILT: dimension check, PASS / FAIL / VOID
branch 2a  proof kernel    kernel/      BUILT: Metamath .mm reader and proof verifier
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
      bisect the inputs, widest first, to the depth limit; read every piece:
        every piece HOLDS                      -> HOLDS
        pieces that HOLD and pieces that FAIL  -> MIXED (both kinds listed)
        pieces that FAIL, none that hold       -> FAILS, located
        else                                   -> UNDECIDED
                      |  UNDECIDED at tolerance 0, nothing against it, and the two
                      v  sides agree at every sampled exact point?
      identity candidate -> "proposal" on the record, status PROPOSED, no proof

        HOLDS  lhs - rhs inside [-t, t]      FAILS  wholly outside
        MIXED  holds on part of the given values, fails on another part
        UNDECIDED  straddles after the above
        VOID  no value on these inputs (division by an interval containing 0, ...)
```

```sh
python3 -m numcheck check checks.json [--json] [--fast] [--proposals proposals.json]
# exit 0 all HOLDS / BOTH_HOLD | 1 any FAILS / ONE_FAILS | 3 MIXED, UNDECIDED or VOID, none failed | 2 usage
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
intersection  two formulas and a box, bisected along the widest side; every subbox
              is read. BOTH_HOLD: both hold on every subbox. MIXED: subboxes where
              both hold and subboxes where one fails everywhere (both listed).
              ONE_FAILS: subboxes where one fails, none where both hold.
              UNDECIDED: neither at the depth limit.
MIXED         a statement about the given ranges: true on part, false on part. It is
              not a failure of the formula and not a pass; exit code 3.
proposals     --proposals FILE adds this run's identity candidates to FILE: {lhs, rhs,
              domain, fixed, units, source_check, evidence, status PROPOSED,
              proof: null}. Existing entries are kept; nothing is written without
              the flag. A candidate is for a later kernel proof; none is attempted.
slots         as branch 1: VOID (absent) or UNCHECKED (given, not checked)
```

Limits of branch 2b

```text
fast          a triage prediction rests on a margin rule (1e-9, or 10^-(prec/2),
              times the largest magnitude met). It is a heuristic with no bound
              over a long chain of steps: (1e16 + 1) - 1e16 = 1 is predicted FAILS
              by the float tier. Only --fast lets it stand, marked rigorous: false.
tolerance 0   on interval inputs an identity still reads UNDECIDED: x*x = x**2 on
              x in [0, 1] is UNDECIDED at tolerance 0 (the two enclosures differ; the
              dependency problem), since bisection narrows the gap without closing it.
              With a tolerance > 0 it reads HOLDS via bisection, if the depth allows.
FAILS         on interval inputs FAILS can mean "fails on located pieces of the given
              ranges, and no piece holds" (other pieces may still straddle)
lists         a record lists at most 32 pieces of each kind; the counts are complete
candidates    an identity candidate rests on 7 to 14 sampled points. That is evidence,
              not proof: two different functions can agree at all of them
intervals     inputs given as intervals are treated as independent ranges
ONE_FAILS     and MIXED need a whole subbox where a formula fails; a failure at single
              points only reads UNDECIDED
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
                      branch 2a: time; branch 2b: decimal, math (isqrt, floor, float tier)
python                3.10 (floor) and 3.13 run by .github/workflows/ci.yml; see its runs
```

## Known blind spots of branch 1, not built

```text
scale                 no scale factors: km vs m, eV vs J read as the same
affine temperature    degC vs K: an offset is not a dimension; both read as Theta
angle                 rad is dimensionless here, so a dropped or extra angle factor
                      (omega*t against f*t) does not show, and a torque and an
                      energy read alike
```
