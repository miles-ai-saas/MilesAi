"""API 侧枚举声明与 ORM 侧的逐字一致护栏，以及「不得 `is` 比较枚举成员」的守卫。

背景：API 声明层（``views/`` / ``schemas/``）不得 import ORM 包（``.importlinter``
契约 ``api-layer-no-orm``），故 21 个持久化枚举在 API 侧各有一份**独立声明**。
本模块把「两份定义逐字一致」变成可执行约束：成员名、成员顺序、成员值、基类四项全等。

为什么不能只靠 OpenAPI 快照：快照漂移的失败信息是一整份 JSON diff，指不出是哪个枚举的
哪个成员；本模块的失败信息能直接写成 ``AgentStatus.ENABLED 的 API 值 'enable' != ORM 值 'enabled'``。
两者互补而非替代。

第二个不变量：不得对枚举成员做 ``is`` / ``is not`` 比较。两份声明是**不同类**；
``StrEnum`` 的 ``==`` / ``hash`` / ``str`` / ``format`` 都按值成立（实测，见设计 §3），
唯独 ``is`` 跨类恒为 ``False`` —— 这是本设计唯一会静默出错的写法。
"""

from __future__ import annotations

import ast
import enum
from pathlib import Path

import pytest

from miles_common.schemas import marketplace as common_marketplace
from miles_core.models.marketplace import models as orm_marketplace

CASES: list[tuple[str, type[enum.Enum], type[enum.Enum]]] = [
    ("MarketplaceAppStatus", common_marketplace.MarketplaceAppStatus, orm_marketplace.MarketplaceAppStatus),
    ("MarketplaceAppVisibility", common_marketplace.MarketplaceAppVisibility, orm_marketplace.MarketplaceAppVisibility),
]


def _mismatch_report(name: str, api: type[enum.Enum], orm: type[enum.Enum]) -> str:
    """返回首个不一致的可读描述；完全一致时返回空串。"""
    api_pairs = [(m.name, m.value) for m in api]
    orm_pairs = [(m.name, m.value) for m in orm]
    if [n for n, _ in api_pairs] != [n for n, _ in orm_pairs]:
        return f"{name} 的成员名或顺序不一致：API={[n for n, _ in api_pairs]} ORM={[n for n, _ in orm_pairs]}"
    for member_name, api_value in api_pairs:
        orm_value = dict(orm_pairs)[member_name]
        if api_value != orm_value:
            return f"{name}.{member_name} 的 API 值 {api_value!r} != ORM 值 {orm_value!r}"
    return ""


@pytest.mark.parametrize(("name", "api", "orm"), CASES, ids=[c[0] for c in CASES])
def test_api_enum_is_an_independent_declaration(name, api, orm):
    """API 侧必须是独立类；转 re-export 会字面满足契约而公开契约仍绑 ORM（设计 §4 已否决）。"""
    assert api is not orm, f"{name} 在 API 侧是 ORM 枚举的 re-export，不是独立声明"


@pytest.mark.parametrize(("name", "api", "orm"), CASES, ids=[c[0] for c in CASES])
def test_api_enum_matches_orm_verbatim(name, api, orm):
    """成员名、成员顺序、成员值必须与 ORM 侧逐字一致（Pydantic 按定义顺序生成 enum 数组）。"""
    assert issubclass(api, enum.StrEnum), f"{name} 的 API 声明不是 enum.StrEnum"
    report = _mismatch_report(name, api, orm)
    assert not report, report


_BACKEND = Path(__file__).resolve().parents[2]
_PACKAGES = _BACKEND / "packages"
_ENUM_NAMES = frozenset(name for name, _, _ in CASES)


def _identity_comparisons(path: Path) -> list[tuple[int, str]]:
    """返回该文件里对枚举成员做 ``is`` / ``is not`` 比较的 (行号, 表达式)。"""
    found: list[tuple[int, str]] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.Compare) or not any(isinstance(op, (ast.Is, ast.IsNot)) for op in node.ops):
            continue
        for operand in [node.left, *node.comparators]:
            if isinstance(operand, ast.Attribute) and isinstance(operand.value, ast.Name) and operand.value.id in _ENUM_NAMES:
                found.append((node.lineno, f"{operand.value.id}.{operand.attr}"))
    return found


def test_no_identity_comparison_on_enum_members():
    """两份声明是不同类，`is` 跨类恒为 False —— 全仓禁止该写法。

    用 AST 判据而非文本匹配：注释与 docstring 里的说明性提及不应误伤（同 ``tests/test_l3_neutral_imports.py``
    的意图，但那里的目标是 import 语句、这里是比较表达式，故收紧为语法级）。
    """
    offenders: list[str] = []
    for path in sorted(_PACKAGES.glob("*/src/**/*.py")):
        if "__pycache__" in path.parts:
            continue
        for lineno, expr in _identity_comparisons(path):
            offenders.append(f"{path.relative_to(_PACKAGES)}:{lineno}: is 比较 {expr}")
    assert not offenders, "API 侧与 ORM 侧的枚举是不同类，`is` 比较跨类恒为 False（`==` / `in` 才按值成立）：\n" + "\n".join(offenders)
