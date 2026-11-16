"""poly -- is an expression a polynomial in some variables, and of what degree?

Co-authored. Read from the ast, nothing is expanded.

  polynomial   built from the variables and rational constants with + - *,
               powers with a literal non-negative integer exponent, and
               division by a sub-expression that holds none of the variables
  degree       an UPPER bound per variable: + and - take the larger, * adds,
               ** n multiplies by n. Cancellation can make the true degree
               lower; a bound is all the proof below needs.
  otherwise    non_polynomial, with the reason (a function call, a variable
               in a divisor, a negative or non-integer power, ...)

Why a bound is enough: a polynomial of degree at most d_i in each variable
x_i that is 0 on a full grid of (d_i + 1) distinct values per variable is
the zero polynomial. (One variable: a non-zero polynomial of degree <= d has
at most d roots. Several: apply that to one variable at a time.) So if
lhs - rhs is 0 at every point of such a grid, lhs = rhs for all values.
"""
import ast

from .tiers import exact_number


class NonPolynomial(Exception):
    pass


def degrees(node, src, variables):
    """{variable: degree bound} of an ast node, or raise NonPolynomial."""
    if exact_number(node, src) is not None:
        return {}
    if isinstance(node, ast.Name):
        return {node.id: 1} if node.id in variables else {}
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        return degrees(node.operand, src, variables)
    if isinstance(node, ast.BinOp):
        if isinstance(node.op, ast.Pow):
            base = degrees(node.left, src, variables)
            k = exact_number(node.right, src)
            if k is None:
                raise NonPolynomial("an exponent that is not a literal number")
            if not base:
                if k.denominator != 1:
                    raise NonPolynomial(f"a constant to the power {k}: not a rational constant")
                return {}
            if k.denominator != 1 or k < 0:
                raise NonPolynomial(f"a variable expression to the power {k}")
            return {v: d * int(k) for v, d in base.items()}
        a = degrees(node.left, src, variables)
        b = degrees(node.right, src, variables)
        if isinstance(node.op, (ast.Add, ast.Sub)):
            return {v: max(a.get(v, 0), b.get(v, 0)) for v in set(a) | set(b)}
        if isinstance(node.op, ast.Mult):
            return {v: a.get(v, 0) + b.get(v, 0) for v in set(a) | set(b)}
        if isinstance(node.op, ast.Div):
            if b:
                raise NonPolynomial("a variable in a divisor: " + ", ".join(sorted(b)))
            return a
        raise NonPolynomial(f"operator {type(node.op).__name__}")
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        raise NonPolynomial(f"the function {node.func.id}")
    raise NonPolynomial(f"syntax {type(node).__name__}")


def degree_of_difference(sides, variables):
    """Degree bounds of lhs - rhs. sides: ((src, tree), (src, tree))."""
    (ls, lt), (rs, rt) = sides
    a, b = degrees(lt, ls, variables), degrees(rt, rs, variables)
    return {v: max(a.get(v, 0), b.get(v, 0)) for v in sorted(variables)}
