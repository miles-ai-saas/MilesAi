"""跨模块枚举展示元数据（value + label + hint）。

各业务域 ``tenant/*/meta.py`` 维护文案，经 ``GET /{module}/meta`` 下发；
前端统一用 ``EnumOption`` + ``optionLabel()`` 渲染，避免前后端枚举漂移。
"""

from __future__ import annotations

from enum import Enum
from typing import Iterable

from pydantic import BaseModel, Field

META_SCHEMA_VERSION = "1"


class EnumOption(BaseModel):
    """单条枚举选项；``implemented`` 仅钩子触发器等需标注接线状态的域使用。"""

    value: str = Field(description="枚举值（API/存储用）")
    label: str = Field(description="展示标签")
    hint: str | None = Field(default=None, description="补充说明")
    implemented: bool | None = Field(
        default=None,
        description="是否已在运行时接线（部分域使用）",
    )


def enum_options(
    enum_cls: type[Enum],
    labels: dict[str, tuple[str, str | None]],
    *,
    implemented: dict[str, bool] | None = None,
) -> list[EnumOption]:
    """从枚举与标签表生成选项列表（顺序与枚举定义一致）。"""
    out: list[EnumOption] = []
    for member in enum_cls:
        key = member.value
        label, hint = labels.get(key, (key, None))
        out.append(
            EnumOption(
                value=key,
                label=label,
                hint=hint,
                implemented=implemented.get(key) if implemented else None,
            )
        )
    return out


def literal_options(pairs: Iterable[tuple[str, str, str | None]]) -> list[EnumOption]:
    """非枚举常量列表：[(value, label, hint?), ...]。"""
    return [EnumOption(value=v, label=lb, hint=h) for v, lb, h in pairs]
