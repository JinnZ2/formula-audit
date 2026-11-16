"""tools -- tool table v0 (five entries). Every entry is PROPOSED. Co-authored.

A tool needs environment features, has a cost (energy) and a time, and turns
one feature instance into one candidate. A candidate is a question for the
other branches, never a result: status PROPOSED, checked by 2b, proved by 2a.
"""
from fractions import Fraction

from unitaudit.check import split_sides

TABLE_V0 = [
    {"name": "dimensional_analogy", "needs": ["shared_dims"], "cost": "2", "time": "1",
     "status": "PROPOSED",
     "does": "two formulas whose sides have the same dimension: propose that their right "
             "sides are equal, as a question"},
    {"name": "boundary_probe", "needs": ["mixed_region"], "cost": "3", "time": "1",
     "status": "PROPOSED",
     "does": "a check that holds on part of its inputs and fails on part: propose the "
             "boundary lhs - rhs = tolerance on the region between a holding and a failing piece"},
    {"name": "conjugate_map", "needs": ["conjugate_exponents"], "cost": "2", "time": "1",
     "status": "PROPOSED",
     "does": "exponents p and q with p * q = 1: propose ( base ** p ) ** q = base"},
    {"name": "slot_fill_audit", "needs": ["void_slots"], "cost": "1", "time": "1",
     "status": "PROPOSED",
     "does": "a claim with a slot left VOID: ask for the slot, as a question"},
    {"name": "frame_edge", "needs": ["declared_scope"], "cost": "1", "time": "1",
     "status": "PROPOSED",
     "does": "an environment with a declared scope (place, time, population): ask what "
             "lies past its edge, as four questions. Questions only, never answers."},
]

# frame_edge: the four questions. The wording is fixed here; the tool fills in
# nothing but the declared scope. It states nothing about the world.
FRAME_QUESTIONS = (
    ("UPSTREAM", "what feeds this from outside the scope? (inflow, source, underground, "
                 "supply)"),
    ("LAG", "what changed earlier that has not arrived yet?"),
    ("SHIFT", "what could change suddenly? (wind, pressure, policy)"),
    ("WHOSE", "whose environment filled the defaults: the case's, or the median's?"),
)
MARGIN_REASON = "unfilled frame-edge slots"


def _blank(x):
    return x is None or not x.strip()


def frame_slots(answers):
    """The four frame-edge slots, each FILLED (answer and source) or VOID.
    A VOID slot is kept; an answer with no source is VOID, and kept as given."""
    rows = []
    for name, question in FRAME_QUESTIONS:
        a = answers.get(name) or {}
        answer, source = a.get("answer"), a.get("source")
        if _blank(answer):
            state, why = "VOID", "unanswered"
        elif _blank(source):
            state, why = "VOID", "answered without a source"
        else:
            state, why = "FILLED", None
        rows.append({"name": name, "question": question, "slot_state": state,
                     "void_reason": why, "answer": answer, "source": source,
                     "status": "PROPOSED"})
    return rows


def margin(slots):
    """The margin flag a set of frame-edge slots raises."""
    void = [s["name"] for s in slots if s["slot_state"] == "VOID"]
    return {"margin_required": bool(void), "reason": MARGIN_REASON if void else None,
            "void_slots": void}


def _ref(r):
    return {k: (str(r[k]) if k == "at" else r[k])
            for k in ("branch", "file", "record", "sha256", "at")}


def _sides(formula):
    lhs, rhs = split_sides(formula)
    return lhs.strip(), rhs.strip()


def _hull(a, b):
    out = {}
    for name in sorted(set(a) & set(b)):
        lo = min(Fraction(a[name]["lo"]), Fraction(b[name]["lo"]))
        hi = max(Fraction(a[name]["hi"]), Fraction(b[name]["hi"]))
        out[name] = {"lo": str(lo), "hi": str(hi)}
    return out


def apply_tool(name, inst):
    """One feature instance -> one candidate: ("proposal" | "question", body)."""
    src = inst["sources"]
    if name == "dimensional_analogy":
        (_, r1), (_, r2) = _sides(src[0]["data"]["formula"]), _sides(src[1]["data"]["formula"])
        return "proposal", {"lhs": r1, "rhs": r2, "domain": {},
                            "note": f"both sides have dimension {inst['dimension']}. The same "
                                    "letter in the two source formulas may not mean the same "
                                    "thing. No values are given: nothing can be checked yet."}
    if name == "boundary_probe":
        d = src[0]["data"]
        lhs, rhs = _sides(d["formula"])
        b = d["bisection"]
        hold, fail = b["pieces_that_hold"][0]["subbox"], b["pieces_that_fail"][0]["subbox"]
        fixed = {n: v["value"]["lo"] for n, v in (d.get("inputs") or {}).items()
                 if v["value"]["is_point"]}
        return "proposal", {"lhs": f"({lhs}) - ({rhs})", "rhs": b["tolerance"],
                            "domain": _hull(hold, fail), "fixed": fixed,
                            "note": "the edge between a piece that holds and a piece that "
                                    "fails; lhs - rhs = -tolerance is the other edge"}
    if name == "conjugate_map":
        p, q, base = inst["p"], inst["q"], inst["base"]
        dom = {}
        for r in src:
            for n, v in (r["data"].get("inputs") or {}).items():
                if not v["value"]["is_point"]:
                    dom[n] = {"lo": v["value"]["lo"], "hi": v["value"]["hi"]}
        return "proposal", {"lhs": f"(({base})**({p}))**({q})", "rhs": f"{base}", "domain": dom,
                            "note": "true where the base is not negative; where it can be "
                                    "negative this is a question, not an identity"}
    if name == "slot_fill_audit":
        d = src[0]["data"]
        return "question", {"word": d.get("word"),
                            "void_slots": [{"name": s["name"], "role": s.get("role"),
                                            "required": s.get("required")}
                                           for s in d["slots"] if s.get("slot_state") == "VOID"],
                            "note": "the claim says nothing until these are filled"}
    if name == "frame_edge":
        slots = frame_slots(inst["answers"])
        return "question", {"scope": inst["scope"], "frame_slots": slots, **margin(slots),
                            "note": "questions about what lies past the edge of the declared "
                                    "scope. The tool states nothing about the world: an "
                                    "answer and its source are the case's, kept as given "
                                    "and not read."}
    raise ValueError(f"no such tool: {name}")
