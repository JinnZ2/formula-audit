# formula-audit
Stdlib-only Python checker for mathematical formulas. Runs on a phone.
Branch 1: unit / dimension audit (fail-closed: unknown → VOID, never PASS)
Branch 2: proof kernel (Metamath-style substitution), data-point and intersection checks
Branch 3: proposes intersections between results; output PROPOSED, checked by branch 2
Status tags: OBSERVED / DERIVED / PROPOSED. Unfilled slots stay VOID.
License: CC0 1.0. Co-authored (human + AI).
