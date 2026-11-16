"""interval -- closed intervals over Fraction. Co-authored. Stdlib only.

+ - * / and integer powers are exact. sqrt, exp, ln, sin, cos return
enclosures: an interval that contains every true value, with bounds rounded
outward at a set number of digits.

  sqrt exp ln   decimal's sqrt / exp / ln are correctly rounded (half a unit
                in the last place of the working precision). The argument is
                first rounded the safe way, the result is then moved one full
                unit in the last place outward, and that Decimal is turned
                into a Fraction exactly. Exact cases stay exact (perfect
                squares, exp(0), ln(1)).
  sin cos       Taylor series in outward-rounded interval arithmetic, with
                the alternating-series remainder added; pi from Machin's
                formula with both partial-sum brackets. Arguments beyond
                +-1000 are VOID.

A division by an interval containing 0, sqrt reaching below 0, ln reaching
0 or below: IntervalVoid, never a number.
"""
import decimal
import math
from decimal import Decimal
from fractions import Fraction

TRIG_LIMIT = 1000


class IntervalVoid(Exception):
    pass


class Interval:
    __slots__ = ("lo", "hi")

    def __init__(self, lo, hi=None):
        lo = Fraction(lo)
        hi = lo if hi is None else Fraction(hi)
        if lo > hi:
            raise ValueError(f"interval bounds out of order: {lo} > {hi}")
        self.lo, self.hi = lo, hi

    # ---- reading ----
    @property
    def is_point(self):
        return self.lo == self.hi

    @property
    def width(self):
        return self.hi - self.lo

    def contains(self, x):
        return self.lo <= x <= self.hi

    def inside(self, other):
        return other.lo <= self.lo and self.hi <= other.hi

    def __eq__(self, o):
        return isinstance(o, Interval) and (self.lo, self.hi) == (o.lo, o.hi)

    def __hash__(self):
        return hash((self.lo, self.hi))

    def __repr__(self):
        return f"[{self.lo}, {self.hi}]"

    def as_record(self):
        return {"lo": str(self.lo), "hi": str(self.hi),
                "approx": [float(self.lo), float(self.hi)], "is_point": self.is_point}

    # ---- exact arithmetic ----
    def __neg__(self):
        return Interval(-self.hi, -self.lo)

    def __add__(self, o):
        return Interval(self.lo + o.lo, self.hi + o.hi)

    def __sub__(self, o):
        return Interval(self.lo - o.hi, self.hi - o.lo)

    def __mul__(self, o):
        p = (self.lo * o.lo, self.lo * o.hi, self.hi * o.lo, self.hi * o.hi)
        return Interval(min(p), max(p))

    def __truediv__(self, o):
        if o.lo <= 0 <= o.hi:
            raise IntervalVoid(f"division by an interval containing 0: {o}")
        return self * Interval(1 / o.hi, 1 / o.lo)

    def __abs__(self):
        if self.lo >= 0:
            return self
        if self.hi <= 0:
            return -self
        return Interval(0, max(-self.lo, self.hi))

    def powi(self, n):
        if n < 0:
            return Interval(1) / self.powi(-n)
        if n == 0:
            return Interval(1)
        if n % 2 or self.lo >= 0:
            return Interval(self.lo ** n, self.hi ** n)
        if self.hi <= 0:
            return Interval(self.hi ** n, self.lo ** n)
        return Interval(0, max(self.lo ** n, self.hi ** n))

    def hull(self, o):
        return Interval(min(self.lo, o.lo), max(self.hi, o.hi))

    def split(self):
        mid = (self.lo + self.hi) / 2
        return Interval(self.lo, mid), Interval(mid, self.hi)


# ---- outward rounding -------------------------------------------------------
def _ctx(prec, rounding=decimal.ROUND_HALF_EVEN):
    return decimal.Context(prec=prec, rounding=rounding, Emax=decimal.MAX_EMAX,
                           Emin=decimal.MIN_EMIN,
                           traps=[decimal.InvalidOperation, decimal.DivisionByZero,
                                  decimal.Overflow])


def to_decimal(x, prec, down):
    """x (Fraction) as a Decimal of `prec` digits, rounded down or up."""
    c = _ctx(prec, decimal.ROUND_FLOOR if down else decimal.ROUND_CEILING)
    return c.divide(Decimal(x.numerator), Decimal(x.denominator))


def round_out(iv, prec):
    """The same interval or a slightly wider one, with `prec`-digit bounds."""
    return Interval(Fraction(to_decimal(iv.lo, prec, True)),
                    Fraction(to_decimal(iv.hi, prec, False)))


def _ulp(y, prec):
    return Fraction(10) ** (y.adjusted() - (prec - 1))


def _monotone(name, x, prec, down):
    """One bound of an increasing function at x: below the true value if down."""
    try:
        xd = to_decimal(x, prec, down)
        y = getattr(_ctx(prec), name)(xd)
    except decimal.DecimalException as e:
        raise IntervalVoid(f"{name}: {type(e).__name__} at {prec} digits")
    if y.is_zero():
        # only when the true value is below the smallest Decimal: no usable bound
        raise IntervalVoid(f"{name}: result underflows at {prec} digits")
    f = Fraction(y)
    return f - _ulp(y, prec) if down else f + _ulp(y, prec)


def _exact_sqrt(x):
    n, d = x.numerator, x.denominator
    rn, rd = math.isqrt(n), math.isqrt(d)
    return Fraction(rn, rd) if rn * rn == n and rd * rd == d else None


def sqrt(iv, prec):
    if iv.lo < 0:
        raise IntervalVoid(f"sqrt of an interval reaching below 0: {iv}")
    out = []
    for x, down in ((iv.lo, True), (iv.hi, False)):
        e = _exact_sqrt(x)
        if e is None:
            e = max(Fraction(0), _monotone("sqrt", x, prec, down)) if down \
                else _monotone("sqrt", x, prec, down)
        out.append(e)
    return Interval(*out)


def exp(iv, prec):
    lo = Fraction(1) if iv.lo == 0 else max(Fraction(0), _monotone("exp", iv.lo, prec, True))
    hi = Fraction(1) if iv.hi == 0 else _monotone("exp", iv.hi, prec, False)
    return Interval(lo, hi)


def ln(iv, prec):
    if iv.lo <= 0:
        raise IntervalVoid(f"ln of an interval reaching 0 or below: {iv}")
    lo = Fraction(0) if iv.lo == 1 else _monotone("ln", iv.lo, prec, True)
    hi = Fraction(0) if iv.hi == 1 else _monotone("ln", iv.hi, prec, False)
    return Interval(lo, hi)


# ---- pi, sin, cos -------------------------------------------------------------
_PI = {}


def _arctan_inv(n, digits):
    """Enclosure of arctan(1/n), n > 1: an alternating series whose two last
    partial sums bracket the value."""
    tol = Fraction(1, 10 ** (digits + 3))
    s, k, sign = Fraction(0), 0, 1
    while True:
        term = Fraction(1, (2 * k + 1) * n ** (2 * k + 1))
        prev = s
        s += sign * term
        if term < tol:
            return Interval(min(prev, s), max(prev, s))
        k, sign = k + 1, -sign


def pi(prec):
    if prec not in _PI:
        a, b = _arctan_inv(5, prec + 5), _arctan_inv(239, prec + 5)
        _PI[prec] = round_out(Interval(16) * a - Interval(4) * b, prec + 5)
    return _PI[prec]


def _series(x, prec, cosine):
    """Enclosure of sin(x) or cos(x) at a point x, |x| <= TRIG_LIMIT."""
    if abs(x) > TRIG_LIMIT:
        raise IntervalVoid(f"sin / cos argument beyond +-{TRIG_LIMIT}: {float(x):.6g}")
    digits = prec + 12 + int(abs(x) * Fraction(45, 100))
    x2 = round_out(Interval(x * x), digits)
    term = Interval(1) if cosine else round_out(Interval(abs(x)), digits)
    total, k, sign = term, 0, 1
    tol = Fraction(1, 10 ** (prec + 4))
    while True:
        k += 1
        den = (2 * k - 1) * (2 * k) if cosine else (2 * k) * (2 * k + 1)
        term = round_out(term * x2 * Interval(Fraction(1, den)), digits)
        decreasing = x2.hi <= den
        if decreasing and term.hi < tol:
            total = total + Interval(-term.hi, term.hi)       # the remainder
            break
        sign = -sign
        total = round_out(total + (term if sign > 0 else -term), digits)
    if not cosine and x < 0:
        total = -total
    return Interval(max(total.lo, Fraction(-1)), min(total.hi, Fraction(1))) \
        if total.lo <= 1 and total.hi >= -1 else total


def _trig(iv, prec, cosine):
    if iv.width >= 7:                                  # more than a full turn
        if max(abs(iv.lo), abs(iv.hi)) > TRIG_LIMIT:
            raise IntervalVoid(f"sin / cos argument beyond +-{TRIG_LIMIT}")
        return Interval(-1, 1)
    out = _series(iv.lo, prec, cosine)
    if not iv.is_point:
        out = out.hull(_series(iv.hi, prec, cosine))
        p = pi(prec)
        # turning points: cos at k*pi, sin at (k + 1/2)*pi; value (-1)**k
        half = Fraction(0) if cosine else Fraction(1, 2)
        k = math.floor(iv.lo / p.hi - half) - 1
        last = math.ceil(iv.hi / p.lo - half) + 1
        while k <= last:
            c = Interval(k + half) * p
            if c.hi >= iv.lo and c.lo <= iv.hi:        # may lie inside: include it
                out = out.hull(Interval(1 if k % 2 == 0 else -1))
            k += 1
    return Interval(max(out.lo, Fraction(-1)), min(out.hi, Fraction(1)))


def sin(iv, prec):
    return _trig(iv, prec, False)


def cos(iv, prec):
    return _trig(iv, prec, True)
