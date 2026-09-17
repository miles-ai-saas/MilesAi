"""枚举契约：UP042 迁移（``(str, Enum)`` → ``StrEnum``）后的结构不变量与可观测行为。

为什么必须存在：本次迁移把 32 个枚举的基类由 ``(str, Enum)`` 换成 ``StrEnum``。
实测两者唯一的行为差异是 **str() 家族**——``str()`` / f-string / ``format()`` 旧得
``"Class.MEMBER"``、新得成员值本身；而 ``repr()``、``json.dumps``、``==``、
``.name`` / ``.value``、字符串方法、Pydantic 序列化与 JSON schema、以及 SQLAlchemy
的 ``.enums`` / 绑定 / 读回**全部一致**。

故本文件只锁三件事：迁移目标是否达成、唯一被改变的行为是否符合预期、SQLAlchemy
层是否等价。第三条尤其必要——测试套件用 ``AsyncMock`` 顶替 DB、不跑真库，DB 路径
没有任何其他守卫。

**探针注意**：本文件的断言对象就是 ``str(member)``，故任何调试输出必须用
``repr()``；否则会与被测目标同源，把假象写成结论（本设计初稿曾因此误报
``_valid_lookup`` 差异）。
"""

from __future__ import annotations

import enum
import importlib
from collections.abc import Iterator
from typing import Any

from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects import postgresql

# UP042 迁移清单（实测导出：`ruff check --select UP042 --output-format json .`）。
# 22 模块 / 32 枚举 / 134 成员。此表同时是「清单自身不得漂移」的锚点。
_UP042_ENUMS: dict[str, tuple[str, ...]] = {
    "miles_admin.models.billing": ("BillStatus",),
    "miles_ai.flow_runtime.constants": ("CanvasNodeType",),
    "miles_core.models.agent.agent": ("AgentStatus", "AgentType"),
    "miles_core.models.agent.constants": ("AgentPlanner", "AgentRuntimeMode", "SubAgentRoleHint"),
    "miles_core.models.agent.schedule_run": ("AgentScheduleRunStatus",),
    "miles_core.models.compliance.constants": ("SensitiveAction",),
    "miles_core.models.flow.flow": ("FlowStatus",),
    "miles_core.models.kb.knowledge_base": ("DocumentStatus",),
    "miles_core.models.marketplace.models": ("MarketplaceAppStatus", "MarketplaceAppVisibility"),
    "miles_core.models.meta.category": ("CategoryDomain",),
    "miles_core.models.meta.tag": ("TagEntityType",),
    "miles_core.models.model.catalog": ("ModelCapabilityType", "ModelPublishStatus", "ModelVendor"),
    "miles_core.models.model.generative_job": ("GenerativeJobStatus",),
    "miles_core.models.platform.tenant": ("TenantStatus",),
    "miles_core.models.risk": ("RiskSeverity",),
    "miles_core.models.task.task_record": ("TaskStatus",),
    "miles_exec.mcp.constants": ("McpTransport",),
    "miles_exec.mcp.spec": ("NetworkMode",),
    "miles_portal.tenant.a2a.models": ("A2aInvokePolicy", "A2aPeerStatus", "A2aPlanTrigger"),
    "miles_portal.tenant.hooks.models": ("HookScope", "HookTrigger", "HookType"),
    "miles_portal.tenant.mcp.models": ("McpStatus",),
    "miles_portal.tenant.tools.models": ("ToolType",),
}


def _iter_enum_classes() -> Iterator[tuple[str, type[enum.Enum]]]:
    """遍历清单内全部枚举类，产出 ``(限定名, 枚举类)``。"""
    for module_name, class_names in _UP042_ENUMS.items():
        module = importlib.import_module(module_name)
        for class_name in class_names:
            yield f"{module_name}.{class_name}", getattr(module, class_name)


def _iter_members() -> Iterator[tuple[str, enum.Enum]]:
    """遍历清单内全部枚举成员，产出 ``(限定名, 成员)``。"""
    for enum_label, enum_cls in _iter_enum_classes():
        for member in enum_cls:
            yield f"{enum_label}.{member.name}", member


def test_migration_checklist_is_complete() -> None:
    """冻结清单本身不得漂移：22 模块 / 32 枚举 / 134 成员。"""
    assert len(_UP042_ENUMS) == 22
    assert sum(len(names) for names in _UP042_ENUMS.values()) == 32
    assert sum(1 for _ in _iter_members()) == 134


def test_all_migrated_enums_are_strenum() -> None:
    """32 个枚举必须全部是 ``StrEnum`` 子类（迁移目标）。"""
    for enum_label, enum_cls in _iter_enum_classes():
        assert issubclass(enum_cls, enum.StrEnum), f"{enum_label} 尚未迁移为 StrEnum"


def test_str_family_returns_member_value() -> None:
    """``str()`` / f-string / ``format()`` 返回成员值（本次迁移唯一可见的行为变化）。

    这里用内建 ``format(member)`` 而非 ``"{}".format(member)``：两者走同一条
    ``__format__`` 路径，但后者会被 ruff 的 UP032 要求改写为 f-string，从而与
    本测试「刻意覆盖 format 路径」的目的冲突。
    """
    for label, member in _iter_members():
        assert str(member) == member.value, f"{label}: str() 应为成员值"
        assert f"{member}" == member.value, f"{label}: f-string 应为成员值"
        assert format(member) == member.value, f"{label}: format() 应为成员值"
        assert f"{member:>20}" == member.value.rjust(20), f"{label}: 格式说明符应作用于成员值"


def test_sqlalchemy_enum_columns_keep_same_values() -> None:
    """真实 ORM 枚举列：``.enums``（DDL 值列表）、绑定值与读回不因迁移改变。

    套件用 ``AsyncMock`` 顶替 DB、不跑真库，故这里直接对列的 SAEnum 做断言，
    不依赖数据库连接。

    期望值一律**写字面量**，不从 ``enum_cls`` 派生：若写成
    ``[m.value for m in enum_cls]``，断言两侧同源——有人把 ``AgentStatus.ENABLED``
    的值改掉时两边同步变化、测试照旧全绿，而 DDL 值列表与落库字符串正是本次迁移
    全部安全依据所在。字面量才能让这条护栏真的会失败。
    """
    from miles_core.models.agent.agent import Agent, AgentStatus, AgentType
    from miles_portal.tenant.tools.models import Tool, ToolType

    cases: tuple[tuple[Any, str, type[enum.Enum], list[str], str], ...] = (
        (Agent, "status", AgentStatus, ["enabled", "disabled"], "enabled"),
        (Agent, "agent_type", AgentType, ["custom", "a2a"], "custom"),
        (Tool, "tool_type", ToolType, ["http", "script"], "http"),
    )
    dialect = postgresql.dialect()
    for model, column_name, enum_cls, expected_enums, sample in cases:
        col_type = model.__table__.c[column_name].type
        assert isinstance(col_type, SAEnum), f"{model.__name__}.{column_name} 应为 SAEnum"
        assert col_type.enums == expected_enums, f"{model.__name__}.{column_name} 的 DDL 值列表已变"
        member = enum_cls(sample)
        assert col_type.bind_processor(dialect)(member) == sample, f"{model.__name__}.{column_name} 绑定值已变"
        # 读回：落库字符串 → 枚举成员（result_processor 是 ORM 读回用到的转换器）
        read_back = col_type.result_processor(dialect, None)
        assert read_back is not None, f"{model.__name__}.{column_name} 无读回转换器"
        assert read_back(sample) is member, f"{model.__name__}.{column_name} 读回未还原为枚举成员"
