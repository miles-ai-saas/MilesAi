"""火山方舟 Images API（豆包 Seedream 文生图 / SeedEdit 图生图）。"""

from __future__ import annotations

import base64
from typing import Any

import httpx

from app.common.exceptions import AppError, BadRequestError
from app.integrations.generative.constants import DEFAULT_IMAGE_SIZE
from app.integrations.generative.volcengine_client import (
    require_volcengine_api_key,
    volcengine_api_base,
    volcengine_headers,
)
from app.integrations.http_constants import HTTP_DEFAULT_TIMEOUT_SEC
from app.models.model import ModelConfig


def _volcengine_image_size(size: str | None, *, has_reference: bool) -> str:
    """豆包生图尺寸：图生图常用 adaptive；文生图映射为 2K 等。"""
    raw = (size or DEFAULT_IMAGE_SIZE).strip()
    if has_reference and raw.lower() in ("1024x1024", "1280x720", "720x1280"):
        return "adaptive"
    if "x" in raw.lower():
        return "2K"
    return raw or "2K"


async def generate_volcengine_image(
    model: ModelConfig,
    *,
    prompt: str,
    size: str,
    n: int = 1,
    reference_image_data_url: str | None = None,
) -> list[bytes]:
    """``/v1/images/generations``；有参考图时在 body 中传 ``image``（data URL 或 URL）。"""
    api_key = require_volcengine_api_key(model)
    url = f"{volcengine_api_base(model)}/images/generations"
    model_name = model.model_name or "doubao-seedream-4-0-250828"
    # seededit 图生图必须带参考图
    if "seededit" in model_name.lower() or "-i2i" in model_name.lower():
        if not reference_image_data_url:
            raise BadRequestError(f"模型「{model.name}」为图生图，需提供参考图 attachment")

    body: dict[str, Any] = {
        "model": model_name,
        "prompt": prompt,
        "size": _volcengine_image_size(size, has_reference=bool(reference_image_data_url)),
        "n": min(max(n, 1), 4),
        "response_format": "b64_json",
        "watermark": False,
    }
    if reference_image_data_url:
        body["image"] = reference_image_data_url

    async with httpx.AsyncClient(timeout=HTTP_DEFAULT_TIMEOUT_SEC) as client:
        resp = await client.post(url, headers=volcengine_headers(api_key), json=body)
    if resp.status_code >= 400:
        raise AppError(f"豆包生图失败 ({resp.status_code}): {resp.text[:500]}", status_code=502)

    payload = resp.json()
    items = payload.get("data") or []
    if not items:
        raise AppError("豆包生图返回为空", status_code=502)

    out: list[bytes] = []
    for item in items:
        b64 = item.get("b64_json")
        if b64:
            out.append(base64.standard_b64decode(b64))
            continue
        img_url = item.get("url")
        if img_url:
            async with httpx.AsyncClient(timeout=HTTP_DEFAULT_TIMEOUT_SEC) as client:
                img_resp = await client.get(img_url)
            if img_resp.status_code < 400:
                out.append(img_resp.content)
    if not out:
        raise AppError("豆包生图未返回可用图片数据", status_code=502)
    return out
