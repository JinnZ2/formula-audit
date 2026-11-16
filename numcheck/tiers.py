"""tiers -- one formula walk, three number systems. Co-authored.

  float     binary64. Fast, NOT an enclosure. It decides only when the result
            is far from the tolerance edge (margin > 1e-9 x the largest
            magnitude met); otherwise it says "too close to call".
  decimal   Decimal at a set precision. Still not an enclosure. Decides when
            the margin > 10^-(prec/2) x the largest magnitude met. No sin /
            cos here: a formula using them climbs past this tier.
  interval  Fraction intervals; sqrt exp ln sin cos as outward enclosures at
            a set precision. This tier is the rigorous one: HOLDS and FAILS
            from it are statements about every value inside the inputs.

A tier that cannot run (overflow, domain, no such function) climbs; only the
interval tier can say VOID.
"""
import ast
import decimal
import math
from decimal import Decimal
from fractions import Fraction

from . import interval as I

FLOAT_GUARD = 1e-9
FUNCTIONS = ("sqrt", "exp", "log", "sin", "cos", "tan", "abs")


class NumVoid(Exception):
    """Rigorous: the formula has no value on these inputs, or is not supported."""


class TierCannot(Exception):
    """This tier cannot evaluate; climb."""


def exact_number(node, src):
    """Fraction value of a number-only expression, read from the source text
    (so 0.1 is one tenth, not the nearest binary float), or None."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
            and not isinstance(node.value, bool):
        if isinstance(node.value, int):
            return Fraction(node.value)
        text = ast.get_source_segment(src, node)
        try:
            return Fraction(text.replace("_", ""))
        except (ValueError, AttributeError):
            return None
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        v = exact_number(node.operand, src)
        return None if v is None else (-v if isinstance(node.op, ast.USub) else v)
    if isinstance(node, ast.BinOp):
        a, b = exact_number(node.left, src), exact_number(node.right, src)
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
    return None


class FloatSys:
    name, rigorous = "float", False

    def __init__(self):
        self.scale = 0.0
        self.precision = "binary64"

    def _seen(self, v):
        if v != v or v in (math.inf, -math.inf):
            raise TierCannot("float result is not finite")
        self.scale = max(self.scale, abs(v))
        return v

    def const(self, fr):
        try:
            return self._seen(float(fr))
        except OverflowError:
            raise TierCannot("value too large for a float")

    def _do(self, f, *a):
        try:
            return self._seen(f(*a))
        except (OverflowError, ValueError, ZeroDivisionError) as e:
            raise TierCannot(f"float: {type(e).__name__}")

    def neg(self, a): return -a
    def add(self, a, b): return self._do(lambda: a + b)
    def sub(self, a, b): return self._do(lambda: a - b)
    def mul(self, a, b): return self._do(lambda: a * b)
    def div(self, a, b): return self._do(lambda: a / b)
    def powi(self, a, n): return self._do(lambda: a ** n)
    def sqrt(self, a): return self._do(math.sqrt, a)
    def exp(self, a): return self._do(math.exp, a)
    def log(self, a): return self._do(math.log, a)
    def sin(self, a): return self._do(math.sin, a)
    def cos(self, a): return self._do(math.cos, a)
    def abs(self, a): return abs(a)

    def judge(self, d, tol):
        t = float(tol)
        guard = FLOAT_GUARD * max(self.scale, t)
        m = abs(d) - t
        return ("HOLDS" if m < -guard else "FAILS" if m > guard else None,
                {"difference": d, "margin": m, "guard": guard})


class DecSys:
    name, rigorous = "decimal", False

    def __init__(self, prec):
        self.precision = prec
        self.ctx = decimal.Context(prec=prec, traps=[decimal.InvalidOperation,
                                                     decimal.DivisionByZero, decimal.Overflow])
        self.scale = Decimal(0)

    def _do(self, f, *a):
        try:
            v = f(*a)
        except decimal.DecimalException as e:
            raise TierCannot(f"decimal: {type(e).__name__}")
        self.scale = max(self.scale, abs(v))
        return v

    def const(self, fr):
        return self._do(self.ctx.divide, Decimal(fr.numerator), Decimal(fr.denominator))

    def neg(self, a): return self.ctx.minus(a)
    def add(self, a, b): return self._do(self.ctx.add, a, b)
    def sub(self, a, b): return self._do(self.ctx.subtract, a, b)
    def mul(self, a, b): return self._do(self.ctx.multiply, a, b)
    def div(self, a, b): return self._do(self.ctx.divide, a, b)
    def powi(self, a, n): return self._do(self.ctx.power, a, n)
    def sqrt(self, a): return self._do(self.ctx.sqrt, a)
    def exp(self, a): return self._do(self.ctx.exp, a)
    def log(self, a): return self._do(self.ctx.ln, a)
    def abs(self, a): return abs(a)

    def sin(self, a):
        raise TierCannot("no sin / cos at the decimal tier")
    cos = sin

    def judge(self, d, tol):
        t = self.const(tol)
        guard = Decimal(10) ** (-(self.precision // 2)) * max(self.scale, t)
        m = abs(d) - t
        return ("HOLDS" if m < -guard else "FAILS" if m > guard else None,
                {"difference": str(d), "margin": str(m), "guard": str(guard)})


class IntSys:
    name, rigorous = "interval", True

    def __init__(self, prec):
        self.precision = prec
        self.used_enclosure = False

    def const(self, fr): return I.Interval(fr)
    def neg(self, a): return -a
    def add(self, a, b): return a + b
    def sub(self, a, b): return a - b
    def mul(self, a, b): return a * b
    def abs(self, a): return abs(a)

    def _do(self, f, *a):
        try:
            return f(*a)
        except I.IntervalVoid as e:
            raise NumVoid(str(e))

    def div(self, a, b): return self._do(lambda: a / b)
    def powi(self, a, n): return self._do(a.powi, n)

    def _enc(self, f, a):
        self.used_enclosure = True
        return self._do(f, a, self.precision)

    def sqrt(self, a): return self._enc(I.sqrt, a)
    def exp(self, a): return self._enc(I.exp, a)
    def log(self, a): return self._enc(I.ln, a)
    def sin(self, a): return self._enc(I.sin, a)
    def cos(self, a): return self._enc(I.cos, a)

    def judge(self, d, tol):
        if -tol <= d.lo and d.hi <= tol:
            return "HOLDS", {}
        if d.lo > tol or d.hi < -tol:
            return "FAILS", {}
        return None, {}


def evaluate(node, src, env, S):
    """Value of an ast node in number system S. env: name -> S value."""
    num = exact_number(node, src)
    if num is not None:
        return S.const(num)
    if isinstance(node, ast.Name):
        if node.id not in env:
            raise NumVoid(f"no value for symbol {node.id!r}")
        return env[node.id]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        v = evaluate(node.operand, src, env, S)
        return S.neg(v) if isinstance(node.op, ast.USub) else v
    if isinstance(node, ast.BinOp):
        if isinstance(node.op, ast.Pow):
            k = exact_number(node.right, src)
            if k is None:
                raise NumVoid("exponent is not a literal number")
            base = evaluate(node.left, src, env, S)
            if k.denominator == 1:
                return S.powi(base, int(k))
            if abs(k) == Fraction(1, 2):
                r = S.sqrt(base)
                return r if k > 0 else S.div(S.const(Fraction(1)), r)
            raise NumVoid(f"power {k} is not supported (integers and 1/2 only)")
        a = evaluate(node.left, src, env, S)
        b = evaluate(node.right, src, env, S)
        if isinstance(node.op, ast.Add):
            return S.add(a, b)
        if isinstance(node.op, ast.Sub):
            return S.sub(a, b)
        if isinstance(node.op, ast.Mult):
            return S.mul(a, b)
        if isinstance(node.op, ast.Div):
            return S.div(a, b)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
            and node.func.id in FUNCTIONS and len(node.args) == 1 and not node.keywords:
        x = evaluate(node.args[0], src, env, S)
        f = node.func.id
        if f == "tan":
            return S.div(S.sin(x), S.cos(x))
        return getattr(S, f)(x)
    raise NumVoid(f"unsupported syntax {type(node).__name__}")
