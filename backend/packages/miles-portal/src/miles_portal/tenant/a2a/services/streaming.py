"""A2A 流式响应的公共原语：SSE 帧、保活帧与耗时计时。

``message/stream``（``services/server.py``）与 ``tasks/resubscribe``
（``services/subscription.py``）都要拼 SSE 帧、发保活帧、算 ``durationMs``，故集中在此 ——
否则订阅模块只能 import 兄弟模块的私有符号，比搬过来更差。
"""

from __future__ import annotations

import json
import time

#: 保活帧：SSE 规范规定的注释行，客户端解析器一律忽略。
SSE_HEARTBEAT_FRAME = ": ping\n\n"

#: 等待增量的上限（秒）。超时就发一个 SSE 注释帧保活 —— 一次性路由（tool_agent / flow /
#: 子智能体）在末帧之前可能几分钟不产出任何字节，对端与中间代理会按 idle 超时把连接掐掉。
#: 只服务 ``message/stream``：``tasks/resubscribe`` 的保活节奏即它自己的轮询间隔（更密）。
SSE_HEARTBEAT_SECONDS = 15.0


def sse_frame(payload: dict) -> str:
    """单个 SSE 帧。``ensure_ascii=False`` 让中文按原样出网；JSON 转义保证单行。"""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def elapsed_ms(started: float) -> int:
    """自 ``started``（``time.monotonic()``）起的毫秒数。"""
    return int((time.monotonic() - started) * 1000)
