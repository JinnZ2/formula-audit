# Reading notes: common misreads

Status: a list of misreads of this repository, recorded so that the next reader
can avoid them. Each entry says what the repository does and where to check it.
First entries come from one AI deep-research audit of this repository and
study-aperture, dated 2026-11-17, which the owner pasted into a session on
2026-11-16; the audit text itself is not in this repository. Not established:
that this list is complete, or that every reader makes these misreads.

Prose drift is now checked: `tests/test_readme_claims.py` binds concrete README
examples to the behaviour they describe, and fails if either side changes.
`python3 tests/test_readme_claims.py --hunt` lists README lines that look like
examples and are not yet registered (UNCHECKED, not wrong; the selection rule
is a heuristic). First run, 2026-11-16 on `main` at `6ce55ec`: 13 registered,
all matching; 6 UNCHECKED, in branches 3, 4, 5 and the seam.
Second run, 2026-11-19 on `main` at `a216f74`: 7 UNCHECKED (the glyph
"gain undeclared" line was new). 10 claims added: 23 registered, all matching;
0 UNCHECKED. One of the 10 binds "pieces that HOLD and pieces that FAIL -> MIXED"
and fails if `holds_elsewhere` comes back: the drift this file itself carried
(see the 2026-11-19 correction) was not in the register then. 0 UNCHECKED means
the heuristic finds nothing more, not that every example is bound.

| Misread | What the repository does | Check |
|---|---|---|
| "The float tier mispredicts `(1e16 + 1) - 1e16 = 1`" | Number-only expressions are folded to exact Fractions before any tier runs, so that check is exact at every tier. The misprediction needs symbols and a scale factor. The README carried the stale example until 2026-11-16; the audit caught it. | README "Limits of branch 2b"; `tests/test_numcheck.py` `test_a_wrong_triage_prediction_is_logged_not_used`, `test_number_only_expression_is_exact_at_every_tier` |
| A triage prediction is a verdict | Float and Decimal only predict or abstain. The interval tier decides. A prediction stands only with `--fast`, and the record then says `rigorous: false`. | README "Branch 2b" |
| UNDECIDED means FAILS | UNDECIDED means the enclosures could not decide within the depth limit. `x*x = x**2` on `[0, 1]` at tolerance 0 is UNDECIDED (the dependency problem), not false. | README "Limits of branch 2b" |
| An interval FAILS means it fails everywhere | FAILS on interval inputs names the piece where it fails at every point; it may hold on other pieces (`bisection.holds_elsewhere`). | README "Limits of branch 2b" |
| Correction 2026-11-19 to the row above (the row is kept as written) | `bisection.holds_elsewhere` was removed after `19ff7df`; it is in no file on `main`. On `main` a run with pieces that hold and pieces that fail reads MIXED, and FAILS means located failing pieces with none holding. README: "pieces that HOLD and pieces that FAIL  -> MIXED (both kinds listed)"; "pieces that FAIL, none that hold       -> FAILS, located"; "FAILS         on interval inputs FAILS can mean \"fails on located pieces of the given ranges, and no piece holds\" (other pieces may still straddle)". Observed: the Kimi CF02 numcheck audit, run 2026-11-19 on a checkout at `4345de6`, reports MIXED point records (its report is not in this repository); a local run on `c1acb59` of `y = 2*x`, `x` in `[0, 4]`, `y = 4`, tolerance 1 read MIXED (hold 2, fail 12, straddle 2; exit 3). | README "Branch 2b", "Limits of branch 2b"; `tests/test_numcheck.py` (asserts `MIXED`) |
| `unitaudit` converts units, or reads km and m as the same today | It answers "which dimension", never "how many". km, eV and degC are not in the unit table, so today they come back VOID (unknown unit), not converted and not PASS. The README blind-spot list describes what a table without scale factors would miss if such units were added. | `unitaudit/dims.py` header; README "Known blind spots of branch 1" |
| A units PASS means physically the same quantity | Angle is dimensionless, so torque checks the same as energy, and `sin(f*t)` passes with f in Hz. | README "Known blind spots of branch 1" |
| `kernel` is a production Metamath verifier | It checks hand-written test databases in CI; `set.mm` is not in the repository and is run by hand only. | README "Branch 2a" |
| The default branch shows the current repository | Until 2026-11-19, GitHub's default branch here was `claude/quasicrystal-projection-properties-448bx7`, which stopped at branches 1, 2a and 2b with branch 3 VOID. Current work is on `main` (branches 3, 4 and 5 built), which is now the default. The 2026-11-17 audit read the old default branch; so did the first version of this file. | `git branch -r`; repository settings |
| A pure-number check that passes was checked against floating-point error | It was not exercised there at all; it was exact by construction. | this file, first row |

## Note 2026-11-19: the default branch is stale

Measurand: "default behind the integration branch". This repository's GitHub default,
`claude/quasicrystal-projection-properties-448bx7` at `7df0d81`, is STALE: 45 commits behind
`main` (at `c1acb59`), with 3 commits `main` does not have (their content is on `main` as
`5fcc404` and `7574be0`). Until the setting changed, a clone without `-b main` read the stale tree.

Resolved 2026-11-19: Perplexity Computer changed the default branch to `main`
(`gh repo edit --default-branch main`), with the owner's authorization. The old branch is kept,
not deleted.

## Note 2026-11-19: the outside audit's author

The 2026-11-17 outside audit named at the top of this file: author recorded as Kimi-or-GPT,
UNRESOLVED (owner-stated 2026-11-19; neither is confirmed). Its text is not filed in this
repository or in study-aperture. The rows above are the record of it; the audit itself cannot be
re-read from here.
