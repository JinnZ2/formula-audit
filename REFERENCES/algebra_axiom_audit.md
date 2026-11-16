# Audit of tests/data/algebra.mm

Status: OBSERVED run of `python3 -m kernel.axiom_audit --setmm set.mm` on 2026-11-16.
No axiom FAILS. That is not a proof the axioms are sound: 35 statements are
DERIVED (a polynomial identity proved on a full grid, exact arithmetic, or a
truth table); 26 are PROPOSED (sampled at exact points, no counterexample);
22 are syntax. Co-authored. Observer slots null.

```text
database   tests/data/algebra.mm, 83 $a statements; kernel status of each: OBSERVED, no verdict
set.mm     fetched 2026-11-16, 51,952,199 bytes, sha256 099864b6785c45be...; not in this repository
classes    {"syntax": 22, "propositional": 7, "equational": 28, "conditional": 26}
results    DERIVED 35   PROPOSED (sampled) 26   FAILS 0
set.mm     {"EXACT": 19, "TYPED": 18, "IMPLIED": 24, "SYNTAX": 22, "UNMAPPED": 0}
mutation   66 one-change mutants of 28 equational axioms: 65 FAIL in step 2;
           the 1 not failed is ( t - 0 ) = t, which is a true statement
sampling   values -2 -1 -1/2 0 1/2 1 2 9/4 4 for every term variable, all combinations;
           undefined values (x / 0, sqrt below 0, a non-numeral power) filled in two
           different ways, the statement must hold under both
```

Reading of the set.mm column: EXACT the same statement; TYPED the same statement
under set.mm's `A e. CC` / `A e. RR` antecedents (algebra.mm has one sort, real
numbers); IMPLIED follows from the named statement(s), which are stronger or
packaged differently; SYNTAX a syntax statement with a set.mm counterpart.

| label | statement | class | result | set.mm | set.mm statement (quoted) |
|---|---|---|---|---|---|
| `n0` | `term 0` | syntax | n/a | SYNTAX | `cc0` $a class 0 |
| `n1` | `term 1` | syntax | n/a | SYNTAX | `c1` $a class 1 |
| `n2` | `term 2` | syntax | n/a | SYNTAX | `c2` $a class 2 |
| `n3` | `term 3` | syntax | n/a | SYNTAX | `c3` $a class 3 |
| `n4` | `term 4` | syntax | n/a | SYNTAX | `c4` $a class 4 |
| `n5` | `term 5` | syntax | n/a | SYNTAX | `c5` $a class 5 |
| `n6` | `term 6` | syntax | n/a | SYNTAX | `c6` $a class 6 |
| `n7` | `term 7` | syntax | n/a | SYNTAX | `c7` $a class 7 |
| `n8` | `term 8` | syntax | n/a | SYNTAX | `c8` $a class 8 |
| `n9` | `term 9` | syntax | n/a | SYNTAX | `c9` $a class 9 |
| `tadd` | `term ( t + r )` | syntax | n/a | SYNTAX | `co` $a class ( A F B ); `caddc` $a class + (co with F := +) |
| `tsub` | `term ( t - r )` | syntax | n/a | SYNTAX | `co` $a class ( A F B ); `cmin` $a class - (co with F := -) |
| `tmul` | `term ( t * r )` | syntax | n/a | SYNTAX | `co` $a class ( A F B ); `cmul` $a class x. (co with F := x.) |
| `tdiv` | `term ( t / r )` | syntax | n/a | SYNTAX | `co` $a class ( A F B ); `cdiv` $a class / (co with F := /) |
| `tpow` | `term ( t ^ r )` | syntax | n/a | SYNTAX | `co` $a class ( A F B ); `cexp` $a class ^ (co with F := ^) |
| `tsqrt` | `term ( sqrt t )` | syntax | n/a | SYNTAX | `cfv` $a class ( F ` A ); `csqrt` $a class sqrt (cfv with F := sqrt) |
| `tneg` | `term -u t` | syntax | n/a | SYNTAX | `cneg` $a class -u A |
| `weq` | `wff t = r` | syntax | n/a | SYNTAX | `wceq` $a wff A = B |
| `wle` | `wff t <_ r` | syntax | n/a | SYNTAX | `wbr` $a wff A R B; `cle` $a class <_ (wbr with R := <_) |
| `wn` | `wff -. ph` | syntax | n/a | SYNTAX | `wn` $a wff -. ph |
| `wi` | `wff ( ph -> ps )` | syntax | n/a | SYNTAX | `wi` $a wff ( ph -> ps ) |
| `wa` | `wff ( ph /\ ps )` | syntax | n/a | SYNTAX | `wa` $a wff ( ph /\ ps ) |
| `ax-mp` | `\|- ps given \|- ph ; \|- ( ph -> ps )` | propositional | DERIVED: truth_table | EXACT | `ax-mp` $a \|- ps given \|- ph ; \|- ( ph -> ps ) |
| `ax-1` | `\|- ( ph -> ( ps -> ph ) )` | propositional | DERIVED: truth_table | EXACT | `ax-1` $a \|- ( ph -> ( ps -> ph ) ) |
| `ax-2` | `\|- ( ( ph -> ( ps -> ch ) ) -> ( ( ph -> ps ) -> ( ph -> ch ) ) )` | propositional | DERIVED: truth_table | EXACT | `ax-2` $a \|- ( ( ph -> ( ps -> ch ) ) -> ( ( ph -> ps ) -> ( ph -> ch ) ) ) |
| `ax-3` | `\|- ( ( -. ph -> -. ps ) -> ( ps -> ph ) )` | propositional | DERIVED: truth_table | EXACT | `ax-3` $a \|- ( ( -. ph -> -. ps ) -> ( ps -> ph ) ) |
| `ax-simpl` | `\|- ( ( ph /\ ps ) -> ph )` | propositional | DERIVED: truth_table | EXACT | `simpl` $p \|- ( ( ph /\ ps ) -> ph ) (a theorem in set.mm, an axiom here) |
| `ax-simpr` | `\|- ( ( ph /\ ps ) -> ps )` | propositional | DERIVED: truth_table | EXACT | `simpr` $p \|- ( ( ph /\ ps ) -> ps ) (a theorem in set.mm, an axiom here) |
| `ax-conj` | `\|- ( ph -> ( ps -> ( ph /\ ps ) ) )` | propositional | DERIVED: truth_table | EXACT | `pm3.2` $p \|- ( ph -> ( ps -> ( ph /\ ps ) ) ) (a theorem in set.mm, an axiom here) |
| `eqid` | `\|- t = t` | equational | DERIVED: polynomial_identity_by_points, grid 2 | EXACT | `eqid` $p \|- A = A |
| `eqcom` | `\|- ( t = r -> r = t )` | conditional | PROPOSED: 162 true, 0 not decided, 0 false | IMPLIED | `eqcom` $p \|- ( A = B <-> B = A ) (set.mm states the two-way form) |
| `eqtr` | `\|- ( ( t = r /\ r = s ) -> t = s )` | conditional | PROPOSED: 1458 true, 0 not decided, 0 false | EXACT | `eqtr` $p \|- ( ( A = B /\ B = C ) -> A = C ) |
| `addeq1` | `\|- ( t = r -> ( t + s ) = ( r + s ) )` | conditional | PROPOSED: 1458 true, 0 not decided, 0 false | IMPLIED | `oveq1` $p \|- ( A = B -> ( A F C ) = ( B F C ) ) (oveq1 with F := +) |
| `addeq2` | `\|- ( t = r -> ( s + t ) = ( s + r ) )` | conditional | PROPOSED: 1458 true, 0 not decided, 0 false | IMPLIED | `oveq2` $p \|- ( A = B -> ( C F A ) = ( C F B ) ) (oveq2 with F := +) |
| `subeq1` | `\|- ( t = r -> ( t - s ) = ( r - s ) )` | conditional | PROPOSED: 1458 true, 0 not decided, 0 false | IMPLIED | `oveq1` $p \|- ( A = B -> ( A F C ) = ( B F C ) ) (oveq1 with F := -) |
| `subeq2` | `\|- ( t = r -> ( s - t ) = ( s - r ) )` | conditional | PROPOSED: 1458 true, 0 not decided, 0 false | IMPLIED | `oveq2` $p \|- ( A = B -> ( C F A ) = ( C F B ) ) (oveq2 with F := -) |
| `muleq1` | `\|- ( t = r -> ( t * s ) = ( r * s ) )` | conditional | PROPOSED: 1458 true, 0 not decided, 0 false | IMPLIED | `oveq1` $p \|- ( A = B -> ( A F C ) = ( B F C ) ) (oveq1 with F := x.) |
| `muleq2` | `\|- ( t = r -> ( s * t ) = ( s * r ) )` | conditional | PROPOSED: 1458 true, 0 not decided, 0 false | IMPLIED | `oveq2` $p \|- ( A = B -> ( C F A ) = ( C F B ) ) (oveq2 with F := x.) |
| `diveq1` | `\|- ( t = r -> ( t / s ) = ( r / s ) )` | conditional | PROPOSED: 1458 true, 0 not decided, 0 false | IMPLIED | `oveq1` $p \|- ( A = B -> ( A F C ) = ( B F C ) ) (oveq1 with F := /) |
| `diveq2` | `\|- ( t = r -> ( s / t ) = ( s / r ) )` | conditional | PROPOSED: 1458 true, 0 not decided, 0 false | IMPLIED | `oveq2` $p \|- ( A = B -> ( C F A ) = ( C F B ) ) (oveq2 with F := /) |
| `poweq1` | `\|- ( t = r -> ( t ^ s ) = ( r ^ s ) )` | conditional | PROPOSED: 1458 true, 0 not decided, 0 false | IMPLIED | `oveq1` $p \|- ( A = B -> ( A F C ) = ( B F C ) ) (oveq1 with F := ^) |
| `sqrteq` | `\|- ( t = r -> ( sqrt t ) = ( sqrt r ) )` | conditional | PROPOSED: 158 true, 4 not decided, 0 false | IMPLIED | `fveq2` $p \|- ( A = B -> ( F ` A ) = ( F ` B ) ) (fveq2 with F := sqrt) |
| `negeq` | `\|- ( t = r -> -u t = -u r )` | conditional | PROPOSED: 162 true, 0 not decided, 0 false | EXACT | `negeq` $p \|- ( A = B -> -u A = -u B ) |
| `leeq1` | `\|- ( t = r -> ( t <_ s -> r <_ s ) )` | conditional | PROPOSED: 1458 true, 0 not decided, 0 false | IMPLIED | `breq1` $p \|- ( A = B -> ( A R C <-> B R C ) ) (breq1 with R := <_ ; set.mm states the two-way form) |
| `leeq2` | `\|- ( t = r -> ( s <_ t -> s <_ r ) )` | conditional | PROPOSED: 1458 true, 0 not decided, 0 false | IMPLIED | `breq2` $p \|- ( A = B -> ( C R A <-> C R B ) ) (breq2 with R := <_ ; set.mm states the two-way form) |
| `addcom` | `\|- ( t + r ) = ( r + t )` | equational | DERIVED: polynomial_identity_by_points, grid 4 | TYPED | `addcom` $p \|- ( ( A e. CC /\ B e. CC ) -> ( A + B ) = ( B + A ) ) |
| `addass` | `\|- ( ( t + r ) + s ) = ( t + ( r + s ) )` | equational | DERIVED: polynomial_identity_by_points, grid 8 | TYPED | `addass` $p \|- ( ( A e. CC /\ B e. CC /\ C e. CC ) -> ( ( A + B ) + C ) = ( A + ( B + C ) ) ) |
| `add0` | `\|- ( t + 0 ) = t` | equational | DERIVED: polynomial_identity_by_points, grid 2 | TYPED | `addrid` $p \|- ( A e. CC -> ( A + 0 ) = A ) |
| `addneg` | `\|- ( t + -u t ) = 0` | equational | DERIVED: polynomial_identity_by_points, grid 2 | TYPED | `negid` $p \|- ( A e. CC -> ( A + -u A ) = 0 ) |
| `subdef` | `\|- ( t - r ) = ( t + -u r )` | equational | DERIVED: polynomial_identity_by_points, grid 4 | TYPED | `negsub` $p \|- ( ( A e. CC /\ B e. CC ) -> ( A + -u B ) = ( A - B ) ) (set.mm writes the equation the other way round) |
| `mulcom` | `\|- ( t * r ) = ( r * t )` | equational | DERIVED: polynomial_identity_by_points, grid 4 | TYPED | `mulcom` $p \|- ( ( A e. CC /\ B e. CC ) -> ( A x. B ) = ( B x. A ) ) |
| `mulass` | `\|- ( ( t * r ) * s ) = ( t * ( r * s ) )` | equational | DERIVED: polynomial_identity_by_points, grid 8 | TYPED | `mulass` $p \|- ( ( A e. CC /\ B e. CC /\ C e. CC ) -> ( ( A x. B ) x. C ) = ( A x. ( B x. C ) ) ) |
| `mul1` | `\|- ( t * 1 ) = t` | equational | DERIVED: polynomial_identity_by_points, grid 2 | TYPED | `mulrid` $p \|- ( A e. CC -> ( A x. 1 ) = A ) |
| `distr` | `\|- ( t * ( r + s ) ) = ( ( t * r ) + ( t * s ) )` | equational | DERIVED: polynomial_identity_by_points, grid 8 | TYPED | `adddi` $p \|- ( ( A e. CC /\ B e. CC /\ C e. CC ) -> ( A x. ( B + C ) ) = ( ( A x. B ) + ( A x. C ) ) ) |
| `divmul` | `\|- ( -. r = 0 -> ( ( t / r ) * r ) = t )` | conditional | PROPOSED: 162 true, 0 not decided, 0 false | TYPED | `divcan1` $p \|- ( ( A e. CC /\ B e. CC /\ B =/= 0 ) -> ( ( A / B ) x. B ) = A ) (set.mm writes B =/= 0 for -. B = 0) |
| `ne01` | `\|- -. 0 = 1` | conditional | PROPOSED: 2 true, 0 not decided, 0 false | IMPLIED | `0ne1` $p \|- 0 =/= 1 (set.mm writes 0 =/= 1) |
| `df-2` | `\|- 2 = ( 1 + 1 )` | equational | HOLDS: exact arithmetic, no variables | EXACT | `df-2` $a \|- 2 = ( 1 + 1 ) |
| `df-3` | `\|- 3 = ( 2 + 1 )` | equational | HOLDS: exact arithmetic, no variables | EXACT | `df-3` $a \|- 3 = ( 2 + 1 ) |
| `df-4` | `\|- 4 = ( 3 + 1 )` | equational | HOLDS: exact arithmetic, no variables | EXACT | `df-4` $a \|- 4 = ( 3 + 1 ) |
| `df-5` | `\|- 5 = ( 4 + 1 )` | equational | HOLDS: exact arithmetic, no variables | EXACT | `df-5` $a \|- 5 = ( 4 + 1 ) |
| `df-6` | `\|- 6 = ( 5 + 1 )` | equational | HOLDS: exact arithmetic, no variables | EXACT | `df-6` $a \|- 6 = ( 5 + 1 ) |
| `df-7` | `\|- 7 = ( 6 + 1 )` | equational | HOLDS: exact arithmetic, no variables | EXACT | `df-7` $a \|- 7 = ( 6 + 1 ) |
| `df-8` | `\|- 8 = ( 7 + 1 )` | equational | HOLDS: exact arithmetic, no variables | EXACT | `df-8` $a \|- 8 = ( 7 + 1 ) |
| `df-9` | `\|- 9 = ( 8 + 1 )` | equational | HOLDS: exact arithmetic, no variables | EXACT | `df-9` $a \|- 9 = ( 8 + 1 ) |
| `exp0` | `\|- ( t ^ 0 ) = 1` | equational | HOLDS: interval tier | TYPED | `exp0` $p \|- ( A e. CC -> ( A ^ 0 ) = 1 ) |
| `exp1` | `\|- ( t ^ 1 ) = t` | equational | DERIVED: polynomial_identity_by_points, grid 2 | TYPED | `exp1` $p \|- ( A e. CC -> ( A ^ 1 ) = A ) |
| `exp2` | `\|- ( t ^ 2 ) = ( t * t )` | equational | DERIVED: polynomial_identity_by_points, grid 3 | TYPED | `sqval` $p \|- ( A e. CC -> ( A ^ 2 ) = ( A x. A ) ) |
| `exp3` | `\|- ( t ^ 3 ) = ( ( t ^ 2 ) * t )` | equational | DERIVED: polynomial_identity_by_points, grid 4 | IMPLIED | `expp1` $p \|- ( ( A e. CC /\ N e. NN0 ) -> ( A ^ ( N + 1 ) ) = ( ( A ^ N ) x. A ) ); `df-3` $a \|- 3 = ( 2 + 1 ) (expp1 with N := 2, and df-3) |
| `exp4` | `\|- ( t ^ 4 ) = ( ( t ^ 3 ) * t )` | equational | DERIVED: polynomial_identity_by_points, grid 5 | IMPLIED | `expp1` $p \|- ( ( A e. CC /\ N e. NN0 ) -> ( A ^ ( N + 1 ) ) = ( ( A ^ N ) x. A ) ); `df-4` $a \|- 4 = ( 3 + 1 ) (expp1 with N := 3, and df-4) |
| `exp5` | `\|- ( t ^ 5 ) = ( ( t ^ 4 ) * t )` | equational | DERIVED: polynomial_identity_by_points, grid 6 | IMPLIED | `expp1` $p \|- ( ( A e. CC /\ N e. NN0 ) -> ( A ^ ( N + 1 ) ) = ( ( A ^ N ) x. A ) ); `df-5` $a \|- 5 = ( 4 + 1 ) (expp1 with N := 4, and df-5) |
| `exp6` | `\|- ( t ^ 6 ) = ( ( t ^ 5 ) * t )` | equational | DERIVED: polynomial_identity_by_points, grid 7 | IMPLIED | `expp1` $p \|- ( ( A e. CC /\ N e. NN0 ) -> ( A ^ ( N + 1 ) ) = ( ( A ^ N ) x. A ) ); `df-6` $a \|- 6 = ( 5 + 1 ) (expp1 with N := 5, and df-6) |
| `exp7` | `\|- ( t ^ 7 ) = ( ( t ^ 6 ) * t )` | equational | DERIVED: polynomial_identity_by_points, grid 8 | IMPLIED | `expp1` $p \|- ( ( A e. CC /\ N e. NN0 ) -> ( A ^ ( N + 1 ) ) = ( ( A ^ N ) x. A ) ); `df-7` $a \|- 7 = ( 6 + 1 ) (expp1 with N := 6, and df-7) |
| `exp8` | `\|- ( t ^ 8 ) = ( ( t ^ 7 ) * t )` | equational | DERIVED: polynomial_identity_by_points, grid 9 | IMPLIED | `expp1` $p \|- ( ( A e. CC /\ N e. NN0 ) -> ( A ^ ( N + 1 ) ) = ( ( A ^ N ) x. A ) ); `df-8` $a \|- 8 = ( 7 + 1 ) (expp1 with N := 7, and df-8) |
| `exp9` | `\|- ( t ^ 9 ) = ( ( t ^ 8 ) * t )` | equational | DERIVED: polynomial_identity_by_points, grid 10 | IMPLIED | `expp1` $p \|- ( ( A e. CC /\ N e. NN0 ) -> ( A ^ ( N + 1 ) ) = ( ( A ^ N ) x. A ) ); `df-9` $a \|- 9 = ( 8 + 1 ) (expp1 with N := 8, and df-9) |
| `leid` | `\|- t <_ t` | conditional | PROPOSED: 18 true, 0 not decided, 0 false | TYPED | `leid` $p \|- ( A e. RR -> A <_ A ) |
| `letr` | `\|- ( ( t <_ r /\ r <_ s ) -> t <_ s )` | conditional | PROPOSED: 1458 true, 0 not decided, 0 false | TYPED | `letr` $p \|- ( ( A e. RR /\ B e. RR /\ C e. RR ) -> ( ( A <_ B /\ B <_ C ) -> A <_ C ) ) |
| `letot` | `\|- ( -. t <_ r -> r <_ t )` | conditional | PROPOSED: 162 true, 0 not decided, 0 false | IMPLIED | `letric` $p \|- ( ( A e. RR /\ B e. RR ) -> ( A <_ B \/ B <_ A ) ) (letric states A <_ B \/ B <_ A) |
| `leasym` | `\|- ( ( t <_ r /\ r <_ t ) -> t = r )` | conditional | PROPOSED: 162 true, 0 not decided, 0 false | IMPLIED | `letri3` $p \|- ( ( A e. RR /\ B e. RR ) -> ( A = B <-> ( A <_ B /\ B <_ A ) ) ) (letri3 states the two-way form) |
| `leadd` | `\|- ( t <_ r -> ( t + s ) <_ ( r + s ) )` | conditional | PROPOSED: 1458 true, 0 not decided, 0 false | IMPLIED | `leadd1` $p \|- ( ( A e. RR /\ B e. RR /\ C e. RR ) -> ( A <_ B <-> ( A + C ) <_ ( B + C ) ) ) (leadd1 states the two-way form) |
| `lemul` | `\|- ( ( 0 <_ t /\ 0 <_ r ) -> 0 <_ ( t * r ) )` | conditional | PROPOSED: 162 true, 0 not decided, 0 false | TYPED | `mulge0` $p \|- ( ( ( A e. RR /\ 0 <_ A ) /\ ( B e. RR /\ 0 <_ B ) ) -> 0 <_ ( A x. B ) ) |
| `le01` | `\|- 0 <_ 1` | conditional | PROPOSED: 2 true, 0 not decided, 0 false | EXACT | `0le1` $p \|- 0 <_ 1 |
| `sqrtsq` | `\|- ( 0 <_ t -> ( ( sqrt t ) * ( sqrt t ) ) = t )` | conditional | PROPOSED: 14 true, 4 not decided, 0 false | TYPED | `remsqsqrt` $p \|- ( ( A e. RR /\ 0 <_ A ) -> ( ( sqrt ` A ) x. ( sqrt ` A ) ) = A ) |
| `sqrtge0` | `\|- ( 0 <_ t -> 0 <_ ( sqrt t ) )` | conditional | PROPOSED: 18 true, 0 not decided, 0 false | TYPED | `sqrtge0` $p \|- ( ( A e. RR /\ 0 <_ A ) -> 0 <_ ( sqrt ` A ) ) |

## What this does not establish

```text
soundness     a sampled check finds counterexamples; it does not prove there are none.
              The 26 conditional axioms rest on sampling and on the set.mm map.
the map       made by reading: the correspondence between an untyped axiom here and a
              typed set.mm theorem was not checked by any program
one sort      algebra.mm treats every term as a real number, including ( t / 0 ) and
              ( sqrt t ) for t below 0, which set.mm does not. The axioms were checked
              to hold whatever value such a term is given (two fill-ins), which is the
              reading under which leid, letot and the congruence axioms are stated.
consistency   not examined: nothing here shows the axioms do not contradict each other
```
