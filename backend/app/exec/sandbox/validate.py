"""Python 脚本工具源码 AST 校验（API 与 Runner 共用）。

脚本禁止 ``import``；Runner 运行时预注入 ``json`` / ``math`` / ``re`` /
``datetime`` 四个白名单模块，脚本可直接引用。
"""

from __future__ import annotations

import ast

from app.common.exceptions import BadRequestError

_MAX_SOURCE_LEN = 32_768
_FORBIDDEN_SNIPPETS = (
    "__import__",
    "import os",
    "import sys",
    "import subprocess",
    "import socket",
    "import httpx",
    "import requests",
    "open(",
    "eval(",
    "exec(",
    "compile(",
    "globals(",
    "locals(",
    "getattr(",
    "setattr(",
    "delattr(",
    "breakpoint(",
)

_FORBIDDEN_AST = (
    ast.Import,
    ast.ImportFrom,
    ast.Global,
    ast.Nonlocal,
)


class _ScriptVisitor(ast.NodeVisitor):
    """遍历脚本 AST，收集禁用语法并确认存在合法的 ``run`` 入口。"""

    def __init__(self) -> None:
        self.has_run = False
        self.errors: list[str] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """识别 ``run`` 入口并校验其至少接收一个 params 参数。"""
        if node.name == "run":
            if len(node.args.args) < 1:
                self.errors.append("run() 须至少接受一个 params 参数")
            else:
                self.has_run = True
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """禁止 async 定义（Runner 以同步方式调用 ``run``）。"""
        self.errors.append("不支持 async def")

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """禁止 class 定义。"""
        self.errors.append("不支持 class 定义")

    def generic_visit(self, node: ast.AST) -> None:
        """拦截禁用语法与危险内置调用，其余节点继续递归遍历。"""
        if isinstance(node, _FORBIDDEN_AST):
            self.errors.append(f"不允许的语法: {type(node).__name__}")
            return
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in {"eval", "exec", "compile", "open", "__import__"}:
                self.errors.append(f"禁止调用 {node.func.id}()")
                return
        super().generic_visit(node)


def validate_script_source(source: str) -> str:
    """校验脚本；通过则返回 strip 后的源码。"""
    text = (source or "").strip()
    if not text:
        raise BadRequestError("脚本源码不能为空")
    if len(text) > _MAX_SOURCE_LEN:
        raise BadRequestError(f"脚本长度不能超过 {_MAX_SOURCE_LEN} 字符")
    lowered = text.lower()
    for snippet in _FORBIDDEN_SNIPPETS:
        if snippet.lower() in lowered:
            raise BadRequestError(f"脚本含禁止用法: {snippet}")

    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        raise BadRequestError(f"脚本语法错误: {e.msg}") from e

    visitor = _ScriptVisitor()
    visitor.visit(tree)
    if not visitor.has_run:
        raise BadRequestError("脚本须定义 run(params) 函数")
    if visitor.errors:
        raise BadRequestError(visitor.errors[0])
    return text
