"""LangGraph Checkpointer：优先 Redis，不可用时回退内存。"""

from __future__ import annotations

import logging
import warnings
from contextlib import AsyncExitStack
from typing import Any

from langgraph.checkpoint.memory import MemorySaver

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# redisvl（langgraph-checkpoint-redis 依赖）在 asetup 时的已知告警，待上游改为 async API
warnings.filterwarnings(
    "ignore",
    message=r"get_async_redis_connection will become async",
    category=DeprecationWarning,
    module=r"redisvl\.redis\.connection",
)

_checkpointer: Any = None
_compiled_rag_graph: Any = None  # 进程内单例，随 checkpointer 后端初始化
_exit_stack: AsyncExitStack | None = None
_backend: str = "memory"


def _import_async_redis_saver():
    """langgraph-checkpoint-redis 为独立 PyPI 包，提供 langgraph.checkpoint.redis。"""
    try:
        from langgraph.checkpoint.redis import AsyncRedisSaver

        return AsyncRedisSaver
    except ImportError as exc:
        raise ImportError(
            "未安装 langgraph-checkpoint-redis。请执行: "
            "pip install -e \".[dev]\" 或 pip install langgraph-checkpoint-redis>=0.4"
        ) from exc


def get_checkpointer() -> Any:
    if _checkpointer is None:
        return MemorySaver()
    return _checkpointer


def get_compiled_rag_graph() -> Any:
    if _compiled_rag_graph is None:
        from app.integrations.langgraph.graphs.rag_qa import build_rag_qa_graph

        return build_rag_qa_graph().compile(checkpointer=MemorySaver())
    return _compiled_rag_graph


def checkpoint_backend() -> str:
    return _backend


async def init_langgraph_checkpointer() -> str:
    """应用启动时初始化；返回实际后端标识 redis | memory。"""
    global _checkpointer, _compiled_rag_graph, _exit_stack, _backend

    from app.integrations.langgraph.graphs.rag_qa import build_rag_qa_graph

    settings = get_settings()
    saver: Any = MemorySaver()
    backend = "memory"

    if settings.langgraph_redis_checkpoint:
        try:
            AsyncRedisSaver = _import_async_redis_saver()
            from app.utils.health_checks import check_redis

            if await check_redis():
                stack = AsyncExitStack()
                saver = await stack.enter_async_context(
                    AsyncRedisSaver.from_conn_string(settings.langgraph_redis_url)
                )
                await saver.asetup()
                _exit_stack = stack
                backend = "redis"
                logger.info("LangGraph checkpointer: Redis (%s)", settings.langgraph_redis_url)
            else:
                logger.warning("LangGraph checkpointer: Redis 不可用，使用 MemorySaver")
        except ImportError as exc:
            logger.warning(
                "LangGraph checkpointer: %s；使用 MemorySaver。"
                "（安装后重启: pip install langgraph-checkpoint-redis）",
                exc,
            )
        except Exception as exc:
            logger.warning("LangGraph checkpointer: Redis 初始化失败 (%s)，使用 MemorySaver", exc)

    _checkpointer = saver
    _backend = backend
    _compiled_rag_graph = build_rag_qa_graph().compile(checkpointer=saver)
    return backend


async def shutdown_langgraph_checkpointer() -> None:
    global _checkpointer, _compiled_rag_graph, _exit_stack, _backend
    if _exit_stack is not None:
        await _exit_stack.aclose()
        _exit_stack = None
    _checkpointer = None
    _compiled_rag_graph = None
    _backend = "memory"
