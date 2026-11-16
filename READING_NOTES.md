# Reading notes: common misreads

Status: a list of misreads of this repository, recorded so that the next reader
can avoid them. Each entry says what the repository does and where to check it.
First entries come from one AI deep-research audit of this repository and
study-aperture, dated 2026-11-17, which the owner pasted into a session on
2026-11-16; the audit text itself is not in this repository. Not established:
that this list is complete, or that every reader makes these misreads.

| Misread | What the repository does | Check |
|---|---|---|
| "The float tier mispredicts `(1e16 + 1) - 1e16 = 1`" | Number-only expressions are folded to exact Fractions before any tier runs, so that check is exact at every tier. The misprediction needs symbols and a scale factor. The README carried the stale example until 2026-11-16; the audit caught it. | README "Limits of branch 2b"; `tests/test_numcheck.py` `test_a_wrong_triage_prediction_is_logged_not_used`, `test_number_only_expression_is_exact_at_every_tier` |
| A triage prediction is a verdict | Float and Decimal only predict or abstain. The interval tier decides. A prediction stands only with `--fast`, and the record then says `rigorous: false`. | README "Branch 2b" |
| UNDECIDED means FAILS | UNDECIDED means the enclosures could not decide within the depth limit. `x*x = x**2` on `[0, 1]` at tolerance 0 is UNDECIDED (the dependency problem), not false. | README "Limits of branch 2b" |
| An interval FAILS means it fails everywhere | FAILS on interval inputs names the piece where it fails at every point; it may hold on other pieces (`bisection.holds_elsewhere`). | README "Limits of branch 2b" |
| `unitaudit` converts units, or reads km and m as the same today | It answers "which dimension", never "how many". km, eV and degC are not in the unit table, so today they come back VOID (unknown unit), not converted and not PASS. The README blind-spot list describes what a table without scale factors would miss if such units were added. | `unitaudit/dims.py` header; README "Known blind spots of branch 1" |
| A units PASS means physically the same quantity | Angle is dimensionless, so torque checks the same as energy, and `sin(f*t)` passes with f in Hz. | README "Three known blind spots" |
| `kernel` is a production Metamath verifier | It checks hand-written test databases in CI; `set.mm` is not in the repository and is run by hand only. | README "Branch 2a" |
| Branch 3 is missing by oversight | It is VOID on purpose: not named or specified here. | README "Three branches" |
| A pure-number check that passes was checked against floating-point error | It was not exercised there at all; it was exact by construction. | this file, first row |
