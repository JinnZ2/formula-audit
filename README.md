# formula-audit

Status: branch 1 (unit audit) is implemented and passes its own tests within
tested scope. Its slots (limit, sign, magnitude range) are recorded, NOT
checked. Its scanner is a placeholder. Branch 2a (proof kernel) is implemented
and passes its own tests within tested scope; it reads Metamath databases
only. The rest of branch 2, and branch 3, are not built and are not specified
in this repository yet. Three known blind spots of branch 1 are listed below
and are not built.

License: CC0 1.0. Co-authored (human + AI). Stdlib only, phone-runnable.

## Three branches

```text
branch 1   unit audit      unitaudit/   BUILT: dimension check, PASS / FAIL / VOID
branch 2a  proof kernel    kernel/      BUILT: Metamath .mm reader and proof verifier
branch 2   (rest) VOID     not named or specified here
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
tests           hand-written databases only (tests/data/prop.mm and inline);
                set.mm is not in this repository and not run by CI
phone           no phone timing was taken; see the run notes in the commit that
                added this section for timings on the build machine
```

## Limits (branch 1)

```text
PASS                  means the dimensions agree, not that the formula is right
unit table            SI base, N J W Pa Hz V C ohm T Wb, dimensionless; anything else is VOID
scanner               placeholder: one-'=' lines and `backtick` spans that parse; misses
                      prose and LaTeX formulas, picks up ordinary assignments
formulas.json         example input; its units were typed in, not read from a source
stdlib used           ast, fractions, json, plus sys and pathlib (CLI, scanner), unittest
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
