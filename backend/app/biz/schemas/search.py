"""业务中心全局搜索 schemas。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BizSearchHit:
    kind: str  # client | project | opportunity | contract
    id: str
    title: str
    subtitle: str = ""


@dataclass
class BizSearchOut:
    query: str
    items: list[BizSearchHit] = field(default_factory=list)
