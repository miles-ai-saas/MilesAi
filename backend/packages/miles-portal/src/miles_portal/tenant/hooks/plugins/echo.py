"""示例 Python 钩子：原样继续执行。"""

from __future__ import annotations

from typing import Any


async def handle(envelope: dict[str, Any]) -> dict[str, Any]:
    """接收 Event v1 envelope，返回钩子动作 JSON。"""
    return {"action": "continue"}
