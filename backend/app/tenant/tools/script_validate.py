"""Python 脚本工具源码 AST 校验（API 与 Runner 共用）。"""

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
    def __init__(self) -> None:
        self.has_run = False
        self.errors: list[str] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if node.name == "run":
            if len(node.args.args) < 1:
                self.errors.append("run() 须至少接受一个 params 参数")
            else:
                self.has_run = True
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.errors.append("不支持 async def")

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.errors.append("不支持 class 定义")

    def generic_visit(self, node: ast.AST) -> None:
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
