"""项目业务动态 schemas。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BizProjectActivityItem:
    id: str
    action: str
    label: str
    username: str | None = None
    created_at: str = ""
    detail: dict = field(default_factory=dict)
