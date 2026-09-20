"""生成任务订阅循环：Redis Pub/Sub 推送 + 兜底终查 + Redis 不可用时回退 DB 轮询。

平台 SSE（``GenerativeJobService.stream_job_events``）与 A2A ``tasks/resubscribe``
共用本模块。两者只在「怎么重新取数」「多久算超时」「空闲要不要产刻度」上不同，故把这些
作为注入项；循环本身只吐 ``GenerativeJob`` 快照，与 SSE、JSON、A2A 全无关。

首个产出契约：**必是 ``reload()`` 的快照**。空闲刻度只会出现在订阅建立**之后**。
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from uuid import UUID

from miles_common.redis_keys import RedisKeys
from miles_core.logging import get_logger
from miles_core.models.model.generative_job import GenerativeJob

logger = get_logger(__name__)


async def watch_generative_job(
    *,
    job_id: UUID,
    tenant_id: UUID,
    reload: Callable[[], Awaitable[GenerativeJob]],
    is_terminal: Callable[[GenerativeJob], bool],
    max_seconds: float,
    poll_interval: float = 1.0,
    emit_ticks: bool = False,
) -> AsyncIterator[GenerativeJob | None]:
    """订阅任务更新直到终态或超时。

    ``poll_interval`` 同时是 ``get_message`` 的阻塞上限、DB 降级路径的刷新间隔与空闲刻度的
    间隔。``emit_ticks=True`` 时，订阅建立后每次空等到点的轮询产出 ``None`` —— 消费方的
    ``async for`` 会一直挂在 ``__anext__`` 上，不给它一个空闲产出点，它就没有机会发保活帧
    （而 ``asyncio.wait_for(anext(...))`` 超时会取消那次 ``anext``、把生成器关掉，不能用）。
    """
    job = await reload()
    yield job
    if is_terminal(job):
        return

    pubsub = None
    channel = None
    try:
        # 必须在函数内 import：单测用 ``monkeypatch.setattr("miles_core.infra.redis.get_redis", …)``
        # 替换源模块属性，模块级 ``from … import get_redis`` 会把替换前的引用固化进来。
        from miles_core.infra.redis import get_redis

        redis = get_redis()
        channel = RedisKeys.generative_job_progress(str(tenant_id), str(job_id))
        pubsub = redis.pubsub()
        await pubsub.subscribe(channel)

        start = time.monotonic()
        terminal_yielded = False
        while time.monotonic() - start < max_seconds:
            # 必须显式传 timeout：redis-py 仅在 timeout 非 None 时阻塞等待、超时返回 None；
            # 省略时默认 0.0 为非阻塞，本循环会空转打满 CPU 直到上限。
            msg = await pubsub.get_message(timeout=poll_interval)
            if msg and msg["type"] == "message":
                job = await reload()
                yield job
                if is_terminal(job):
                    terminal_yielded = True
                    break
            elif emit_ticks:
                yield None
        # 兜底：Pub/Sub 超时或消息丢失时，做一次最终查询避免对端永久等待
        if not terminal_yielded:
            job = await reload()
            if is_terminal(job):
                yield job
    except Exception as exc:
        # Redis 不可用时回退 DB 轮询。此处为宽泛捕获：若失败原因不是「Redis 不可用」
        # （消息序列化错误、下游 bug 等），debug 级在生产不可见、也无消息与堆栈，
        # 整条降级路径等于无据可查，故升为 warning 并带堆栈。
        logger.warning("Redis Pub/Sub 不可用，回退 DB 轮询 (job_id=%s): %s", job_id, exc, exc_info=True)
        idle_ticks = 0
        # 按 ticks 计数而非墙钟：单测把 ``asyncio.sleep`` 换成直通，墙钟上限会变成死循环。
        max_ticks = max(1, int(max_seconds / poll_interval))
        while idle_ticks < max_ticks:
            job = await reload()
            yield job
            if is_terminal(job):
                break
            idle_ticks += 1
            await asyncio.sleep(poll_interval)
    finally:
        if pubsub is not None and channel is not None:
            try:
                await pubsub.unsubscribe(channel)
            except Exception:
                # finally 中的清理动作，失败不应影响收尾，仅 debug 留痕。
                logger.debug("取消订阅 pubsub 失败: channel=%s", channel, exc_info=True)
