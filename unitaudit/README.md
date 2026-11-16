# unitaudit, branch 1 (unit audit)

Status: dimension check implemented and passing its own tests within tested
scope. Slots (limit, sign, magnitude range) are recorded, NOT checked. The
scanner is a placeholder. Three known blind spots are listed under Limits and
are not built. Repository: JinnZ2/formula-audit. Licence: CC0, as the
repository's. Co-authored.

This file sits inside the package so the repository's own README, LICENSE
and CI stay as their author wrote them. When this branch was pushed
(2026-11-16) the remote had no branch and no files; none of those three
were present to read.

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
# all three from the repository root
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

Limits

```text
PASS                  means the dimensions agree, not that the formula is right
unit table            SI base, N J W Pa Hz V C ohm T Wb, dimensionless; anything else is VOID
stdlib used           ast, fractions, json, plus sys and pathlib (CLI, scanner), unittest
python                written for 3.10 syntax; run here on 3.11, 3.12, 3.13, not on 3.10
```

Known blind spots, not built

```text
scale                 no scale factors: km vs m, eV vs J read as the same
affine temperature    degC vs K: an offset is not a dimension; both read as Theta
angle                 rad is dimensionless here, so sin(omega) with omega in rad/s
                      still fails, but a dropped or extra angle factor does not show,
                      and a torque and an energy read alike
```
