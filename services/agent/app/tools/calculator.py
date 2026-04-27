from __future__ import annotations

import ast
import operator
from decimal import Decimal

from langchain_core.tools import tool


def _apply_unary(op: ast.unaryop, value: Decimal) -> Decimal:
    if isinstance(op, ast.USub):
        return operator.neg(value)
    raise ValueError("Unsupported unary operator")


def _apply_bin(op: ast.operator, left: Decimal, right: Decimal) -> Decimal:
    if isinstance(op, ast.Add):
        return operator.add(left, right)
    if isinstance(op, ast.Sub):
        return operator.sub(left, right)
    if isinstance(op, ast.Mult):
        return operator.mul(left, right)
    if isinstance(op, ast.Div):
        return operator.truediv(left, right)
    if isinstance(op, ast.Pow):
        return operator.pow(left, right)
    raise ValueError("Unsupported binary operator")


def _eval_numeric(node: ast.AST) -> Decimal:
    if isinstance(node, ast.Constant):
        val = node.value
        if isinstance(val, bool) or isinstance(val, complex):
            raise ValueError("Unsupported literal type")
        if isinstance(val, int | float):
            return Decimal(str(val))
        raise ValueError("Unsupported literal type")
    if isinstance(node, ast.BinOp):
        left = _eval_numeric(node.left)
        right = _eval_numeric(node.right)
        try:
            return _apply_bin(node.op, left, right)
        except ArithmeticError as exc:
            raise ValueError(str(exc)) from exc
    if isinstance(node, ast.UnaryOp):
        operand = _eval_numeric(node.operand)
        try:
            return _apply_unary(node.op, operand)
        except ArithmeticError as exc:
            raise ValueError(str(exc)) from exc
    raise ValueError("Unsupported expression")


@tool("calculator")
async def calculator(expression: str) -> str:
    """Evaluate a simple arithmetic expression for accounting calculations."""
    stripped = expression.strip()
    if not stripped:
        return "Calculation failed: empty expression"
    try:
        tree = ast.parse(stripped, mode="eval")
        result = _eval_numeric(tree.body)
    except SyntaxError as exc:
        return f"Calculation failed: invalid syntax ({exc.msg})"
    except Exception as exc:
        return f"Calculation failed: {exc}"
    return str(result)
