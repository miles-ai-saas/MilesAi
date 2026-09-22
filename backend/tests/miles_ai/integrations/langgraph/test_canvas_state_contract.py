"""LangGraph 画布 state 契约守卫：读写键必须声明在 ``CanvasGraphState``。

LangGraph 只按 State TypedDict 的注解建立通道；未声明的键在 ``ainvoke`` 时会被
**静默丢弃**（读取端得 ``None``，不报错）。曾因 ``_State`` 漏声明 ``media``，导致画布
``ctx.media`` 整条附图链路实际失效却无测试报警，故此处以源码扫描锁死不变式：

- ``compiler/run.py`` 构造的初始 state 键 ⊆ ``CanvasGraphState`` 注解
- ``compiler/*.py`` 中 ``state.get("k")`` / ``state["k"]`` 读取键 ⊆ ``CanvasGraphState`` 注解

风格对齐 ``tests/test_l3_neutral_imports.py``（同样是源码扫描守卫）。
"""

from __future__ import annotations

import ast

from miles_ai.integrations.langgraph.compiler.state import CanvasGraphState
from tests.paths import BACKEND_ROOT

# 路径常量统一来自 ``tests.paths``（本文件已搬到 tests/miles_ai/integrations/langgraph/，
# 目录深度变化后 ``parents`` 不再可靠）。
_BACKEND_DIR = BACKEND_ROOT
_COMPILER_DIR = _BACKEND_DIR / "packages" / "miles-ai" / "src" / "miles_ai" / "integrations" / "langgraph" / "compiler"


def _declared_keys() -> set[str]:
    return set(CanvasGraphState.__annotations__)


def _literal_str(node: ast.expr | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _initial_state_keys() -> set[str]:
    """``run_compiled_canvas`` 中 ``initial`` 字典字面量的键。"""
    tree = ast.parse((_COMPILER_DIR / "run.py").read_text(encoding="utf-8"))
    keys: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "initial":
            if isinstance(node.value, ast.Dict):
                keys.update(s for k in node.value.keys if (s := _literal_str(k)))
    return keys


def _state_read_keys() -> set[str]:
    """``compiler/`` 内 ``state.get("k")`` / ``state["k"]`` 读取到的字符串键。"""
    keys: set[str] = set()
    for path in sorted(_COMPILER_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            literal: str | None = None
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "state"
                and node.args
            ):
                literal = _literal_str(node.args[0])
            elif isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == "state":
                literal = _literal_str(node.slice)
            if literal:
                keys.add(literal)
    return keys


def test_initial_state_keys_are_declared_channels():
    missing = _initial_state_keys() - _declared_keys()
    assert not missing, f"run.py 初始 state 含未声明通道（LangGraph 会静默丢弃）：{sorted(missing)}"


def test_state_read_keys_are_declared_channels():
    missing = _state_read_keys() - _declared_keys()
    assert not missing, f"compiler 节点读取了未声明通道（恒为 None）：{sorted(missing)}"


def test_media_channel_declared():
    """回归锚点：画布附图通道 ``media`` 必须声明，否则含图运行拿不到任何附件。"""
    assert "media" in _declared_keys()
