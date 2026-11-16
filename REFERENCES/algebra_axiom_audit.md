# Audit of tests/data/algebra.mm

Status: OBSERVED run of `python3 -m kernel.axiom_audit` on 2026-11-16. No axiom
FAILS and every guard row reads GUARD_OK, so the seam's PASS route is OPEN.
Consistency is DERIVED by a model argument that rests on the guard table and
the set.mm map below. Both were made by one reader: second reader VOID.
Co-authored. Observer slots null.

```text
database     tests/data/algebra.mm, 83 $a statements; kernel status of each: OBSERVED, no verdict
set.mm       fetched 2026-11-16, 51,952,199 bytes, sha256 099864b6785c45be...; not in this
             repository. The statements quoted here are recorded in REFERENCES/setmm_quotes.json.
classes      {"syntax": 22, "propositional": 7, "equational": 28, "conditional": 26}
step 2       DERIVED 35: a polynomial identity proved on a full grid, exact arithmetic,
             or a truth table (28 equational, 7 propositional)
step 3       26 conditional axioms sampled at exact points: 0 false, 0 not decided
             (sqrt comparisons are decided exactly, by squaring)
set.mm map   {"EXACT": 19, "TYPED": 18, "IMPLIED": 24, "SYNTAX": 22, "UNMAPPED": 0}
guard table  45 rows: {"GUARD_OK": 45, "GUARD_WEAKER": 0, "UNCLEAR": 0}
mutation     66 one-change mutants of 28 equational axioms: 65 FAIL in step 2;
             the 1 not failed is ( t - 0 ) = t, which is a true statement
sampling     values -2 -1 -1/2 0 1/2 1 2 9/4 4 for every term variable, all combinations;
             undefined values (x / 0, sqrt below 0, a non-numeral power) filled in two
             different ways, the statement must hold under both
```

## Consistency

```text
status         DERIVED
argument       a model: the real numbers, with x / 0, sqrt below 0 and non-numeral powers
               given fixed values. Every axiom is true in it:
                 equational     a polynomial identity (proved on a full grid) or exact arithmetic
                 propositional  truth table
                 conditional    the set.mm statement it maps to, with the guards compared
                                row by row below; and no counterexample under two fill-ins
               Axioms that have a model do not contradict each other.
rests on       the guard table and the set.mm map
relative to    the real numbers as set.mm has them
truth in model the 26 conditional axioms: DERIVED via the set.mm map
second reader  VOID  -- the map and the guard table were made by one reader (this
               build). The slot is for a pass by a different model or person; it is empty.
```

## Guard table

algebra.mm's guards (antecedents of the axiom) beside the antecedents of the set.mm
statement it maps to. GUARD_OK: every set.mm antecedent that is not a typing
antecedent (`A e. CC`, `A e. RR`, `N e. NN0`) is among algebra.mm's guards. Typing is
set aside because algebra.mm has one sort: every term is a real number in the model.
GUARD_WEAKER would mean algebra.mm claims more than set.mm proves.

| axiom | algebra.mm guards | set.mm antecedents (not typing) | set.mm typing | set.mm statement (quoted) | verdict |
|---|---|---|---|---|---|
| `eqcom` | t = r | - | - | eqcom $p \|- ( A = B <-> B = A ) | GUARD_OK |
| `eqtr` | t = r ; r = s | A = B ; B = C | - | eqtr $p \|- ( ( A = B /\ B = C ) -> A = C ) | GUARD_OK |
| `addeq1` | t = r | A = B | - | oveq1 $p \|- ( A = B -> ( A F C ) = ( B F C ) ) | GUARD_OK |
| `addeq2` | t = r | A = B | - | oveq2 $p \|- ( A = B -> ( C F A ) = ( C F B ) ) | GUARD_OK |
| `subeq1` | t = r | A = B | - | oveq1 $p \|- ( A = B -> ( A F C ) = ( B F C ) ) | GUARD_OK |
| `subeq2` | t = r | A = B | - | oveq2 $p \|- ( A = B -> ( C F A ) = ( C F B ) ) | GUARD_OK |
| `muleq1` | t = r | A = B | - | oveq1 $p \|- ( A = B -> ( A F C ) = ( B F C ) ) | GUARD_OK |
| `muleq2` | t = r | A = B | - | oveq2 $p \|- ( A = B -> ( C F A ) = ( C F B ) ) | GUARD_OK |
| `diveq1` | t = r | A = B | - | oveq1 $p \|- ( A = B -> ( A F C ) = ( B F C ) ) | GUARD_OK |
| `diveq2` | t = r | A = B | - | oveq2 $p \|- ( A = B -> ( C F A ) = ( C F B ) ) | GUARD_OK |
| `poweq1` | t = r | A = B | - | oveq1 $p \|- ( A = B -> ( A F C ) = ( B F C ) ) | GUARD_OK |
| `sqrteq` | t = r | A = B | - | fveq2 $p \|- ( A = B -> ( F ` A ) = ( F ` B ) ) | GUARD_OK |
| `negeq` | t = r | A = B | - | negeq $p \|- ( A = B -> -u A = -u B ) | GUARD_OK |
| `leeq1` | t = r ; t <_ s | A = B | - | breq1 $p \|- ( A = B -> ( A R C <-> B R C ) ) | GUARD_OK |
| `leeq2` | t = r ; s <_ t | A = B | - | breq2 $p \|- ( A = B -> ( C R A <-> C R B ) ) | GUARD_OK |
| `addcom` | - | - | A e. CC ; B e. CC | addcom $p \|- ( ( A e. CC /\ B e. CC ) -> ( A + B ) = ( B + A ) ) | GUARD_OK |
| `addass` | - | - | A e. CC ; B e. CC ; C e. CC | addass $p \|- ( ( A e. CC /\ B e. CC /\ C e. CC ) -> ( ( A + B ) + C ) = ( A + ( B + C ) ) ) | GUARD_OK |
| `add0` | - | - | A e. CC | addrid $p \|- ( A e. CC -> ( A + 0 ) = A ) | GUARD_OK |
| `addneg` | - | - | A e. CC | negid $p \|- ( A e. CC -> ( A + -u A ) = 0 ) | GUARD_OK |
| `subdef` | - | - | A e. CC ; B e. CC | negsub $p \|- ( ( A e. CC /\ B e. CC ) -> ( A + -u B ) = ( A - B ) ) | GUARD_OK |
| `mulcom` | - | - | A e. CC ; B e. CC | mulcom $p \|- ( ( A e. CC /\ B e. CC ) -> ( A x. B ) = ( B x. A ) ) | GUARD_OK |
| `mulass` | - | - | A e. CC ; B e. CC ; C e. CC | mulass $p \|- ( ( A e. CC /\ B e. CC /\ C e. CC ) -> ( ( A x. B ) x. C ) = ( A x. ( B x. C ) ) ) | GUARD_OK |
| `mul1` | - | - | A e. CC | mulrid $p \|- ( A e. CC -> ( A x. 1 ) = A ) | GUARD_OK |
| `distr` | - | - | A e. CC ; B e. CC ; C e. CC | adddi $p \|- ( ( A e. CC /\ B e. CC /\ C e. CC ) -> ( A x. ( B + C ) ) = ( ( A x. B ) + ( A x. C ) ) ) | GUARD_OK |
| `divmul` | -. r = 0 | B =/= 0 | A e. CC ; B e. CC | divcan1 $p \|- ( ( A e. CC /\ B e. CC /\ B =/= 0 ) -> ( ( A / B ) x. B ) = A ) | GUARD_OK |
| `ne01` | - | - | - | 0ne1 $p \|- 0 =/= 1 | GUARD_OK |
| `exp0` | - | - | A e. CC | exp0 $p \|- ( A e. CC -> ( A ^ 0 ) = 1 ) | GUARD_OK |
| `exp1` | - | - | A e. CC | exp1 $p \|- ( A e. CC -> ( A ^ 1 ) = A ) | GUARD_OK |
| `exp2` | - | - | A e. CC | sqval $p \|- ( A e. CC -> ( A ^ 2 ) = ( A x. A ) ) | GUARD_OK |
| `exp3` | - | - | A e. CC ; N e. NN0 | expp1 $p \|- ( ( A e. CC /\ N e. NN0 ) -> ( A ^ ( N + 1 ) ) = ( ( A ^ N ) x. A ) ) ;; df-3 $a \|- 3 = ( 2 + 1 ) | GUARD_OK |
| `exp4` | - | - | A e. CC ; N e. NN0 | expp1 $p \|- ( ( A e. CC /\ N e. NN0 ) -> ( A ^ ( N + 1 ) ) = ( ( A ^ N ) x. A ) ) ;; df-4 $a \|- 4 = ( 3 + 1 ) | GUARD_OK |
| `exp5` | - | - | A e. CC ; N e. NN0 | expp1 $p \|- ( ( A e. CC /\ N e. NN0 ) -> ( A ^ ( N + 1 ) ) = ( ( A ^ N ) x. A ) ) ;; df-5 $a \|- 5 = ( 4 + 1 ) | GUARD_OK |
| `exp6` | - | - | A e. CC ; N e. NN0 | expp1 $p \|- ( ( A e. CC /\ N e. NN0 ) -> ( A ^ ( N + 1 ) ) = ( ( A ^ N ) x. A ) ) ;; df-6 $a \|- 6 = ( 5 + 1 ) | GUARD_OK |
| `exp7` | - | - | A e. CC ; N e. NN0 | expp1 $p \|- ( ( A e. CC /\ N e. NN0 ) -> ( A ^ ( N + 1 ) ) = ( ( A ^ N ) x. A ) ) ;; df-7 $a \|- 7 = ( 6 + 1 ) | GUARD_OK |
| `exp8` | - | - | A e. CC ; N e. NN0 | expp1 $p \|- ( ( A e. CC /\ N e. NN0 ) -> ( A ^ ( N + 1 ) ) = ( ( A ^ N ) x. A ) ) ;; df-8 $a \|- 8 = ( 7 + 1 ) | GUARD_OK |
| `exp9` | - | - | A e. CC ; N e. NN0 | expp1 $p \|- ( ( A e. CC /\ N e. NN0 ) -> ( A ^ ( N + 1 ) ) = ( ( A ^ N ) x. A ) ) ;; df-9 $a \|- 9 = ( 8 + 1 ) | GUARD_OK |
| `leid` | - | - | A e. RR | leid $p \|- ( A e. RR -> A <_ A ) | GUARD_OK |
| `letr` | t <_ r ; r <_ s | A <_ B ; B <_ C | A e. RR ; B e. RR ; C e. RR | letr $p \|- ( ( A e. RR /\ B e. RR /\ C e. RR ) -> ( ( A <_ B /\ B <_ C ) -> A <_ C ) ) | GUARD_OK |
| `letot` | -. t <_ r | - | A e. RR ; B e. RR | letric $p \|- ( ( A e. RR /\ B e. RR ) -> ( A <_ B \/ B <_ A ) ) | GUARD_OK |
| `leasym` | t <_ r ; r <_ t | - | A e. RR ; B e. RR | letri3 $p \|- ( ( A e. RR /\ B e. RR ) -> ( A = B <-> ( A <_ B /\ B <_ A ) ) ) | GUARD_OK |
| `leadd` | t <_ r | - | A e. RR ; B e. RR ; C e. RR | leadd1 $p \|- ( ( A e. RR /\ B e. RR /\ C e. RR ) -> ( A <_ B <-> ( A + C ) <_ ( B + C ) ) ) | GUARD_OK |
| `lemul` | 0 <_ t ; 0 <_ r | 0 <_ A ; 0 <_ B | A e. RR ; B e. RR | mulge0 $p \|- ( ( ( A e. RR /\ 0 <_ A ) /\ ( B e. RR /\ 0 <_ B ) ) -> 0 <_ ( A x. B ) ) | GUARD_OK |
| `le01` | - | - | - | 0le1 $p \|- 0 <_ 1 | GUARD_OK |
| `sqrtsq` | 0 <_ t | 0 <_ A | A e. RR | remsqsqrt $p \|- ( ( A e. RR /\ 0 <_ A ) -> ( ( sqrt ` A ) x. ( sqrt ` A ) ) = A ) | GUARD_OK |
| `sqrtge0` | 0 <_ t | 0 <_ A | A e. RR | sqrtge0 $p \|- ( ( A e. RR /\ 0 <_ A ) -> 0 <_ ( sqrt ` A ) ) | GUARD_OK |

Rows where the forms differ (relation IMPLIED): `letot` against `letric`'s
`A <_ B \/ B <_ A`, `leasym` against `letri3`'s two-way form, `leadd` against
`leadd1`'s two-way form, the congruence axioms against `oveq1` / `oveq2` / `fveq2`,
`exp3`..`exp9` against `expp1` with a numeral for N. GUARD_OK there says no set.mm
antecedent is missing; that the algebra.mm form follows from the set.mm form was
read, not computed.

## Every $a statement

Reading of the set.mm column: EXACT the same statement; TYPED the same statement
under set.mm's typing antecedents; IMPLIED follows from the named statement(s), which
are stronger or packaged differently; SYNTAX a syntax statement with a counterpart.

| label | statement | class | result | set.mm | set.mm statement (quoted) |
|---|---|---|---|---|---|
| `n0` | term 0 | syntax | n/a | SYNTAX | `cc0` $a class 0 |
| `n1` | term 1 | syntax | n/a | SYNTAX | `c1` $a class 1 |
| `n2` | term 2 | syntax | n/a | SYNTAX | `c2` $a class 2 |
| `n3` | term 3 | syntax | n/a | SYNTAX | `c3` $a class 3 |
| `n4` | term 4 | syntax | n/a | SYNTAX | `c4` $a class 4 |
| `n5` | term 5 | syntax | n/a | SYNTAX | `c5` $a class 5 |
| `n6` | term 6 | syntax | n/a | SYNTAX | `c6` $a class 6 |
| `n7` | term 7 | syntax | n/a | SYNTAX | `c7` $a class 7 |
| `n8` | term 8 | syntax | n/a | SYNTAX | `c8` $a class 8 |
| `n9` | term 9 | syntax | n/a | SYNTAX | `c9` $a class 9 |
| `tadd` | term ( t + r ) | syntax | n/a | SYNTAX | `co` $a class ( A F B ); `caddc` $a class + (co with F := +) |
| `tsub` | term ( t - r ) | syntax | n/a | SYNTAX | `co` $a class ( A F B ); `cmin` $a class - (co with F := -) |
| `tmul` | term ( t * r ) | syntax | n/a | SYNTAX | `co` $a class ( A F B ); `cmul` $a class x. (co with F := x.) |
| `tdiv` | term ( t / r ) | syntax | n/a | SYNTAX | `co` $a class ( A F B ); `cdiv` $a class / (co with F := /) |
| `tpow` | term ( t ^ r ) | syntax | n/a | SYNTAX | `co` $a class ( A F B ); `cexp` $a class ^ (co with F := ^) |
| `tsqrt` | term ( sqrt t ) | syntax | n/a | SYNTAX | `cfv` $a class ( F ` A ); `csqrt` $a class sqrt (cfv with F := sqrt) |
| `tneg` | term -u t | syntax | n/a | SYNTAX | `cneg` $a class -u A |
| `weq` | wff t = r | syntax | n/a | SYNTAX | `wceq` $a wff A = B |
| `wle` | wff t <_ r | syntax | n/a | SYNTAX | `wbr` $a wff A R B; `cle` $a class <_ (wbr with R := <_) |
| `wn` | wff -. ph | syntax | n/a | SYNTAX | `wn` $a wff -. ph |
| `wi` | wff ( ph -> ps ) | syntax | n/a | SYNTAX | `wi` $a wff ( ph -> ps ) |
| `wa` | wff ( ph /\ ps ) | syntax | n/a | SYNTAX | `wa` $a wff ( ph /\ ps ) |
| `ax-mp` | \|- ps given \|- ph ; \|- ( ph -> ps ) | propositional | DERIVED: truth_table | EXACT | `ax-mp` $a \|- ps given \|- ph ; \|- ( ph -> ps ) |
| `ax-1` | \|- ( ph -> ( ps -> ph ) ) | propositional | DERIVED: truth_table | EXACT | `ax-1` $a \|- ( ph -> ( ps -> ph ) ) |
| `ax-2` | \|- ( ( ph -> ( ps -> ch ) ) -> ( ( ph -> ps ) -> ( ph -> ch ) ) ) | propositional | DERIVED: truth_table | EXACT | `ax-2` $a \|- ( ( ph -> ( ps -> ch ) ) -> ( ( ph -> ps ) -> ( ph -> ch ) ) ) |
| `ax-3` | \|- ( ( -. ph -> -. ps ) -> ( ps -> ph ) ) | propositional | DERIVED: truth_table | EXACT | `ax-3` $a \|- ( ( -. ph -> -. ps ) -> ( ps -> ph ) ) |
| `ax-simpl` | \|- ( ( ph /\ ps ) -> ph ) | propositional | DERIVED: truth_table | EXACT | `simpl` $p \|- ( ( ph /\ ps ) -> ph ) (a theorem in set.mm, an axiom here) |
| `ax-simpr` | \|- ( ( ph /\ ps ) -> ps ) | propositional | DERIVED: truth_table | EXACT | `simpr` $p \|- ( ( ph /\ ps ) -> ps ) (a theorem in set.mm, an axiom here) |
| `ax-conj` | \|- ( ph -> ( ps -> ( ph /\ ps ) ) ) | propositional | DERIVED: truth_table | EXACT | `pm3.2` $p \|- ( ph -> ( ps -> ( ph /\ ps ) ) ) (a theorem in set.mm, an axiom here) |
| `eqid` | \|- t = t | equational | DERIVED: polynomial_identity_by_points, grid 2 | EXACT | `eqid` $p \|- A = A |
| `eqcom` | \|- ( t = r -> r = t ) | conditional | sampled: 162 true, 0 not decided, 0 false; truth in model DERIVED via the map | IMPLIED | `eqcom` $p \|- ( A = B <-> B = A ) (set.mm states the two-way form) |
| `eqtr` | \|- ( ( t = r /\ r = s ) -> t = s ) | conditional | sampled: 1458 true, 0 not decided, 0 false; truth in model DERIVED via the map | EXACT | `eqtr` $p \|- ( ( A = B /\ B = C ) -> A = C ) |
| `addeq1` | \|- ( t = r -> ( t + s ) = ( r + s ) ) | conditional | sampled: 1458 true, 0 not decided, 0 false; truth in model DERIVED via the map | IMPLIED | `oveq1` $p \|- ( A = B -> ( A F C ) = ( B F C ) ) (oveq1 with F := +) |
| `addeq2` | \|- ( t = r -> ( s + t ) = ( s + r ) ) | conditional | sampled: 1458 true, 0 not decided, 0 false; truth in model DERIVED via the map | IMPLIED | `oveq2` $p \|- ( A = B -> ( C F A ) = ( C F B ) ) (oveq2 with F := +) |
| `subeq1` | \|- ( t = r -> ( t - s ) = ( r - s ) ) | conditional | sampled: 1458 true, 0 not decided, 0 false; truth in model DERIVED via the map | IMPLIED | `oveq1` $p \|- ( A = B -> ( A F C ) = ( B F C ) ) (oveq1 with F := -) |
| `subeq2` | \|- ( t = r -> ( s - t ) = ( s - r ) ) | conditional | sampled: 1458 true, 0 not decided, 0 false; truth in model DERIVED via the map | IMPLIED | `oveq2` $p \|- ( A = B -> ( C F A ) = ( C F B ) ) (oveq2 with F := -) |
| `muleq1` | \|- ( t = r -> ( t * s ) = ( r * s ) ) | conditional | sampled: 1458 true, 0 not decided, 0 false; truth in model DERIVED via the map | IMPLIED | `oveq1` $p \|- ( A = B -> ( A F C ) = ( B F C ) ) (oveq1 with F := x.) |
| `muleq2` | \|- ( t = r -> ( s * t ) = ( s * r ) ) | conditional | sampled: 1458 true, 0 not decided, 0 false; truth in model DERIVED via the map | IMPLIED | `oveq2` $p \|- ( A = B -> ( C F A ) = ( C F B ) ) (oveq2 with F := x.) |
| `diveq1` | \|- ( t = r -> ( t / s ) = ( r / s ) ) | conditional | sampled: 1458 true, 0 not decided, 0 false; truth in model DERIVED via the map | IMPLIED | `oveq1` $p \|- ( A = B -> ( A F C ) = ( B F C ) ) (oveq1 with F := /) |
| `diveq2` | \|- ( t = r -> ( s / t ) = ( s / r ) ) | conditional | sampled: 1458 true, 0 not decided, 0 false; truth in model DERIVED via the map | IMPLIED | `oveq2` $p \|- ( A = B -> ( C F A ) = ( C F B ) ) (oveq2 with F := /) |
| `poweq1` | \|- ( t = r -> ( t ^ s ) = ( r ^ s ) ) | conditional | sampled: 1458 true, 0 not decided, 0 false; truth in model DERIVED via the map | IMPLIED | `oveq1` $p \|- ( A = B -> ( A F C ) = ( B F C ) ) (oveq1 with F := ^) |
| `sqrteq` | \|- ( t = r -> ( sqrt t ) = ( sqrt r ) ) | conditional | sampled: 162 true, 0 not decided, 0 false; truth in model DERIVED via the map | IMPLIED | `fveq2` $p \|- ( A = B -> ( F ` A ) = ( F ` B ) ) (fveq2 with F := sqrt) |
| `negeq` | \|- ( t = r -> -u t = -u r ) | conditional | sampled: 162 true, 0 not decided, 0 false; truth in model DERIVED via the map | EXACT | `negeq` $p \|- ( A = B -> -u A = -u B ) |
| `leeq1` | \|- ( t = r -> ( t <_ s -> r <_ s ) ) | conditional | sampled: 1458 true, 0 not decided, 0 false; truth in model DERIVED via the map | IMPLIED | `breq1` $p \|- ( A = B -> ( A R C <-> B R C ) ) (breq1 with R := <_ ; set.mm states the two-way form) |
| `leeq2` | \|- ( t = r -> ( s <_ t -> s <_ r ) ) | conditional | sampled: 1458 true, 0 not decided, 0 false; truth in model DERIVED via the map | IMPLIED | `breq2` $p \|- ( A = B -> ( C R A <-> C R B ) ) (breq2 with R := <_ ; set.mm states the two-way form) |
| `addcom` | \|- ( t + r ) = ( r + t ) | equational | DERIVED: polynomial_identity_by_points, grid 4 | TYPED | `addcom` $p \|- ( ( A e. CC /\ B e. CC ) -> ( A + B ) = ( B + A ) ) |
| `addass` | \|- ( ( t + r ) + s ) = ( t + ( r + s ) ) | equational | DERIVED: polynomial_identity_by_points, grid 8 | TYPED | `addass` $p \|- ( ( A e. CC /\ B e. CC /\ C e. CC ) -> ( ( A + B ) + C ) = ( A + ( B + C ) ) ) |
| `add0` | \|- ( t + 0 ) = t | equational | DERIVED: polynomial_identity_by_points, grid 2 | TYPED | `addrid` $p \|- ( A e. CC -> ( A + 0 ) = A ) |
| `addneg` | \|- ( t + -u t ) = 0 | equational | DERIVED: polynomial_identity_by_points, grid 2 | TYPED | `negid` $p \|- ( A e. CC -> ( A + -u A ) = 0 ) |
| `subdef` | \|- ( t - r ) = ( t + -u r ) | equational | DERIVED: polynomial_identity_by_points, grid 4 | TYPED | `negsub` $p \|- ( ( A e. CC /\ B e. CC ) -> ( A + -u B ) = ( A - B ) ) (set.mm writes the equation the other way round) |
| `mulcom` | \|- ( t * r ) = ( r * t ) | equational | DERIVED: polynomial_identity_by_points, grid 4 | TYPED | `mulcom` $p \|- ( ( A e. CC /\ B e. CC ) -> ( A x. B ) = ( B x. A ) ) |
| `mulass` | \|- ( ( t * r ) * s ) = ( t * ( r * s ) ) | equational | DERIVED: polynomial_identity_by_points, grid 8 | TYPED | `mulass` $p \|- ( ( A e. CC /\ B e. CC /\ C e. CC ) -> ( ( A x. B ) x. C ) = ( A x. ( B x. C ) ) ) |
| `mul1` | \|- ( t * 1 ) = t | equational | DERIVED: polynomial_identity_by_points, grid 2 | TYPED | `mulrid` $p \|- ( A e. CC -> ( A x. 1 ) = A ) |
| `distr` | \|- ( t * ( r + s ) ) = ( ( t * r ) + ( t * s ) ) | equational | DERIVED: polynomial_identity_by_points, grid 8 | TYPED | `adddi` $p \|- ( ( A e. CC /\ B e. CC /\ C e. CC ) -> ( A x. ( B + C ) ) = ( ( A x. B ) + ( A x. C ) ) ) |
| `divmul` | \|- ( -. r = 0 -> ( ( t / r ) * r ) = t ) | conditional | sampled: 162 true, 0 not decided, 0 false; truth in model DERIVED via the map | TYPED | `divcan1` $p \|- ( ( A e. CC /\ B e. CC /\ B =/= 0 ) -> ( ( A / B ) x. B ) = A ) (set.mm writes B =/= 0 for -. B = 0) |
| `ne01` | \|- -. 0 = 1 | conditional | sampled: 2 true, 0 not decided, 0 false; truth in model DERIVED via the map | IMPLIED | `0ne1` $p \|- 0 =/= 1 (set.mm writes 0 =/= 1) |
| `df-2` | \|- 2 = ( 1 + 1 ) | equational | HOLDS: exact arithmetic, no variables | EXACT | `df-2` $a \|- 2 = ( 1 + 1 ) |
| `df-3` | \|- 3 = ( 2 + 1 ) | equational | HOLDS: exact arithmetic, no variables | EXACT | `df-3` $a \|- 3 = ( 2 + 1 ) |
| `df-4` | \|- 4 = ( 3 + 1 ) | equational | HOLDS: exact arithmetic, no variables | EXACT | `df-4` $a \|- 4 = ( 3 + 1 ) |
| `df-5` | \|- 5 = ( 4 + 1 ) | equational | HOLDS: exact arithmetic, no variables | EXACT | `df-5` $a \|- 5 = ( 4 + 1 ) |
| `df-6` | \|- 6 = ( 5 + 1 ) | equational | HOLDS: exact arithmetic, no variables | EXACT | `df-6` $a \|- 6 = ( 5 + 1 ) |
| `df-7` | \|- 7 = ( 6 + 1 ) | equational | HOLDS: exact arithmetic, no variables | EXACT | `df-7` $a \|- 7 = ( 6 + 1 ) |
| `df-8` | \|- 8 = ( 7 + 1 ) | equational | HOLDS: exact arithmetic, no variables | EXACT | `df-8` $a \|- 8 = ( 7 + 1 ) |
| `df-9` | \|- 9 = ( 8 + 1 ) | equational | HOLDS: exact arithmetic, no variables | EXACT | `df-9` $a \|- 9 = ( 8 + 1 ) |
| `exp0` | \|- ( t ^ 0 ) = 1 | equational | HOLDS: interval tier | TYPED | `exp0` $p \|- ( A e. CC -> ( A ^ 0 ) = 1 ) |
| `exp1` | \|- ( t ^ 1 ) = t | equational | DERIVED: polynomial_identity_by_points, grid 2 | TYPED | `exp1` $p \|- ( A e. CC -> ( A ^ 1 ) = A ) |
| `exp2` | \|- ( t ^ 2 ) = ( t * t ) | equational | DERIVED: polynomial_identity_by_points, grid 3 | TYPED | `sqval` $p \|- ( A e. CC -> ( A ^ 2 ) = ( A x. A ) ) |
| `exp3` | \|- ( t ^ 3 ) = ( ( t ^ 2 ) * t ) | equational | DERIVED: polynomial_identity_by_points, grid 4 | IMPLIED | `expp1` $p \|- ( ( A e. CC /\ N e. NN0 ) -> ( A ^ ( N + 1 ) ) = ( ( A ^ N ) x. A ) ); `df-3` $a \|- 3 = ( 2 + 1 ) (expp1 with N := 2, and df-3) |
| `exp4` | \|- ( t ^ 4 ) = ( ( t ^ 3 ) * t ) | equational | DERIVED: polynomial_identity_by_points, grid 5 | IMPLIED | `expp1` $p \|- ( ( A e. CC /\ N e. NN0 ) -> ( A ^ ( N + 1 ) ) = ( ( A ^ N ) x. A ) ); `df-4` $a \|- 4 = ( 3 + 1 ) (expp1 with N := 3, and df-4) |
| `exp5` | \|- ( t ^ 5 ) = ( ( t ^ 4 ) * t ) | equational | DERIVED: polynomial_identity_by_points, grid 6 | IMPLIED | `expp1` $p \|- ( ( A e. CC /\ N e. NN0 ) -> ( A ^ ( N + 1 ) ) = ( ( A ^ N ) x. A ) ); `df-5` $a \|- 5 = ( 4 + 1 ) (expp1 with N := 4, and df-5) |
| `exp6` | \|- ( t ^ 6 ) = ( ( t ^ 5 ) * t ) | equational | DERIVED: polynomial_identity_by_points, grid 7 | IMPLIED | `expp1` $p \|- ( ( A e. CC /\ N e. NN0 ) -> ( A ^ ( N + 1 ) ) = ( ( A ^ N ) x. A ) ); `df-6` $a \|- 6 = ( 5 + 1 ) (expp1 with N := 5, and df-6) |
| `exp7` | \|- ( t ^ 7 ) = ( ( t ^ 6 ) * t ) | equational | DERIVED: polynomial_identity_by_points, grid 8 | IMPLIED | `expp1` $p \|- ( ( A e. CC /\ N e. NN0 ) -> ( A ^ ( N + 1 ) ) = ( ( A ^ N ) x. A ) ); `df-7` $a \|- 7 = ( 6 + 1 ) (expp1 with N := 6, and df-7) |
| `exp8` | \|- ( t ^ 8 ) = ( ( t ^ 7 ) * t ) | equational | DERIVED: polynomial_identity_by_points, grid 9 | IMPLIED | `expp1` $p \|- ( ( A e. CC /\ N e. NN0 ) -> ( A ^ ( N + 1 ) ) = ( ( A ^ N ) x. A ) ); `df-8` $a \|- 8 = ( 7 + 1 ) (expp1 with N := 7, and df-8) |
| `exp9` | \|- ( t ^ 9 ) = ( ( t ^ 8 ) * t ) | equational | DERIVED: polynomial_identity_by_points, grid 10 | IMPLIED | `expp1` $p \|- ( ( A e. CC /\ N e. NN0 ) -> ( A ^ ( N + 1 ) ) = ( ( A ^ N ) x. A ) ); `df-9` $a \|- 9 = ( 8 + 1 ) (expp1 with N := 8, and df-9) |
| `leid` | \|- t <_ t | conditional | sampled: 18 true, 0 not decided, 0 false; truth in model DERIVED via the map | TYPED | `leid` $p \|- ( A e. RR -> A <_ A ) |
| `letr` | \|- ( ( t <_ r /\ r <_ s ) -> t <_ s ) | conditional | sampled: 1458 true, 0 not decided, 0 false; truth in model DERIVED via the map | TYPED | `letr` $p \|- ( ( A e. RR /\ B e. RR /\ C e. RR ) -> ( ( A <_ B /\ B <_ C ) -> A <_ C ) ) |
| `letot` | \|- ( -. t <_ r -> r <_ t ) | conditional | sampled: 162 true, 0 not decided, 0 false; truth in model DERIVED via the map | IMPLIED | `letric` $p \|- ( ( A e. RR /\ B e. RR ) -> ( A <_ B \/ B <_ A ) ) (letric states A <_ B \/ B <_ A) |
| `leasym` | \|- ( ( t <_ r /\ r <_ t ) -> t = r ) | conditional | sampled: 162 true, 0 not decided, 0 false; truth in model DERIVED via the map | IMPLIED | `letri3` $p \|- ( ( A e. RR /\ B e. RR ) -> ( A = B <-> ( A <_ B /\ B <_ A ) ) ) (letri3 states the two-way form) |
| `leadd` | \|- ( t <_ r -> ( t + s ) <_ ( r + s ) ) | conditional | sampled: 1458 true, 0 not decided, 0 false; truth in model DERIVED via the map | IMPLIED | `leadd1` $p \|- ( ( A e. RR /\ B e. RR /\ C e. RR ) -> ( A <_ B <-> ( A + C ) <_ ( B + C ) ) ) (leadd1 states the two-way form) |
| `lemul` | \|- ( ( 0 <_ t /\ 0 <_ r ) -> 0 <_ ( t * r ) ) | conditional | sampled: 162 true, 0 not decided, 0 false; truth in model DERIVED via the map | TYPED | `mulge0` $p \|- ( ( ( A e. RR /\ 0 <_ A ) /\ ( B e. RR /\ 0 <_ B ) ) -> 0 <_ ( A x. B ) ) |
| `le01` | \|- 0 <_ 1 | conditional | sampled: 2 true, 0 not decided, 0 false; truth in model DERIVED via the map | EXACT | `0le1` $p \|- 0 <_ 1 |
| `sqrtsq` | \|- ( 0 <_ t -> ( ( sqrt t ) * ( sqrt t ) ) = t ) | conditional | sampled: 18 true, 0 not decided, 0 false; truth in model DERIVED via the map | TYPED | `remsqsqrt` $p \|- ( ( A e. RR /\ 0 <_ A ) -> ( ( sqrt ` A ) x. ( sqrt ` A ) ) = A ) |
| `sqrtge0` | \|- ( 0 <_ t -> 0 <_ ( sqrt t ) ) | conditional | sampled: 18 true, 0 not decided, 0 false; truth in model DERIVED via the map | TYPED | `sqrtge0` $p \|- ( ( A e. RR /\ 0 <_ A ) -> 0 <_ ( sqrt ` A ) ) |

## What this does not establish

```text
second reader  VOID. One reader made the map, the guard table and the model argument.
the map        the step from a set.mm statement to the algebra.mm form (two-way forms,
               a disjunction, an instance of a general operation) was read, not computed
typing         set aside by the one-sort reading; if a term could stand for something
               that is not a real number, the TYPED rows would not carry over
completeness   nothing here says the axioms are enough to prove what one would want
set.mm         its theorems are taken as true of the real numbers; the kernel verified
               set.mm's proofs (branch 2a), not its axioms
```
