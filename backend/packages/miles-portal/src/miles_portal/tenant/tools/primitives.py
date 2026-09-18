"""工具域共用的纯函数，与「内置/自定义」无关。

放在顶层而非 ``handlers/`` 下：``safe_calculate`` 供 calculator handler，``apply_template``
供 ``invoke/custom.py``（租户 HTTP 工具的 URL/headers 模板）——后者不是内置工具路径，
若留在 ``handlers/`` 会让「自定义」分支反向依赖「内置 handler」包。
"""

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


def apply_template(template: str, params: dict) -> str:
    """将 ``{{key}}`` 占位符替换为 params；未提供的占位符保持原样。"""
    out = template
    for k, v in params.items():
        out = out.replace(f"{{{{{k}}}}}", str(v))
    return out
