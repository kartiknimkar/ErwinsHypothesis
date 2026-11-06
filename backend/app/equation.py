"""Safe reader for user-typed equations such as "Y = A*exp(-K*X) + C".

Only arithmetic, numbers, the variable X, parameter names and a fixed list of math
functions are allowed. Nothing else (attributes, imports, indexing, strings...) can run.
"""
from __future__ import annotations

import ast
import re

import numpy as np

FUNCS = {
    "exp": np.exp, "log": np.log, "ln": np.log, "log10": np.log10, "log2": np.log2, "sqrt": np.sqrt,
    "abs": np.abs, "sin": np.sin, "cos": np.cos, "tan": np.tan, "arctan": np.arctan, "atan": np.arctan,
    "sinh": np.sinh, "cosh": np.cosh, "tanh": np.tanh,
    "min": np.minimum, "max": np.maximum,
}
CONSTS = {"pi": np.pi, "e": np.e}
_OPS = {ast.Add: np.add, ast.Sub: np.subtract, ast.Mult: np.multiply, ast.Div: np.divide, ast.Pow: np.power}
_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class EquationError(ValueError):
    pass


def parse(text: str):
    """Return (ast tree, list of parameter names in order of appearance)."""
    t = (text or "").strip()
    if not t:
        raise EquationError("Type an equation, for example: Y = A*exp(-K*X) + C")
    if "=" in t:
        lhs, t = t.split("=", 1)
        if lhs.strip().upper() != "Y":
            raise EquationError("The equation should start with 'Y =' .")
    t = t.replace("^", "**").replace("×", "*").replace("−", "-").strip()
    if len(t) > 500:
        raise EquationError("That equation is too long.")
    try:
        tree = ast.parse(t, mode="eval")
    except SyntaxError:
        raise EquationError("The equation couldn't be read. Check brackets and operators (+ − * / ^).")
    params = []

    def check(node):
        if isinstance(node, ast.Expression):
            return check(node.body)
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            check(node.left); check(node.right); return
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            check(node.operand); return
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FUNCS and not node.keywords:
            if not node.args:
                raise EquationError(f"{node.func.id}() needs a value inside the brackets.")
            for a in node.args:
                check(a)
            return
        if isinstance(node, ast.Name):
            n = node.id
            if n in FUNCS:
                raise EquationError(f"{n} is a function; write it with brackets, e.g. {n}(X).")
            if n not in CONSTS and n != "X" and n not in params:
                if not _NAME.match(n):
                    raise EquationError(f"'{n}' isn't a valid parameter name.")
                params.append(n)
            return
        raise EquationError("Only numbers, X, parameter names, + − * / ^ and math functions "
                            f"({', '.join(sorted(FUNCS))}) are allowed.")

    check(tree)
    if not params:
        raise EquationError("The equation has no parameters to fit. Use names like A, K, Top, Bottom.")
    if "X" not in {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}:
        raise EquationError("The equation doesn't use X.")
    return tree, params


def compile_equation(text: str):
    """Return (f(x, *params), parameter names)."""
    tree, params = parse(text)

    def ev(node, env):
        if isinstance(node, ast.Expression):
            return ev(node.body, env)
        if isinstance(node, ast.BinOp):
            return _OPS[type(node.op)](ev(node.left, env), ev(node.right, env))
        if isinstance(node, ast.UnaryOp):
            v = ev(node.operand, env)
            return -v if isinstance(node.op, ast.USub) else v
        if isinstance(node, ast.Constant):
            return float(node.value)
        if isinstance(node, ast.Call):
            return FUNCS[node.func.id](*[ev(a, env) for a in node.args])
        if isinstance(node, ast.Name):
            return CONSTS[node.id] if node.id in CONSTS else env[node.id]
        raise EquationError("Unsupported expression.")

    def f(x, *p):
        env = dict(zip(params, p))
        env["X"] = np.asarray(x, float)
        with np.errstate(all="ignore"):
            out = ev(tree, env)
        return np.broadcast_to(np.asarray(out, float), np.shape(env["X"])).astype(float)

    return f, params
