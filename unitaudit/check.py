"""check -- formula string -> ast -> a dimension per node -> PASS / FAIL / VOID.

Co-authored. Fail-closed: an unknown symbol, unit, function or syntax form is
VOID with a reason. VOID is never PASS and never FAIL.

Rules
  a + b, a - b, lhs = rhs    equal dimensions
  a * b, a / b               dimensions multiply / divide
  a ** k                     k dimensionless; if a has a dimension, k must
                             also be a literal number (else VOID: the result
                             dimension cannot be computed)
  exp log sin cos tan (x)    x dimensionless; result dimensionless
  sqrt(x)                    x ** (1/2)
  abs(x), +x, -x             dimension of x
  number                     dimensionless
"""
import ast

from .dims import Dim, ONE, UnknownUnit, _number, unit_dim

DIMENSIONLESS_ARG = ("exp", "log", "sin", "cos", "tan")
SLOTS = ("limit", "sign", "magnitude_range")
STATUS = ("OBSERVED", "DERIVED", "PROPOSED")
VERSION = "branch1-1"


class Void(Exception):
    def __init__(self, reason, node=None, side=None):
        super().__init__(reason)
        self.reason, self.node, self.side = reason, node, side


class Fail(Exception):
    def __init__(self, rule, node, dims, side=None):
        super().__init__(rule)
        self.rule, self.node, self.dims, self.side = rule, node, dims, side


def _where(node, src, side):
    if node is None:
        return {"side": side, "col": None, "end_col": None, "text": None}
    return {"side": side, "col": node.col_offset, "end_col": node.end_col_offset,
            "text": ast.get_source_segment(src, node)}


def dim_of(node, table):
    """Dimension of an ast node. Raises Fail or Void."""
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return ONE
        raise Void(f"constant {node.value!r} is not a number", node)
    if isinstance(node, ast.Name):
        if node.id not in table:
            raise Void(f"unknown symbol {node.id!r}", node)
        return table[node.id]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        return dim_of(node.operand, table)
    if isinstance(node, ast.BinOp):
        a = dim_of(node.left, table)
        if isinstance(node.op, ast.Pow):
            k_dim = dim_of(node.right, table)
            if not k_dim.dimensionless:
                raise Fail("exponent must be dimensionless", node.right, [k_dim])
            if a.dimensionless:
                return ONE
            k = _number(node.right)
            if k is None:
                raise Void("exponent on a dimensional base is not a literal number", node.right)
            return a ** k
        b = dim_of(node.right, table)
        if isinstance(node.op, (ast.Add, ast.Sub)):
            if a != b:
                raise Fail("+ and - need equal dimensions", node, [a, b])
            return a
        if isinstance(node.op, ast.Mult):
            return a * b
        if isinstance(node.op, ast.Div):
            return a / b
        raise Void(f"unsupported operator {type(node.op).__name__}", node)
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.keywords:
            raise Void("unsupported call form", node)
        name = node.func.id
        if name in DIMENSIONLESS_ARG:
            if len(node.args) != 1:
                raise Void(f"{name} takes one argument here", node)
            d = dim_of(node.args[0], table)
            if not d.dimensionless:
                raise Fail(f"argument of {name} must be dimensionless", node.args[0], [d])
            return ONE
        if name == "sqrt" and len(node.args) == 1:
            return dim_of(node.args[0], table) ** "1/2"
        if name == "abs" and len(node.args) == 1:
            return dim_of(node.args[0], table)
        raise Void(f"unknown function {name!r}", node)
    raise Void(f"unsupported syntax {type(node).__name__}", node)


def split_sides(formula):
    """'lhs = rhs' or 'lhs == rhs' -> (lhs, rhs, column where rhs starts)."""
    depth, hits = 0, []
    i = 0
    while i < len(formula):
        ch = formula[i]
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        elif ch == "=" and depth == 0:
            if formula[i:i + 2] == "==":
                hits.append((i, 2))
                i += 1
            elif i and formula[i - 1] in "<>!":
                raise Void("only = or == between the two sides")
            else:
                hits.append((i, 1))
        i += 1
    if len(hits) != 1:
        raise Void(f"need exactly one = between two sides, found {len(hits)}")
    at, width = hits[0]
    return formula[:at], formula[at + width:]


def symbol_table(symbols, default_status=None):
    """{name: unit} or {name: {"unit": unit, "status": tag}} -> (dims, records).
    Each symbol's unit carries its own tag: OBSERVED (read from a source),
    PROPOSED (scanner / guess), DERIVED; not given = null, never filled in.
    default_status is the entry-level tag, used for symbols with none."""
    if not isinstance(symbols, dict):
        raise Void("symbols is not a {name: unit} table")
    table, records, first = {}, {}, None
    for name, spec in symbols.items():
        unit, status = (spec.get("unit"), spec.get("status", default_status)) \
            if isinstance(spec, dict) else (spec, default_status)
        rec = {"unit": unit, "dim": None, "status": status, "void_reason": None}
        records[name] = rec
        if status is not None and status not in STATUS:
            rec["void_reason"] = f"status {status!r} is not one of {', '.join(STATUS)}"
        elif unit is None:
            rec["void_reason"] = "no unit given"
        else:
            try:
                table[name] = unit_dim(unit)
                rec["dim"] = str(table[name])
            except UnknownUnit as e:
                rec["void_reason"] = str(e)
        if rec["void_reason"] and first is None:
            first = f"symbol {name!r}: {rec['void_reason']}"
    return table, records, first


def slot_record(slots):
    """slot_state per slot: VOID = not given. UNCHECKED = given, and not
    checked: this branch has no numeric values to evaluate a limit, a sign
    or a magnitude with. UNCHECKED is not a pass."""
    slots = slots if isinstance(slots, dict) else {}
    out = {}
    for s in SLOTS:
        given = slots.get(s)
        out[s] = ({"slot_state": "VOID", "given": None} if given is None else
                  {"slot_state": "UNCHECKED", "given": given,
                   "reason": "no values given to evaluate it with; nothing was checked"})
    return out


def check_formula(entry, index=None, input_path=None):
    formula = entry.get("formula") if isinstance(entry, dict) else None
    rec = {"formula": formula, "verdict": "VOID", "void_reason": None, "located_error": None,
           "dims": {"lhs": None, "rhs": None}, "status": None, "symbols": None,
           "provenance": {"source_path": entry.get("source_path") if isinstance(entry, dict)
                          else None, "input": input_path, "index": index,
                          "tool": "unitaudit " + VERSION,
                          "entry_status_given": entry.get("status")
                          if isinstance(entry, dict) else None},
           "slots": slot_record(entry.get("slots") if isinstance(entry, dict) else None),
           "human_interest": None, "ai_interest": None}
    side, src = None, None
    try:
        if not isinstance(formula, str):
            raise Void("no formula string")
        given = entry.get("status")
        if given is not None and given not in STATUS:
            raise Void(f"status {given!r} is not one of {', '.join(STATUS)}")
        table, rec["symbols"], bad = symbol_table(entry.get("symbols"), given)
        if bad:
            raise Void(bad)
        sides = dict(zip(("lhs", "rhs"), split_sides(formula)))
        got = {}
        for side in ("lhs", "rhs"):
            src = sides[side].strip()
            try:
                tree = ast.parse(src, mode="eval").body
            except SyntaxError as e:
                raise Void(f"{side} does not parse: {e.msg}")
            got[side] = dim_of(tree, table)
            rec["dims"][side] = got[side].as_record()
        side = None
        if got["lhs"] != got["rhs"]:
            rec["verdict"] = "FAIL"
            rec["located_error"] = {"side": "both", "col": None, "end_col": None,
                                    "text": formula, "rule": "lhs and rhs need equal dimensions",
                                    "dims": [str(got["lhs"]), str(got["rhs"])]}
        else:
            rec["verdict"] = "PASS"
        # a verdict follows from the supplied unit table: DERIVED. What was
        # observed, if anything, is each symbol's unit; those carry their own tags.
        rec["status"] = "DERIVED"
    except Fail as f:
        rec["verdict"] = "FAIL"
        rec["located_error"] = {**_where(f.node, src, side), "rule": f.rule,
                                "dims": [str(d) for d in f.dims]}
        rec["status"] = "DERIVED"
    except Void as v:
        rec["verdict"] = "VOID"
        rec["void_reason"] = v.reason
        rec["located_error"] = _where(v.node, src, side) if v.node is not None else None
    except Exception as e:                 # fail closed: anything unforeseen is VOID
        rec["verdict"] = "VOID"
        rec["void_reason"] = f"internal: {type(e).__name__}: {e}"
    return rec


def check_all(entries, input_path=None):
    if isinstance(entries, dict) and "formulas" in entries:
        entries = entries["formulas"]
    if not isinstance(entries, list):
        entries = [entries]
    records = [check_formula(e, i, input_path) for i, e in enumerate(entries)]
    counts = {v: sum(1 for r in records if r["verdict"] == v) for v in ("PASS", "FAIL", "VOID")}
    return {"tool": "unitaudit " + VERSION, "input": input_path, "counts": counts,
            "records": records}
