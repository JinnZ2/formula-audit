"""dims -- a dimension is 7 Fractions over L M T I Theta N J. Co-authored.

No scale factors: this table answers "which dimension", never "how many".
An unknown unit raises UnknownUnit; nothing is guessed.
"""
import ast
from fractions import Fraction

BASE = ("L", "M", "T", "I", "Theta", "N", "J")


class UnknownUnit(Exception):
    pass


class Dim:
    __slots__ = ("e",)

    def __init__(self, *e):
        if len(e) != 7:
            raise ValueError("a dimension has 7 exponents: " + " ".join(BASE))
        self.e = tuple(Fraction(x) for x in e)

    def __mul__(self, o):
        return Dim(*[a + b for a, b in zip(self.e, o.e)])

    def __truediv__(self, o):
        return Dim(*[a - b for a, b in zip(self.e, o.e)])

    def __pow__(self, k):
        k = Fraction(k)
        return Dim(*[a * k for a in self.e])

    def __eq__(self, o):
        return isinstance(o, Dim) and self.e == o.e

    def __hash__(self):
        return hash(self.e)

    @property
    def dimensionless(self):
        return not any(self.e)

    def __str__(self):
        parts = [b if x == 1 else f"{b}^{x}" for b, x in zip(BASE, self.e) if x]
        return " ".join(parts) if parts else "1"

    __repr__ = __str__

    def as_record(self):
        return {"text": str(self), "exponents": {b: str(x) for b, x in zip(BASE, self.e)}}


def _base(i):
    return Dim(*[1 if j == i else 0 for j in range(7)])


ONE = Dim(0, 0, 0, 0, 0, 0, 0)
L, M, T, I, THETA, N, J = (_base(i) for i in range(7))

_FORCE = M * L / T ** 2
_ENERGY = _FORCE * L
_CHARGE = I * T
_VOLT = _ENERGY / _CHARGE

UNITS = {
    # SI base
    "m": L, "kg": M, "s": T, "A": I, "K": THETA, "mol": N, "cd": J,
    # derived
    "N": _FORCE, "J": _ENERGY, "W": _ENERGY / T, "Pa": _FORCE / L ** 2, "Hz": ONE / T,
    "V": _VOLT, "C": _CHARGE, "ohm": _VOLT / I, "Ω": _VOLT / I,
    "T": _VOLT * T / L ** 2, "Wb": _VOLT * T,
    # dimensionless
    "1": ONE, "": ONE, "dimensionless": ONE, "rad": ONE,
}


def _number(node):
    """Fraction value of a constant-only expression, or None."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
            and not isinstance(node.value, bool):
        return Fraction(repr(node.value)) if isinstance(node.value, float) else Fraction(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        v = _number(node.operand)
        return None if v is None else (-v if isinstance(node.op, ast.USub) else v)
    if isinstance(node, ast.BinOp):
        a, b = _number(node.left), _number(node.right)
        if a is None or b is None:
            return None
        if isinstance(node.op, ast.Add):
            return a + b
        if isinstance(node.op, ast.Sub):
            return a - b
        if isinstance(node.op, ast.Mult):
            return a * b
        if isinstance(node.op, ast.Div):
            return a / b if b else None
        if isinstance(node.op, ast.Pow) and b.denominator == 1 and (a or b >= 0):
            return a ** int(b)
    return None


def unit_dim(text):
    """Dimension of a unit string: a table entry, or table entries joined by
    * / ** ( ) with number exponents, e.g. 'J/(mol*K)', 'kg*m**2/s**2', 'm/s^2'."""
    if not isinstance(text, str):
        raise UnknownUnit(f"unit is not a string: {text!r}")
    key = text.strip()
    if key in UNITS:
        return UNITS[key]
    src = key.replace("^", "**").replace("Ω", "ohm").replace("·", "*")
    try:
        tree = ast.parse(src, mode="eval").body
    except SyntaxError:
        raise UnknownUnit(f"unit string does not parse: {text!r}")

    def walk(n):
        if isinstance(n, ast.Name):
            if n.id not in UNITS:
                raise UnknownUnit(f"unknown unit {n.id!r} in {text!r}")
            return UNITS[n.id]
        if isinstance(n, ast.Constant) and n.value == 1 and not isinstance(n.value, bool):
            return ONE
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Mult):
            return walk(n.left) * walk(n.right)
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div):
            return walk(n.left) / walk(n.right)
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Pow):
            k = _number(n.right)
            if k is None:
                raise UnknownUnit(f"unit exponent is not a number in {text!r}")
            return walk(n.left) ** k
        raise UnknownUnit(f"unsupported unit expression in {text!r}")
    return walk(tree)
