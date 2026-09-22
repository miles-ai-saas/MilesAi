"""OpenAI 兼容 Images API（/v1/images/generations）。"""

from __future__ import annotations

from typing import Any

import httpx

from miles_common.exceptions import AppError, BadRequestError
from miles_core.models.model import ModelConfig
from miles_core.models.model.catalog import DEFAULT_API_BASES
from miles_integrations.generative.constants import DEFAULT_IMAGE_SIZE
from miles_integrations.generative.image.providers._decoding import decode_b64_image
from miles_integrations.http_constants import HTTP_DEFAULT_TIMEOUT_SEC


async def generate_openai_images(
    model: ModelConfig,
    *,
    prompt: str,
    size: str,
    n: int = 1,
    reference_image_data_url: str | None = None,
) -> list[bytes]:
    """返回 PNG/JPEG 字节列表。"""
    api_key = model.api_key_encrypted
    if not api_key:
        raise BadRequestError(f"模型「{model.name}」未配置 API Key")

    api_base = (model.api_base or DEFAULT_API_BASES.get(model.vendor) or "").rstrip("/")
    if not api_base:
        api_base = "https://api.openai.com/v1"
    url = f"{api_base}/images/generations"

    if reference_image_data_url:
        raise BadRequestError(f"模型「{model.name}」当前 invoke 不支持图生图，请改用豆包 SeedEdit 或通义万相")

    body: dict[str, Any] = {
        "model": model.model_name or "dall-e-3",
        "prompt": prompt,
        "n": min(max(n, 1), 4),
        "size": size or DEFAULT_IMAGE_SIZE,
        "response_format": "b64_json",
    }

    async with httpx.AsyncClient(timeout=HTTP_DEFAULT_TIMEOUT_SEC) as client:
        resp = await client.post(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            json=body,
        )
    if resp.status_code >= 400:
        raise AppError(f"生图 API 失败 ({resp.status_code}): {resp.text[:500]}", status_code=502)

    payload = resp.json()
    items = payload.get("data") or []
    if not items:
        raise AppError("生图 API 返回为空", status_code=502)

    out: list[bytes] = []
    for item in items:
        b64 = item.get("b64_json")
        if b64:
            blob = decode_b64_image(b64)
            if blob is not None:
                out.append(blob)
            continue
        img_url = item.get("url")
        if img_url:
            async with httpx.AsyncClient(timeout=HTTP_DEFAULT_TIMEOUT_SEC) as client:
                img_resp = await client.get(img_url)
            if img_resp.status_code >= 400:
                raise AppError("下载生成图片失败", status_code=502)
            out.append(img_resp.content)
    if not out:
        raise AppError("生图 API 未返回可用图片数据", status_code=502)
    return out
