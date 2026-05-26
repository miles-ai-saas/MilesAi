"""万相 2.x 文生视频 / 首帧图生视频（DashScope HTTP，无需 SDK）。"""

from __future__ import annotations

from typing import Any

import httpx

from app.common.exceptions import AppError
from app.integrations.generative.constants import (
    DEFAULT_POLL_INTERVAL_SEC,
    DEFAULT_POLL_TIMEOUT_SEC,
    DEFAULT_VIDEO_DURATION_SEC,
    DEFAULT_VIDEO_RESOLUTION,
)
from app.integrations.generative.dashscope_client import (
    dashscope_api_base,
    dashscope_headers,
    download_remote_bytes,
    extract_video_url,
    poll_dashscope_task,
    require_api_key,
)
from app.integrations.http_constants import HTTP_DEFAULT_TIMEOUT_SEC
from app.models.model import ModelConfig


def _video_parameters(model: ModelConfig, *, duration: int, resolution: str) -> dict[str, Any]:
    extra = model.extra or {}
    return {
        "resolution": resolution or str(extra.get("video_resolution") or DEFAULT_VIDEO_RESOLUTION),
        "duration": int(extra.get("video_duration") or duration or DEFAULT_VIDEO_DURATION_SEC),
        "prompt_extend": True,
        "watermark": False,
    }


async def generate_dashscope_video(
    model: ModelConfig,
    *,
    prompt: str,
    duration: int = 5,
    resolution: str | None = None,
    first_frame_data_url: str | None = None,
) -> bytes:
    """
    提交万相 video-synthesis 任务并轮询，返回 mp4 字节。

    ``first_frame_data_url``：图生视频首帧（data URL 或公网 URL）；纯文生视频传 None。
    """
    api_key = require_api_key(model)
    api_base = dashscope_api_base(model)
    url = f"{api_base}/services/aigc/video-generation/video-synthesis"

    wan_model = model.model_name or "wan2.1-t2v-plus"
    if first_frame_data_url and "i2v" not in wan_model and "t2v" in wan_model:
        wan_model = wan_model.replace("t2v", "i2v", 1)

    input_body: dict[str, Any] = {"prompt": prompt}
    if first_frame_data_url:
        input_body["media"] = [{"type": "first_frame", "url": first_frame_data_url}]

    body = {
        "model": wan_model,
        "input": input_body,
        "parameters": _video_parameters(
            model, duration=duration, resolution=resolution or DEFAULT_VIDEO_RESOLUTION
        ),
    }

    extra = model.extra or {}
    poll_interval = float(extra.get("poll_interval_sec") or DEFAULT_POLL_INTERVAL_SEC)
    poll_timeout = float(extra.get("poll_timeout_sec") or DEFAULT_POLL_TIMEOUT_SEC)

    async with httpx.AsyncClient(timeout=HTTP_DEFAULT_TIMEOUT_SEC) as client:
        submit = await client.post(url, headers=dashscope_headers(api_key), json=body)
    if submit.status_code >= 400:
        raise AppError(f"万相生视频提交失败 ({submit.status_code}): {submit.text[:500]}", status_code=502)

    task = submit.json()
    output = task.get("output") or task
    task_id = output.get("task_id") or task.get("task_id")
    if not task_id:
        video_url = output.get("video_url")
        if video_url:
            return await download_remote_bytes(str(video_url))
        raise AppError("万相生视频未返回 task_id", status_code=502)

    final = await poll_dashscope_task(
        api_key,
        api_base,
        str(task_id),
        poll_interval_sec=poll_interval,
        poll_timeout_sec=poll_timeout,
        success_label="生视频",
    )
    video_url = extract_video_url(final)
    return await download_remote_bytes(video_url)
