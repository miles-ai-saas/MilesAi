"""DashScope 异步任务通用逻辑（万相生图/生视频共用）。"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.common.exceptions import AppError, BadRequestError
from app.integrations.http_constants import HTTP_DEFAULT_TIMEOUT_SEC
from app.models.model import ModelConfig
from app.models.model_catalog import DEFAULT_API_BASES, ModelVendor


def dashscope_api_base(model: ModelConfig) -> str:
    """万相 API 根路径（可被 model.api_base 覆盖）。"""
    return (
        model.api_base
        or DEFAULT_API_BASES.get(ModelVendor.QWEN.value)
        or "https://dashscope.aliyuncs.com/api/v1"
    ).rstrip("/")


def dashscope_headers(api_key: str, *, async_enable: bool = True) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if async_enable:
        headers["X-DashScope-Async"] = "enable"
    return headers


async def poll_dashscope_task(
    api_key: str,
    api_base: str,
    task_id: str,
    *,
    poll_interval_sec: float = 3.0,
    poll_timeout_sec: float = 600.0,
    success_label: str = "任务",
) -> dict[str, Any]:
    """轮询 ``GET /tasks/{task_id}`` 直至 SUCCEEDED / FAILED。"""
    task_url = f"{api_base}/tasks/{task_id}"
    max_attempts = max(1, int(poll_timeout_sec / poll_interval_sec))
    async with httpx.AsyncClient(timeout=HTTP_DEFAULT_TIMEOUT_SEC) as client:
        for _ in range(max_attempts):
            await asyncio.sleep(poll_interval_sec)
            poll = await client.get(
                task_url,
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if poll.status_code >= 400:
                raise AppError(f"万相{success_label}查询失败: {poll.text[:300]}", status_code=502)
            data = poll.json()
            output = data.get("output") or data
            status = output.get("task_status") or data.get("task_status")
            if status == "SUCCEEDED":
                return data
            if status in ("FAILED", "CANCELED"):
                msg = output.get("message") or data.get("message") or status
                raise AppError(f"万相{success_label}失败: {msg}", status_code=502)
    raise AppError(f"万相{success_label}超时（>{int(poll_timeout_sec)}s）", status_code=504)


def extract_video_url(payload: dict[str, Any]) -> str:
    """从轮询完成后的 task 响应解析 ``output.video_url``。"""
    output = payload.get("output") or payload
    url = output.get("video_url") or payload.get("video_url")
    if not url:
        raise AppError("万相未返回 video_url", status_code=502)
    return str(url)


async def download_remote_bytes(url: str) -> bytes:
    """下载万相返回的临时 video_url（厂商侧短期有效，落库后走 attachment content API）。"""
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.get(url)
    if resp.status_code >= 400:
        raise AppError("下载生成文件失败", status_code=502)
    return resp.content


def require_api_key(model: ModelConfig) -> str:
    key = model.api_key_encrypted
    if not key:
        raise BadRequestError(f"模型「{model.name}」未配置 API Key")
    return key
