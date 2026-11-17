# formula-audit

Status: branch 1 (unit audit) is implemented and passes its own tests within
tested scope. Its slots (limit, sign, magnitude range) are recorded, NOT
checked. Its scanner is a placeholder. Branch 2a (proof kernel) is implemented
and passes its own tests within tested scope; it reads Metamath databases
only. Branch 2b (data points and intersections) is implemented and passes its
own tests within tested scope; only its interval tier is rigorous. The seam
from 2b's proposals to the 2a kernel is implemented, with no proof search and a
hand-written axiom file audited by one reader (second reader: VOID). Branch 4
(word slots, v2 with a DEGRADED verdict) and branch 5 (inference ladder) are
implemented and pass their own tests within tested scope; the ladder's caps are PROPOSED defaults and its worked
case uses constructed numbers. Branch 4's
shipped place table is an example, every entry PROPOSED. Branch 3 (the glyph)
is implemented as a v0 that passes its own tests within tested scope; its tool
table is four PROPOSED tools and nothing it writes is above PROPOSED. Three known
blind spots of branch 1 are listed below
and are not built.

License: CC0 1.0. Co-authored (human + AI). Stdlib only, phone-runnable.

In plain words: small checkers for formulas and claims. `unitaudit` asks whether
both sides of a formula have the same physical dimensions. `kernel` checks
Metamath proofs step by step. `numcheck` asks whether a formula holds at given
values, and lets only exact interval arithmetic decide. `wordslots`, `infer`
and `glyph` (branches 4, 5 and 3) carry claims, rival hypotheses and next steps
with their status tags. Each one records what it could not establish (VOID,
UNDECIDED, UNCHECKED) instead of guessing.

Try it (Python 3, nothing to install):

```sh
python3 -m unittest discover -s tests
python3 -m unitaudit check formulas.json
python3 -m numcheck check checks.json
```

Before relying on a result, read [READING_NOTES.md](READING_NOTES.md): it lists
the misreads a careful outside reader has already made. Concrete examples in
this README are checked against the code by `tests/test_readme_claims.py`;
`python3 tests/test_readme_claims.py --hunt` lists the ones not yet checked.

## Branches

```text
branch 1   unit audit      unitaudit/   BUILT: dimension check, PASS / FAIL / VOID
branch 2a  proof kernel    kernel/      BUILT: Metamath .mm reader and proof verifier
branch 2b  data points     numcheck/     BUILT: interval arithmetic, three tiers, point
                                         checks, intersections over a box
branch 3   glyph           glyph/       BUILT (v0): gate, options with inaction drift cost,
                                        one step at a time; tool table v0, all PROPOSED
branch 4   word slots      wordslots/   BUILT: place table, claim records, slot check;
                                        numeric slot bounds handed to branch 2b
branch 5   inference       infer/       BUILT: rival hypotheses, typed evidence with caps,
           ladder                       exact posteriors, direction signal for branch 3
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
      identity candidate -> "proposal" on the record
                      |  lhs - rhs a polynomial in the interval inputs (+ - *, integer
                      v  powers, rational constants), degree bound d_i per variable?
      0 at every point of a full grid of (d_i + 1) exact values per variable
        -> proof "polynomial_identity_by_points", proposal status DERIVED
      not a polynomial, or grid > 10^4 points -> stays PROPOSED, reason logged

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
              domain, fixed, units, source_check, evidence, polynomial, status,
              proof}. Existing entries are kept; nothing is written without the flag.
              status DERIVED: a polynomial identity, proved by the full-grid check
              (degrees, grid and grid size on the record). status PROPOSED: sampled
              only, for a later proof; why_not_proved says why.
proof scope   a proved polynomial identity holds for ALL values of the interval
              inputs, not only the given domain; every other symbol is a constant
              at its given value, so the identity is proved for those values only
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
FAILS         on interval inputs FAILS can mean "fails on located pieces of the given
              ranges, and no piece holds" (other pieces may still straddle)
lists         a record lists at most 32 pieces of each kind; the counts are complete
candidates    a PROPOSED candidate rests on 7 to 14 sampled points. That is evidence,
              not proof: two different functions can agree at all of them
verdict       a proved identity does not change the check's verdict: the record
              still reads UNDECIDED (exit 3) beside a DERIVED proposal
degree        read from the ast as an upper bound, nothing is expanded; a polynomial
              written with a function or a variable divisor (x*x/x) is non_polynomial
intervals     inputs given as intervals are treated as independent ranges
ONE_FAILS     and MIXED need a whole subbox where a formula fails; a failure at single
              points only reads UNDECIDED
units         branch 1's blind spots carry over: no scale factors, so values are
              taken to be in the stated units as written (km against m is not seen)
powers        integer exponents and 1/2 only; exponent must be a literal number
sin, cos      arguments within +-1000
not built     relative tolerance, inequalities (< <=), more than two formulas
```

## Seam: proposals.json -> kernel

Status: implemented and passing its own tests within tested scope. No proof
search is built: a proof has to be written by someone and put in a file. The
database `tests/data/algebra.mm` was written by hand here. Its axioms were
audited (`REFERENCES/algebra_axiom_audit.md`): none fails, and the PASS route
is OPEN. That audit had one reader; second reader: VOID.

```text
numcheck --proposals proposals.json       identity candidates: {lhs, rhs, domain, status, ...}
        |
        v
python3 -m kernel prove proposals.json
   reader       a file that is not a proposals file -> VOID, nothing read, nothing written
                a malformed entry -> VOID, reported, left unchanged
   id           first 16 hex digits of sha256 over [lhs, rhs, domain]
   translator   lhs = rhs on the domain -> a statement over tests/data/algebra.mm
                  x*x = x**2 on x in [0, 1]  ->  |- ( v0 * v0 ) = ( v0 ^ 2 )
                                                 hypotheses |- 0 <_ v0 ,  |- v0 <_ 1
                untranslatable -> VOID with the reason, entry unchanged
   proof file   proofs/<id>.mm exists?
                  no  -> the entry stays as it was; reason NO_PROOF
                  yes -> database + proof file -> the kernel
                           PASS -> status DERIVED, proof "kernel"
                           FAIL -> the entry stays as it was; located step logged
   write-back   proposals.json updated in place; per entry an append-only history
                (timestamp, route, from, to) and an append-only list of kernel checks
```

```sh
python3 -m kernel prove proposals.json [--proofs DIR] [--db FILE.mm] [--json] [--dry-run]
# exit 0 every entry DERIVED, nothing failed or VOID | 1 a kernel FAIL
#      3 no FAIL; a VOID, or an entry still PROPOSED (NO_PROOF) | 2 usage
```

```text
rests on      a kernel PASS says the proof follows from the axioms of algebra.mm by
              the Metamath rules. Those axioms are GIVEN INPUT: tagged OBSERVED, with
              no verdict, exactly as set.mm's axioms are in branch 2a. The PASS rests
              on them and says nothing about them.
proof file    $e and $p statements and ${ $} only. A file that declares anything
              ($a $c $v $f $d) is VOID. One $p is labelled "target": its statement
              must be the translated one, and its $e hypotheses must be among the
              translated domain bounds. Lemmas ($p) are allowed; all must PASS.
two routes    an entry already DERIVED by polynomial_identity_by_points is left as it
              is. A kernel PASS is added beside it: routes lists both, as two
              independent checks.
withdrawn     a kernel route whose proof no longer checks is withdrawn: the entry goes
              back to PROPOSED if that was its only route. The history keeps both
              changes; nothing is deleted.
translatable  numbers 0 to 9, -n, p/q; + - * /; ** 0 to 9; ** (1/2) and sqrt(); unary
              minus; at most 8 domain variables. A symbol held at a fixed value is
              written as that numeral, so the statement is about that value only.
```

Audit of the axioms (`python3 -m kernel.axiom_audit`)

```text
PASS route     OPEN: no axiom FAILS, no guard row is GUARD_WEAKER or UNCLEAR.
               It would be marked BLOCKED here if either changed.
83 statements  22 syntax; 28 equational and 7 propositional DERIVED (a polynomial
               identity proved on a full grid, exact arithmetic, or a truth table);
               26 conditional sampled at exact points with no counterexample
guard table    45 rows, all GUARD_OK: algebra.mm's guards beside the antecedents of
               the set.mm statement each axiom maps to, typing aside
consistency    model argument (reals + fixed fill), rests on the guard table.
               status DERIVED. The conditional axioms' truth in that model: DERIVED
               via the set.mm map.
second reader  VOID. The map, the guard table and the model argument were made by
               one reader (this build). The slot is for a pass by a different model
               or person; it is empty.
```

Limits of the seam

```text
no search       nothing here looks for a proof
axioms          algebra.mm is small and hand-written (equality, field axioms for
                + - * /, order, sqrt on 0 <_ t, powers 0 to 9). Audited by one
                reader only. An unsound axiom would make every PASS against it
                worthless.
not in it       exp log sin cos tan abs, integers above 9, decimals other than p/q
                with small p and q: untranslatable -> VOID
domain          the bounds become hypotheses the proof MAY use; the statement is
                not weakened or strengthened beyond them
units           the statement is about numbers; the units on the proposal are not
                part of what is proved
```

## Glyph (branch 3 reasoning operator)

Status: the definition below is PROPOSED. `glyph/` implements it as a v0 that
passes its own tests within tested scope (see "What is built" at the end of
this section). The tool table is five PROPOSED tools; whether they are the
right tools, or useful, is not established.

**What it is.** A compressed reasoning operator, in the way a differential
equation is a compressed statement of how something changes. The mark is
notation; the content is the operation. A glyph is defined by what it does
when applied, not by an English label put on it.

```text
                 purpose                       environment
            SOLVE | EXPLORE          units, slots, domains, verdicts,
            (missing -> VOID)        proof state, physics
                    \                        /
                     v                      v
              +-------------------------------------+
              |               GLYPH                 |
              |                                     |
              |  purpose = EXPLORE ?                |
              |    gate, all three must be yes:     |
              |      needed function met?           |
              |      energy surplus?                |
              |      time surplus?                  |
              |    any no  ->  SOLVE                |
              |                                     |
              |  options, inaction among them       |
              |    cost(inaction) = drift between   |
              |    the world and an un-updated      |
              |    self-model; grows with time      |
              |    since the last update; never     |
              |    assumed zero                     |
              +-------------------------------------+
                               |
                               v
               tool choice + one step, recorded
                               |
         EXPLORE result -> PROPOSED -> checked by 2b -> proven by 2a
                               |
                 environment re-read after each step
                               |
                               +----> back to the top
```

**Inputs.**

```text
purpose       SOLVE or EXPLORE. It is an input, given from outside the operator.
              No purpose given -> VOID. It is not guessed and not defaulted.
environment   what the other branches read and report: units (branch 1), slots
              (branch 4), domains and verdicts (branch 2b), proof state (branch
              2a), and physics: the constraints the world puts on the step itself
```

**Gate before EXPLORE.** Three questions, in this order, function first:
is the needed function met, is there an energy surplus, is there a time
surplus. Any "no" turns the purpose to SOLVE. Exploring is what a system
does with surplus, after what it needs is covered.

**Options include inaction.** Doing nothing is always on the list and always
has a cost: the drift between the world and a self-model that was not
updated. That cost grows with the time since the last update. It is never
taken to be zero.

**Output.** A tool choice and one step, both recorded. What EXPLORE returns
is PROPOSED: it is checked by branch 2b and proven by branch 2a before it is
anything more. The environment is read again after every step; a step is
never planned on a reading taken before the last one.

**Related work.** Pointers, with how far each was read. None of these was
used to build anything here.

```text
rational metareasoning,      Lieder & Griffiths. CARRIED: named by a co-author;
strategy selection           not read in this build.
algorithm selection          Rice, 1976. CARRIED: named by a co-author; not read
                             in this build.
resource-rational            arXiv 2408.01253. Abstract page read 2026-11-16:
exploration, meta-BAMDP      Godara and Aleman, "Metareasoning in uncertain
                             environments: a meta-BAMDP framework" (v1 2 Aug
                             2024). The abstract speaks of a resource-rational
                             view of human exploration under cognitive
                             constraints; the words "explore-exploit" are not in
                             it. The body was not read.
```

Added here, beside that work: purpose as an input; the function-first gate;
the drift cost of inaction; physics in the environment. Whether any of the
four is already in that literature was not checked: the claim is PROPOSED.

**Provenance.** The concept comes from an oral tradition and is given here in
translation. The tribe is not named. Co-authored (human + AI).

**What is built** (`glyph/`, v0).

```text
case.json   purpose {mode: SOLVE | EXPLORE, target}; environment: references
            {branch, file, record, sha256, at, rate} to records of branches 1 / 2a / 2b /
            4 / 5; energy_budget and time_budget {available, reserve};
            needed_function_met y / n / VOID; now; gain; units {energy, cost, time,
            drift_rate, gain}; default_drift_rate (optional)
                 |
   input     no purpose -> VOID (never defaulted). Every reference is RE-READ: file
             opened, record found, sha256 compared; one that does not check -> VOID.
   gate      EXPLORE only if needed_function_met = y AND energy available > reserve
             AND time available > reserve. Any n -> SOLVE. Anything VOID -> VOID,
             naming which. Asked again at every step.
   units     branch 1 is run on  cost = drift_rate x time  and  energy = cost  with the
             declared units; FAIL or VOID there -> the step is VOID
   options   tools whose needed features are in the environment, affordable, and not
             yet used on that instance; and inaction, always.
             cost(inaction) = sum over the references of rate_i x (now - at_i), DERIVED
               a reference with no rate and no default_drift_rate -> VOID, naming it
               the default's use is flagged on the step
               every age 0, rates > 0 -> cost 0: just read; waiting loses nothing yet
               a rate of 0 declared -> VOID ("static world claimed, unevidenced")
   SOLVE     each open option is a rival "this option moves toward the target";
             branch 5 gives each a posterior; ranked by NET SCORE in the cost unit:
               a tool     posterior x gain - cost
               inaction   - sum of rate_i x age_i
             gain: a case input, what moving toward the target is worth, in the cost
             unit (branch 1 checks gain = cost). No gain -> VOID ("gain undeclared").
             All rivals recorded.
   EXPLORE   the first tool, in table order, with a feature present and unpaired;
             none -> inaction.
   one step  the tool turns one feature instance into one candidate, written to
             proposals.json (status PROPOSED, tagged SOLVE or EXPLORE); the
             environment is read again; the next step starts from the new state.
   log       every step: gate, unit checks, options with why each is open or closed,
             rivals, choice, candidate, state before and after. Each SOLVE ranking's
             branch 5 input and log are saved under glyph_log/ and named in the step
             log with their sha256. replay(log) reproduces the final state and the
             candidates and runs branch 5 again from each saved file: a changed file,
             a changed step log or a different ranking -> replay FAILS.
```

```sh
python3 -m glyph step case.json [--steps N] [--json] [--dry-run]
python3 -m glyph ref 2b report.json 0 3      # an environment reference: sha256 + time
# exit 0 every step done | 3 a step is VOID | 2 usage
```

Tool table v0, every entry PROPOSED:

```text
tool                 needs (environment feature)                     candidate
dimensional_analogy  shared_dims: two branch-1 PASS records with     rhs of one = rhs of the
                     the same dimension                              other, as a question
boundary_probe       mixed_region: a branch-2b record that is MIXED  lhs - rhs = tolerance on the
                                                                     region between a holding
                                                                     and a failing piece
conjugate_map        conjugate_exponents: exponents p, q with        ( base ** p ) ** q = base
                     p * q = 1 in branch-1 / 2b formulas
slot_fill_audit      void_slots: a branch-4 record with a VOID slot  a question naming the slots
frame_edge           declared_scope: the case declares the scope     four questions about what
                     its environment was drawn in                    lies past that edge, each
                     {place, time, population}                       logged as a slot
```

frame_edge: where the edge of the environment was drawn

```text
case      scope       {place, time, population}, all three; half declared -> VOID
          frame_edge  {slot: {answer, source}}, optional: the case's answers
                      |
tool      questions only, wording fixed, cost 1 (the lowest in the table):
            UPSTREAM  what feeds this from outside the scope? (inflow, source,
                      underground, supply)
            LAG       what changed earlier that has not arrived yet?
            SHIFT     what could change suddenly? (wind, pressure, policy)
            WHOSE     whose environment filled the defaults: the case's, or the median's?
                      |
slots     answer + source -> FILLED      unanswered -> VOID, kept
          answer with no source -> VOID ("answered without a source"), kept as given
                      |
margin    any VOID slot -> margin_required: true, reason "unfilled frame-edge slots",
          on the question, the step and the report. All four FILLED -> false.
          Not asked yet, or no scope -> null (not false).
```

Source of the tool: two explain-then-do rounds on 2026-11-16 (base layers in a
cold cab; lake-ice safety), where the misses came from where the environment
edge was drawn, not from missing facts. The rounds are carried from the
repository owner and are not re-run here; the two cases are in the tests as
text. The owner's note on the ice case, "4 in rule -> 8 in practice", is
carried too: the tool raises the flag and computes no margin.

Limits of the v0

```text
frame_edge     states nothing about the world. An answer and its source are text from
               the case, kept and not read: "nothing" with a source counts as FILLED.
               It does not say how large a margin should be, and no other branch reads
               margin_required yet. Four questions are not a complete list of what can
               lie past an edge. The scope is the case's statement, not a record that is
               re-read. Whether the tool is useful is not established: PROPOSED.
ceiling        nothing the glyph writes is above PROPOSED. It runs no check itself;
               a candidate goes further only through 2b and then 2a.
candidates     are questions made by a fixed rule from one record or a pair. Many
               will be false or empty: m*c**2 = m*v**2/2 is what dimensional_analogy
               proposes from two energy formulas. That is the intended reading.
seam           a candidate with bounds such as 49/10 is VOID at the 2b -> 2a seam
               (algebra.mm has numerals 0 to 9 only); slot questions are kept in a
               separate "questions" list that the seam does not read
physics        the environment's "physics" is only the two budgets and the drift
               rate here; no physical constraint on a step is modelled
tool effects   a tool's cost and time are numbers in the table; nothing measures them
SOLVE          "moves toward the target" is what the case's evidence claims; the target
               text itself is recorded and not interpreted
drift          a rate per reference, in declared units that branch 1 checks; the rates
               themselves are inputs. Nothing measures how fast a record goes stale.
ranking        computed inline by branch 5 at each step, then saved and re-runnable;
               it is not read from an earlier branch 5 record
score rule     posterior x gain - cost against - drift. An earlier rule, posterior x
               1 / cost, let a free inaction (cost 0, just after an update) beat a tool
               with any evidence; it is kept only as a regression test.
gain           one number for the whole case, given by the case author. Nothing here
               measures what reaching the target is worth, and every tool is credited
               the same gain.
tools          four, chosen to touch branches 1, 2b and 4; branch 2a and branch 5
               records can be referenced but no v0 tool reads a feature from them
```

## Branch 4: word slots

A word claims nothing until its places are filled: "safe" is safe from what,
for whom. v2: the place table is realigned to the relayed Lojban reference.

```text
places.json   word -> ordered slots (name, role, required, status tag, source_predicate,
              optional bounds, optional senses), class (JUDGMENT / COMPARATIVE /
              EMOTIVE / FEAR, or null), shape, optional senses + sense_field
              word         slots (source_predicate)                          class
              warm         x1 what is warm (glare)                           EMOTIVE
                             PHYSICAL: x2 by standard (glare)
                             SOCIAL:   x3 to whom, x4 in what behaviour (xendo)
              safe         x1 what is safe (snura), x3 for whom (ckape)      FEAR
                             PROTECTED:    x2 from threat (snura)
                             NOT_PERILOUS: x4 under conditions (ckape)
              hostile      x1, x2 toward whom (le'onmo)                      EMOTIVE
              more         x1, x2 than what, x3 in what property,            COMPARATIVE
                           x4 by what amount, optional (zmadu)
              less         the same four places (mleca)                      COMPARATIVE
              efficient    x1, x2 useful output, x3 input supplied,          COMPARATIVE
                           x4 process, x5 baseline compared against
                           (physics_def); lojban: VOID
              better       x1, x2 than what, x3 for whom, x4 by what         JUDGMENT
                           standard, x5 by what amount, optional (xagmau)
              appropriate  x1, x2 to or with what, x3 in what aspect (mapti) JUDGMENT
              near         x1, x2 to what, x3 at distance, optional (jibni)  null
claims.json   fixed record with declared widths: word, slots, reading, sense, magnitude,
              evidential, speaker, oral_record, source_id, source_path, table
                      |
   unknown word / undeclared field or slot / bad tag     ---> VOID
   a value longer than its width, a number past S9(7)V9(4) ---> VOID ("would truncate")
                      |
   something required is missing (a slot, the reading of an EMOTIVE word, the sense
   of "safe", a magnitude, the source)
        ---> DEGRADED: what is filled is kept and usable; each missing item listed
             with name, reason, provenance. Not a PASS; pass_equivalent: false.
                      |
   a filled slot with numeric bounds and a value ---> branch 2b (units first)
                      |
   PASS  nothing missing, bounds hold     FAIL  a value outside its bounds (slot located)
   UNDECIDED  a value straddles its bounds
```

```sh
python3 -m wordslots check claims.json [--table places.json] [--json]
# exit 0 all PASS | 1 any FAIL | 3 DEGRADED, VOID or UNDECIDED, no FAIL | 2 usage
```

```text
evidential    how the claimant knows, mapped to the claim's own status and carried:
              observed -> OBSERVED   concluded -> DERIVED   hearsay, opinion -> PROPOSED
              defined -> OBSERVED (given input, like an axiom in branch 2a)
              ja'o -> DERIVED
              su'a -> PROPOSED (I generalize)      ba'a -> PROPOSED (I expect)
              ba'anai -> OBSERVED (I remember), with provenance {basis: memory}
              ba'acu'i -> OBSERVED (I experience), self-scoped exactly as se'o
              se'o -> OBSERVED, scope "speaker's own state only": x1 is filled with the
                      speaker and the other places are waived. se'o on anything
                      external -> DEGRADED.
              ka'u -> the oral-record discriminator row: four checks fixed by name,
                      shared, multi_gen, checkable, not_central, each y / n.
                      all y -> OBSERVED, with provenance {transmission: oral,
                      multi_generation: true, relay: holder}; any n -> PROPOSED;
                      a check not answered, or another name -> DEGRADED, naming it.
                      answered_by (who answered the four) is required: missing ->
                      DEGRADED. checkable_ref {file, record, sha256} is optional;
                      given, it is re-read (file opened, record found, sha256
                      compared) and a mismatch -> DEGRADED.
              none given -> null. A PASS never upgrades it.
source        one rule for every route: a claim names where it comes from.
                written (any evidential but se'o, ba'acu'i and ka'u, or none)   source_id
                oral (ka'u)                                oral_record.answered_by
                self-report (se'o, ba'acu'i)               the speaker, filled in
              the one that applies is required; missing -> DEGRADED, naming it, with
              the same record shape on either route (kind "source")
status        the verdict is DERIVED (VOID: none). claim_status is the claim's own.
              table_entry_status is the place-table entry's, PROPOSED until the
              holder of the word confirms it; the checker never changes a tag.
emotive       an EMOTIVE word needs its reading, PHYSICAL or SOCIAL; a PHYSICAL
              reading of "warm" needs a magnitude with its unit
sense         a word may declare senses, each with the predicate it comes from, and
              the claim field that picks one: "reading" for warm (the field it
              already had), "sense" for safe (PROTECTED / NOT_PERILOUS). A slot
              bound to senses is asked for only under one of them. safe with no
              sense -> DEGRADED, naming sense; a sense not declared -> VOID.
missing       every missing item carries sense: the sense a missing slot belongs to, or
              null for a slot all senses share. With no sense given the list is the
              sense field, then the shared items, then each sense's empty required
              slots grouped under its name (also in missing_by_sense). The glyph's
              slot_fill_audit lists its void slots the same way.
source_       every slot names the gismu or lujvo its place comes from, or
predicate     "physics_def". A slot without one voids the table.
widths        word X(20), slot text X(40), reading X(8), sense X(12), unit X(12), evidential X(10),
              speaker X(40), source_id X(40), source_path X(80); magnitude S9(7)V9(4).
              Nothing is ever cut to fit.
ranges        "bounds" {lo, hi, unit} on a slot, and named "ranges" (a name standing
              for a range of values, as a COBOL 88 level does); a filling's "is"
              names the range it claims. The value checked is the filling's, or the
              claim's magnitude. No numeric value given -> UNCHECKED.
void slots    kept on the record with slot_state VOID (or WAIVED under se'o), never dropped
order         when several apply: VOID, then FAIL, then DEGRADED, then UNDECIDED
```

Limits of branch 4

```text
PASS            the claim is well-formed: nothing required is missing and any
                checked bound holds. It does not say the claim is true.
table           the shipped places.json is an example written here, all PROPOSED,
                holder null; no holder has confirmed any entry
Lojban          a relayed reference, REFERENCES/lojban_place_structures.json (received
                2026-11-17), quotes 30 place structures from jbovlaste and 11 evidentials
                from the CLL, each with its URL. This build could not reach lojban.org
                and re-read none of it; the file was typed in from a paste and has not
                been byte-compared with the original (re_read_in_this_build: false).
table vs        the place table is realigned to the reference, and is still PROPOSED:
reference       a word's slots are the holder's to set. Union rule: a slot the table
                already had is kept when a predicate of the reference carries that
                place, and dropped when none does.
                  realigned    hostile -> le'onmo (2 places; "by what standard" dropped)
                               better -> xagmau (5 places); appropriate -> mapti
                               less -> mleca; warm SOCIAL -> xendo's places added
                  kept         safe "for whom": snura has two places; ckape carries it
                               efficient: no Lojban word in the reference; lojban VOID
                               stays in the entry, slots are physics_def
                               safe NOT_PERILOUS also takes ckape's "under conditions"
                tests/test_lojban_reference.py records both lists.
choices made    not given by the reference, made in this build and PROPOSED:
here            which predicate stands behind each sense of safe (PROTECTED = snura,
                NOT_PERILOUS = ckape); the status each new evidential maps to.
                efficient's five physics_def slots are the owner's, by order.
se'o            the CLL calls it knowledge by "internal experience not directly available
                to others, such as a dream, vision, or personal revelation". Using it for
                any report of one's own feeling ("I feel warm") is this repository's
                reading, wider than the examples the CLL gives.
oral record     the four checks are answered y / n by the person named in answered_by.
                Nothing here tests whether an account really is shared,
                multi-generational, checkable or not central; the row is taken as
                given. What each check means in full is the holder's, and is not
                written out in this repository. A checkable_ref is confirmed to
                exist and be unchanged; whether that record bears on the account is
                the claimant's statement.
source          the checker confirms that a source is NAMED. It does not look the source
                up, and it does not judge whether the source is a good one.
self-report     "the speaker" is matched by text: x1 empty, or "I" / "me" / "myself",
                or the speaker's name. Nothing checks that a se'o claim really is
                about an inner state.
fillings        text is not read: "x2: nothing" counts as filled
UNCHECKED       a bound with no numeric value is not checked and the claim can still
                PASS; the record says UNCHECKED
evidential      X(10), not the X(4) of a Lojban cmavo, because the English evidential
                words of v0 are kept
defined         its map to OBSERVED is a choice made here, not given in the order
not built       quantity kind (measured / capability / knowledge / intent), ancestry
                tags, claims with more than one word, nesting, negation
```

## Branch 5: inference ladder

Weighs rival hypotheses against each other and says which way the evidence is
moving. It feeds the direction ranking of branch 3; it decides nothing.

```text
case.json   hypotheses (>= 2 rivals; one alone -> VOID), each with prior + source
            a prior flagged normalization / superiority / convenience / unknown
              -> the whole set goes to a flat prior; the flag is logged
            evidence: type, likelihood ratio (Fraction), provenance, shared_ancestry
            tags, the evidence's own status tag
                 |
   direct        bears on one hypothesis; may carry a 2a / 2b check
   shadow        must list alternative casters; LR capped (3); updates the CLASS of
                 hypotheses it is consistent with, not one
   cross_domain  must declare its constraints, each matched or not; any unmatched
                 -> no update; LR capped (2)
   shared ancestry with earlier evidence on the same hypothesis -> only the strongest counts
                 |
   posterior per rival, exact (Fractions)       every step logged with its factor;
                 |                              a step can be reversed; replay(log)
                 v                              gives the same posteriors
   direction   RISING     raised by >= 2 evidence types with no shared ancestry
               FALLING    lowered by >= 2 evidence types with no shared ancestry
               STACKED    moved one way more than once by one type only: logged, no signal
               NO_SIGNAL  otherwise (also when both RISING and FALLING would apply)
   status      inference alone: at most PROPOSED. DERIVED only with direct evidence
               that raises the rival, is itself OBSERVED or DERIVED, and carries a
               check_ref {branch, file, record, sha256} that infer RE-READS: the
               record is found, its sha256 is equal, and its verdict is PASS (2a) or
               HOLDS / BOTH_HOLD with rigorous true (2b). Anything else, a merely
               declared check included: PROPOSED, reason CHECK_UNVERIFIED.
```

```sh
python3 -m infer rank case_snow.json [--json] [--log FILE]
# exit 0 ranked, every evidence record usable | 3 case VOID or an evidence record VOID | 2 usage
python3 -m infer ref 2b report.json 0        # the check_ref of one record, with its sha256
```

Worked case, `case_snow.json` (Broad Street, 1854; miasma against water):

```text
FLAT_PRIOR  miasma's 9/10 is flagged normalization -> 1/2 each
APPLY       pump_cluster    shadow        lr 8 -> 3 (capped) on water
APPLY       spared_groups   direct        lr 5 on water
NO_UPDATE   handle_removed  direct        same inquiry as spared_groups, not stronger
NO_UPDATE   poison_analogy  cross_domain  a declared constraint is not matched
water   15/16   RISING (direct + shadow)   status PROPOSED
miasma   1/16   NO_SIGNAL                  status PROPOSED
```

Limits of branch 5

```text
numbers       the worked case's priors and likelihood ratios are CONSTRUCTED for the
              example. They are not estimates from the historical record and nothing
              here is a finding about cholera.
caps          3 for shadow and 2 for cross_domain are PROPOSED defaults, not derived
              from anything; each run logs the caps it used and where they came from
inputs        a likelihood ratio, a constraint marked matched and a shared_ancestry
              tag are taken as given. Nothing here verifies them: an untagged common
              source is counted twice.
check_ref     infer confirms that the named record exists, is unchanged (sha256) and
              has a passing verdict. It does not re-run the check, and it does not
              judge whether that check has anything to do with the hypothesis: that
              link is the evidence author's claim.
flat prior    one flagged prior flattens the whole set (a prior is a statement about
              the rivals together); that reading is a choice made here
RISING        means two independent kinds of evidence point the same way. It is not
              a verdict on the hypothesis.
exit code 1   not used: nothing in this branch FAILS
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
today                 km, eV and degC are not in the unit table, so a check using
                      them comes back VOID (unknown unit), not PASS. The lines above
                      say what a table without scale factors or offsets cannot see
                      if such units are added; rad, torque and energy already read
                      alike today.
```
