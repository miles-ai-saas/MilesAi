"""内置 calculator 工具：AST 白名单运算，禁止函数调用与变量访问。"""

import ast
import operator as op

_SAFE_OPS = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.Pow: op.pow,
    ast.USub: op.neg,
}


def _eval_expr(node: ast.AST):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp):
        return _SAFE_OPS[type(node.op)](_eval_expr(node.left), _eval_expr(node.right))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return _SAFE_OPS[ast.USub](_eval_expr(node.operand))
    raise ValueError("不支持的表达式")


def safe_calculate(expression: str) -> float:
    """解析并安全求值四则运算表达式，不支持函数与变量。"""
    tree = ast.parse(expression.strip(), mode="eval")
    return float(_eval_expr(tree.body))
