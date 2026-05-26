"""钩子执行结果。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class HookRunResult:
    """单次 run() 的汇总：各钩子结果 + 可能被 modify 后的 payload。"""

    results: list[dict] = field(default_factory=list)
    payload: dict = field(default_factory=dict)
