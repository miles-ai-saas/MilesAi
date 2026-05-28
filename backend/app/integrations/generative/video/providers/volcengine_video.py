"""
豆包 / 火山方舟 Seedance 生视频（httpx，无 SDK）。

``ModelConfig`` 使用库内已配置的 ``api_base``、``model_name``（或推理接入点 ID）、``api_key``；
可选 ``extra``：``video_resolution``、``video_duration``、``video_ratio``、``poll_*``、
``video_submit_path`` / ``video_poll_path``（非默认路径时覆盖）。
"""

from __future__ import annotations

from typing import Any

import httpx

from app.common.exceptions import AppError, BadRequestError
from app.integrations.generative.constants import (
    DEFAULT_POLL_INTERVAL_SEC,
    DEFAULT_POLL_TIMEOUT_SEC,
    DEFAULT_VIDEO_DURATION_SEC,
    DEFAULT_VIDEO_RESOLUTION,
    EXTRA_GENERATE_AUDIO,
    EXTRA_VIDEO_DURATION,
    EXTRA_VIDEO_RATIO,
    EXTRA_VIDEO_RESOLUTION,
    EXTRA_WATERMARK,
)
from app.integrations.generative.dashscope_client import download_remote_bytes
from app.integrations.generative.volcengine_client import (
    extract_volcengine_video_url,
    normalize_volcengine_resolution,
    poll_volcengine_video_task,
    require_volcengine_api_key,
    volcengine_headers,
    volcengine_submit_url,
)
from app.integrations.http_constants import HTTP_DEFAULT_TIMEOUT_SEC
from app.models.model import ModelConfig


def _build_content(
    prompt: str,
    first_frame_data_url: str | None,
    last_frame_data_url: str | None = None,
) -> list[dict[str, Any]]:
    """方舟 content：文生视频；首帧 i2v；首尾帧需 role=first_frame/last_frame。"""
    if last_frame_data_url and not first_frame_data_url:
        raise BadRequestError("首尾帧生视频需同时提供首帧与尾帧图片")

    items: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    if first_frame_data_url:
        first_item: dict[str, Any] = {
            "type": "image_url",
            "image_url": {"url": first_frame_data_url},
        }
        if last_frame_data_url:
            first_item["role"] = "first_frame"
        items.append(first_item)
    if last_frame_data_url:
        items.append(
            {
                "type": "image_url",
                "image_url": {"url": last_frame_data_url},
                "role": "last_frame",
            }
        )
    return items


def _build_request_body(
    model: ModelConfig,
    *,
    prompt: str,
    duration: int,
    resolution: str,
    ratio: str,
    first_frame_data_url: str | None,
    last_frame_data_url: str | None = None,
) -> dict[str, Any]:
    extra = model.extra or {}
    ep_model = (model.model_name or "").strip()
    if not ep_model:
        raise BadRequestError(f"模型「{model.name}」未配置 model_name（方舟模型/接入点 ID）")

    body: dict[str, Any] = {
        "model": ep_model,
        "content": _build_content(prompt, first_frame_data_url, last_frame_data_url),
        "duration": int(extra.get(EXTRA_VIDEO_DURATION) or duration or DEFAULT_VIDEO_DURATION_SEC),
        "resolution": normalize_volcengine_resolution(resolution or str(extra.get(EXTRA_VIDEO_RESOLUTION) or DEFAULT_VIDEO_RESOLUTION)),
        "ratio": ratio,
        "watermark": bool(extra.get(EXTRA_WATERMARK, False)),
    }
    if extra.get(EXTRA_GENERATE_AUDIO):
        body["generate_audio"] = True
    return body


async def generate_volcengine_video(
    model: ModelConfig,
    *,
    prompt: str,
    duration: int = 5,
    resolution: str | None = None,
    first_frame_data_url: str | None = None,
    last_frame_data_url: str | None = None,
    progress: object | None = None,
) -> bytes:
    """提交方舟视频任务并轮询，返回 mp4 字节。"""
    api_key = require_volcengine_api_key(model)
    extra = model.extra or {}
    poll_interval = float(extra.get("poll_interval_sec") or DEFAULT_POLL_INTERVAL_SEC)
    poll_timeout = float(extra.get("poll_timeout_sec") or DEFAULT_POLL_TIMEOUT_SEC)

    ratio = str(extra.get(EXTRA_VIDEO_RATIO) or "").strip()
    if not ratio:
        ratio = "adaptive" if (first_frame_data_url or last_frame_data_url) else "16:9"

    body = _build_request_body(
        model,
        prompt=prompt,
        duration=duration,
        resolution=resolution or DEFAULT_VIDEO_RESOLUTION,
        ratio=ratio,
        first_frame_data_url=first_frame_data_url,
        last_frame_data_url=last_frame_data_url,
    )
    submit_url = volcengine_submit_url(model)

    async with httpx.AsyncClient(timeout=HTTP_DEFAULT_TIMEOUT_SEC) as client:
        submit = await client.post(submit_url, headers=volcengine_headers(api_key), json=body)
    if submit.status_code >= 400:
        raise AppError(f"豆包生视频提交失败 ({submit.status_code}): {submit.text[:500]}", status_code=502)

    payload = submit.json()
    task_id = payload.get("id") or payload.get("task_id")
    if not task_id:
        raise AppError("豆包生视频未返回任务 id", status_code=502)

    on_poll = progress.update if progress and hasattr(progress, "update") else None
    should_cancel = progress.is_cancelled if progress and hasattr(progress, "is_cancelled") else None

    final = await poll_volcengine_video_task(
        model,
        api_key,
        str(task_id),
        poll_interval_sec=poll_interval,
        poll_timeout_sec=poll_timeout,
        on_poll=on_poll,
        should_cancel=should_cancel,
    )
    if on_poll:
        await on_poll(92, "下载视频中…")
    video_url = extract_volcengine_video_url(final)
    return await download_remote_bytes(video_url)
