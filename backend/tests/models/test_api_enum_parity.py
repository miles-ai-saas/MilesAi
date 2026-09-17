"""API 侧枚举声明与 ORM 侧的逐字一致护栏，以及「不得 `is` 比较枚举成员」的守卫。

背景：API 声明层（``views/`` / ``schemas/``）不得 import ORM 包（``.importlinter``
契约 ``api-layer-no-orm``），故 21 个持久化枚举在 API 侧各有一份**独立声明**。
本模块把「两份定义逐字一致」变成可执行约束：基类、成员名、成员顺序、成员值、类 docstring
五项全等。类 docstring 也在其列，因为 Pydantic 会把 enum 类 docstring 渲染成 schema 的
``description`` —— 漏抄会静默漂移 ``openapi.snapshot.json``（Task 3 实测：5 个带 docstring
的 ORM 枚举曾因此丢掉 description）。

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

from miles_admin.app_ops.schemas import enums as admin_enums
from miles_admin.models import billing as orm_admin_billing
from miles_common.schemas import api_enums as common_enums
from miles_common.schemas import marketplace as common_marketplace
from miles_core.models import risk as orm_risk
from miles_core.models.agent import agent as orm_agent
from miles_core.models.compliance import constants as orm_compliance
from miles_core.models.flow import flow as orm_flow
from miles_core.models.kb import knowledge_base as orm_kb
from miles_core.models.marketplace import models as orm_marketplace
from miles_core.models.meta import category as orm_category
from miles_core.models.model import catalog as orm_catalog
from miles_core.models.model import generative_job as orm_generative_job
from miles_core.models.platform import tenant as orm_tenant
from miles_core.models.task import task_record as orm_task_record
from miles_portal.tenant.a2a import models as orm_a2a
from miles_portal.tenant.a2a.schemas import enums as a2a_enums
from miles_portal.tenant.agents.schemas import enums as agents_enums
from miles_portal.tenant.categories.schemas import enums as categories_enums
from miles_portal.tenant.compliance.schemas import enums as compliance_enums
from miles_portal.tenant.flows.schemas import enums as flows_enums
from miles_portal.tenant.generative.schemas import enums as generative_enums
from miles_portal.tenant.hooks import models as orm_hooks
from miles_portal.tenant.hooks.schemas import enums as hooks_enums
from miles_portal.tenant.kb.schemas import enums as kb_enums
from miles_portal.tenant.mcp import models as orm_mcp
from miles_portal.tenant.mcp.schemas import enums as mcp_enums
from miles_portal.tenant.tasks.schemas import enums as tasks_enums
from miles_portal.tenant.tools import models as orm_tools
from miles_portal.tenant.tools.schemas import enums as tools_enums

CASES: list[tuple[str, type[enum.Enum], type[enum.Enum]]] = [
    ("A2aPeerStatus", a2a_enums.A2aPeerStatus, orm_a2a.A2aPeerStatus),
    ("AgentStatus", agents_enums.AgentStatus, orm_agent.AgentStatus),
    ("AgentType", agents_enums.AgentType, orm_agent.AgentType),
    ("BillStatus", admin_enums.BillStatus, orm_admin_billing.BillStatus),
    ("CategoryDomain", categories_enums.CategoryDomain, orm_category.CategoryDomain),
    ("DocumentStatus", kb_enums.DocumentStatus, orm_kb.DocumentStatus),
    ("FlowStatus", flows_enums.FlowStatus, orm_flow.FlowStatus),
    ("GenerativeJobStatus", generative_enums.GenerativeJobStatus, orm_generative_job.GenerativeJobStatus),
    ("HookScope", hooks_enums.HookScope, orm_hooks.HookScope),
    ("HookTrigger", hooks_enums.HookTrigger, orm_hooks.HookTrigger),
    ("HookType", hooks_enums.HookType, orm_hooks.HookType),
    ("MarketplaceAppStatus", common_marketplace.MarketplaceAppStatus, orm_marketplace.MarketplaceAppStatus),
    ("MarketplaceAppVisibility", common_marketplace.MarketplaceAppVisibility, orm_marketplace.MarketplaceAppVisibility),
    ("McpStatus", mcp_enums.McpStatus, orm_mcp.McpStatus),
    ("ModelCapabilityType", common_enums.ModelCapabilityType, orm_catalog.ModelCapabilityType),
    ("ModelVendor", common_enums.ModelVendor, orm_catalog.ModelVendor),
    ("RiskSeverity", admin_enums.RiskSeverity, orm_risk.RiskSeverity),
    ("SensitiveAction", compliance_enums.SensitiveAction, orm_compliance.SensitiveAction),
    ("TaskStatus", tasks_enums.TaskStatus, orm_task_record.TaskStatus),
    ("TenantStatus", common_enums.TenantStatus, orm_tenant.TenantStatus),
    ("ToolType", tools_enums.ToolType, orm_tools.ToolType),
]


def _mismatch_report(name: str, api: type[enum.Enum], orm: type[enum.Enum]) -> str:
    """返回首个不一致的可读描述；完全一致时返回空串。

    按「基类 → 成员名/顺序 → 成员值 → 类 docstring」短路。四项都是 Pydantic 生成 schema 的
    输入（类 docstring 渲染成 ``description``），故都必须逐字一致。
    """
    if api.__bases__ != orm.__bases__:
        return f"{name} 的直接基类不一致：API={api.__bases__} ORM={orm.__bases__}"
    api_pairs = [(m.name, m.value) for m in api]
    orm_pairs = [(m.name, m.value) for m in orm]
    if [n for n, _ in api_pairs] != [n for n, _ in orm_pairs]:
        return f"{name} 的成员名或顺序不一致：API={[n for n, _ in api_pairs]} ORM={[n for n, _ in orm_pairs]}"
    for member_name, api_value in api_pairs:
        orm_value = dict(orm_pairs)[member_name]
        if api_value != orm_value:
            return f"{name}.{member_name} 的 API 值 {api_value!r} != ORM 值 {orm_value!r}"
    if api.__doc__ != orm.__doc__:
        return f"{name} 的 API 类 docstring {api.__doc__!r} != ORM 类 docstring {orm.__doc__!r}"
    return ""


@pytest.mark.parametrize(("name", "api", "orm"), CASES, ids=[c[0] for c in CASES])
def test_api_enum_is_an_independent_declaration(name, api, orm):
    """API 侧必须是独立类；转 re-export 会字面满足契约而公开契约仍绑 ORM（设计 §4 已否决）。"""
    assert api is not orm, f"{name} 在 API 侧是 ORM 枚举的 re-export，不是独立声明"


@pytest.mark.parametrize(("name", "api", "orm"), CASES, ids=[c[0] for c in CASES])
def test_api_enum_matches_orm_verbatim(name, api, orm):
    """基类、成员名、成员顺序、成员值、类 docstring 必须与 ORM 侧逐字一致。

    前四项决定 Pydantic 生成的 ``enum`` 数组，类 docstring 决定 ``description``。
    """
    assert issubclass(api, enum.StrEnum), f"{name} 的 API 声明不是 enum.StrEnum"
    report = _mismatch_report(name, api, orm)
    assert not report, report


_BACKEND = Path(__file__).resolve().parents[2]
_PACKAGES = _BACKEND / "packages"
_ENUM_NAMES = frozenset(name for name, _, _ in CASES)


def _enum_class_of(operand: ast.expr) -> str | None:
    """若 ``operand`` 形如 ``<任意前缀>.ClassName.MEMBER`` 且 ``ClassName`` 是已知枚举类，返回它。

    覆盖 ``Name.MEMBER``、``alias.ClassName.MEMBER``、``pkg.mod.ClassName.MEMBER`` 三种写法
    —— 后两种正是迁移后 ``from ...schemas import enums as X`` 的风格，旧判据（要求
    ``operand.value`` 是 ``ast.Name``）会漏检。
    """
    if not isinstance(operand, ast.Attribute):
        return None
    parent = operand.value
    if isinstance(parent, ast.Name):
        class_name = parent.id
    elif isinstance(parent, ast.Attribute):
        class_name = parent.attr
    else:
        return None
    return class_name if class_name in _ENUM_NAMES else None


def _identity_comparisons(path: Path) -> list[tuple[int, str]]:
    """返回该文件里对枚举成员做 ``is`` / ``is not`` 比较的 (行号, 表达式)。"""
    found: list[tuple[int, str]] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.Compare) or not any(isinstance(op, (ast.Is, ast.IsNot)) for op in node.ops):
            continue
        for operand in [node.left, *node.comparators]:
            if _enum_class_of(operand):
                found.append((node.lineno, ast.unparse(operand)))
    return found


def test_no_identity_comparison_on_enum_members():
    """两份声明是不同类，`is` 跨类恒为 False —— 全仓禁止该写法。

    用 AST 判据而非文本匹配：注释与 docstring 里的说明性提及不应误伤（同 ``tests/test_l3_neutral_imports.py``
    的意图，但那里的目标是 import 语句、这里是比较表达式，故收紧为语法级）。
    """
    paths = [p for p in sorted(_PACKAGES.glob("*/src/**/*.py")) if "__pycache__" not in p.parts]
    assert paths, f"未扫到任何源码文件，扫描面已失效（目录改名？）：{_PACKAGES}"
    offenders: list[str] = []
    for path in paths:
        for lineno, expr in _identity_comparisons(path):
            offenders.append(f"{path.relative_to(_PACKAGES)}:{lineno}: is 比较 {expr}")
    assert not offenders, "API 侧与 ORM 侧的枚举是不同类，`is` 比较跨类恒为 False（`==` / `in` 才按值成立）：\n" + "\n".join(offenders)


def test_parity_table_covers_exactly_21_enums():
    """防有人删表项「修好」测试：表必须恰好 21 项且无重名。"""
    assert len(CASES) == 21, f"平价表应恰有 21 项，实际 {len(CASES)}"
    assert len({name for name, _, _ in CASES}) == 21
