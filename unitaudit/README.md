# unitaudit, branch 1 (unit audit)

Status: dimension check implemented and passing its own tests within tested
scope. Slots (limit, sign, magnitude range) are carried, NOT checked. The
scanner is a placeholder. Repository: JinnZ2/formula-audit. Licence: CC0,
as the repository's. Co-authored.

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

Input entry: `{formula, symbols: {name: unit}, source_path, slots, status?}`.
Output record: `verdict, void_reason, located_error, dims, status,
provenance, slots, human_interest (null), ai_interest (null)`.

Limits

```text
dimension only        no scale factors: km vs m, degC vs K, eV vs J are not seen
unit table            SI base, N J W Pa Hz V C ohm T Wb, dimensionless; anything else is VOID
PASS                  means the dimensions agree, not that the formula is right
angles                rad is dimensionless here; a torque and an energy read alike
status                OBSERVED = computed here from the given table; a table marked
                      PROPOSED gives a PROPOSED verdict; VOID has no status
stdlib used           ast, fractions, json, plus sys and pathlib (CLI, scanner), unittest
python                written for 3.10 syntax; run here on 3.13 only
```
