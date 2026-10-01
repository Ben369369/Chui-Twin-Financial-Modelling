"""Safe arithmetic formulas over KPI names, e.g. "units + unit_value".

Parsed with ast; only numbers, names, + - * / ** and unary minus are allowed.
Works element-wise on NumPy arrays so the simulator can evaluate all paths at once.
"""

from __future__ import annotations

import ast
import operator
from typing import Mapping

_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}


class Formula:
    def __init__(self, text: str):
        self.text = text
        self._tree = ast.parse(text, mode="eval").body
        self.names = sorted(self._collect(self._tree))

    def _collect(self, node: ast.AST) -> set[str]:
        if isinstance(node, ast.Name):
            return {node.id}
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return set()
        if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
            return self._collect(node.left) | self._collect(node.right)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            return self._collect(node.operand)
        raise ValueError(f"unsupported expression in formula {self.text!r}: {ast.dump(node)}")

    def evaluate(self, values: Mapping[str, object]):
        return self._eval(self._tree, values)

    def _eval(self, node: ast.AST, values: Mapping[str, object]):
        if isinstance(node, ast.Name):
            return values[node.id]
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.BinOp):
            return _BINOPS[type(node.op)](self._eval(node.left, values), self._eval(node.right, values))
        if isinstance(node, ast.UnaryOp):
            v = self._eval(node.operand, values)
            return -v if isinstance(node.op, ast.USub) else v
        raise AssertionError("unreachable")

    def gradient(self, at: Mapping[str, float], eps: float = 1e-6) -> dict[str, float]:
        """Numerical partial derivatives, used to linearize formulas for attribution."""
        base = float(self.evaluate(at))
        grad = {}
        for n in self.names:
            bumped = dict(at)
            bumped[n] = at[n] + eps
            grad[n] = (float(self.evaluate(bumped)) - base) / eps
        return grad
