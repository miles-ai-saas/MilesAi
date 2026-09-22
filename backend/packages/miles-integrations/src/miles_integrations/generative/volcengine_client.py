"""火山方舟（豆包 Seedance）视频生成任务 HTTP 客户端。"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from miles_common.exceptions import AppError, BadRequestError
from miles_core.models.model import ModelConfig
from miles_core.models.model.catalog import DEFAULT_API_BASES, ModelVendor
from miles_integrations.generative.constants import (
    DEFAULT_POLL_INTERVAL_SEC,
    DEFAULT_POLL_TIMEOUT_SEC,
    EXTRA_VIDEO_POLL_PATH,
    EXTRA_VIDEO_SUBMIT_PATH,
)
from miles_integrations.http_constants import HTTP_DEFAULT_TIMEOUT_SEC

DEFAULT_VIDEO_SUBMIT_PATH = "/contents/generations/tasks"
DEFAULT_VIDEO_POLL_PATH = "/contents/generations/tasks/{task_id}"

_TERMINAL_FAIL = frozenset({"failed", "cancelled", "canceled", "expired"})


def volcengine_api_base(model: ModelConfig) -> str:
    """API 根路径（``model.api_base`` 优先，否则豆包默认方舟 v3）。"""
    return (model.api_base or DEFAULT_API_BASES.get(ModelVendor.DOUBAO.value) or "https://ark.cn-beijing.volces.com/api/v3").rstrip("/")


def volcengine_headers(api_key: str) -> dict[str, str]:
    """构造方舟 Bearer 鉴权请求头。"""
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def volcengine_submit_url(model: ModelConfig) -> str:
    """生成任务提交 URL（路径可被 ``model.extra`` 覆盖，自动补前导斜杠）。"""
    extra = model.extra or {}
    path = str(extra.get(EXTRA_VIDEO_SUBMIT_PATH) or DEFAULT_VIDEO_SUBMIT_PATH).strip()
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{volcengine_api_base(model)}{path}"


def volcengine_poll_url(model: ModelConfig, task_id: str) -> str:
    """生成任务轮询 URL（路径模板可被 ``model.extra`` 覆盖并填入 task_id）。"""
    extra = model.extra or {}
    template = str(extra.get(EXTRA_VIDEO_POLL_PATH) or DEFAULT_VIDEO_POLL_PATH).strip()
    path = template.format(task_id=task_id)
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{volcengine_api_base(model)}{path}"


def require_volcengine_api_key(model: ModelConfig) -> str:
    """取模型已配置的方舟 API Key；缺失时抛 ``BadRequestError``。"""
    key = model.api_key_encrypted
    if not key:
        raise BadRequestError(f"模型「{model.name}」未配置 API Key")
    return key


def normalize_volcengine_resolution(resolution: str) -> str:
    """万相常用 ``720P``，方舟要求 ``720p``。"""
    r = (resolution or "720p").strip()
    if r.upper().endswith("P") and r[-1] == "P":
        return r[:-1] + "p"
    return r.lower() if r.lower() in ("480p", "720p", "1080p") else r


OnPollTick = Callable[[int, str], Awaitable[None]]
ShouldCancel = Callable[[], Awaitable[bool]]


async def poll_volcengine_video_task(
    model: ModelConfig,
    api_key: str,
    task_id: str,
    *,
    poll_interval_sec: float = DEFAULT_POLL_INTERVAL_SEC,
    poll_timeout_sec: float = DEFAULT_POLL_TIMEOUT_SEC,
    on_poll: OnPollTick | None = None,
    should_cancel: ShouldCancel | None = None,
) -> dict[str, Any]:
    """轮询 ``GET .../tasks/{id}`` 直至 succeeded 或失败/超时。"""
    url = volcengine_poll_url(model, task_id)
    max_attempts = max(1, int(poll_timeout_sec / poll_interval_sec))
    async with httpx.AsyncClient(timeout=HTTP_DEFAULT_TIMEOUT_SEC) as client:
        for attempt in range(max_attempts):
            if should_cancel and await should_cancel():
                from miles_integrations.generative.jobs.errors import GenerativeJobCancelled

                raise GenerativeJobCancelled()
            if on_poll:
                pct = min(90, 10 + int((attempt / max_attempts) * 80))
                await on_poll(pct, "豆包生视频生成中…")
            await asyncio.sleep(poll_interval_sec)
            poll = await client.get(url, headers=volcengine_headers(api_key))
            if poll.status_code >= 400:
                raise AppError(f"豆包生视频查询失败 ({poll.status_code}): {poll.text[:300]}", status_code=502)
            data = poll.json()
            status = str(data.get("status") or "").lower()
            if status == "succeeded":
                return data
            if status in _TERMINAL_FAIL:
                err = data.get("error") or data.get("message") or status
                raise AppError(f"豆包生视频失败: {err}", status_code=502)
    raise AppError(f"豆包生视频超时（>{int(poll_timeout_sec)}s）", status_code=504)


def extract_volcengine_video_url(payload: dict[str, Any]) -> str:
    """从任务响应解析 ``content.video_url``（回退顶层 ``video_url``）；缺失时抛 ``AppError``（502）。"""
    content = payload.get("content") or {}
    url = content.get("video_url") if isinstance(content, dict) else None
    if not url:
        url = payload.get("video_url")
    if not url:
        raise AppError("豆包生视频未返回 video_url", status_code=502)
    return str(url)
