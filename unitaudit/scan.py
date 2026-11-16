"""scan -- PLACEHOLDER. Find formula-shaped lines in files -> a formulas.json draft.

Co-authored. Every entry is PROPOSED and every unit is null, so the checker
returns VOID for all of them until a person confirms the symbols and units.
What counts as formula-shaped here: a line (or a `backtick` span in it) with
one '=' whose two sides parse as expressions, with at least one operator or
call and at least two names in all. This misses most formulas written as
prose or LaTeX and picks up ordinary assignments; it is a draft maker only.
"""
import ast
from pathlib import Path

from .check import Void, split_sides

SUFFIXES = (".py", ".md", ".txt", ".rst")


def _candidates(line):
    if "`" in line:
        parts = line.split("`")
        return [parts[i] for i in range(1, len(parts), 2)]
    s = line.strip().lstrip("#").strip()
    return [s] if s else []


def _formula_shaped(text):
    try:
        lhs, rhs = split_sides(text)
        trees = [ast.parse(x.strip(), mode="eval").body for x in (lhs, rhs)]
    except (Void, SyntaxError, ValueError):
        return None
    names, ops = set(), 0
    for t in trees:
        for n in ast.walk(t):
            if isinstance(n, ast.Name):
                names.add(n.id)
            elif isinstance(n, (ast.BinOp, ast.Call)):
                ops += 1
            elif not isinstance(n, (ast.Constant, ast.UnaryOp, ast.operator, ast.unaryop,
                                    ast.expr_context)):
                return None
    funcs = {n.func.id for t in trees for n in ast.walk(t)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    names -= funcs
    return sorted(names) if ops and len(names) >= 2 else None


def scan(root):
    root = Path(root)
    files = [root] if root.is_file() else sorted(
        p for p in root.rglob("*") if p.is_file() and p.suffix in SUFFIXES
        and ".git" not in p.parts)
    out, unread = [], []
    for f in files:
        try:
            lines = f.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError) as e:
            unread.append({"path": str(f), "reason": type(e).__name__})
            continue
        for i, line in enumerate(lines, 1):
            for text in _candidates(line):
                names = _formula_shaped(text)
                if names:
                    out.append({"formula": text.strip(), "symbols": {n: None for n in names},
                                "source_path": f"{f}:{i}", "slots": {},
                                "status": "PROPOSED"})
    return {"draft": True, "status": "PROPOSED",
            "note": "placeholder scanner; units are null until confirmed, so every entry "
                    "checks as VOID",
            "files_read": len(files) - len(unread), "files_not_read": unread, "formulas": out}
