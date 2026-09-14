"""火山方舟 Images API（豆包 Seedream 文生图 / SeedEdit 图生图）。"""

from __future__ import annotations

import base64
from typing import Any

import httpx

from miles_ai.integrations.generative.constants import DEFAULT_IMAGE_SIZE
from miles_ai.integrations.generative.volcengine_client import (
    require_volcengine_api_key,
    volcengine_api_base,
    volcengine_headers,
)
from miles_ai.integrations.http_constants import HTTP_DEFAULT_TIMEOUT_SEC
from miles_common.exceptions import AppError, BadRequestError
from miles_core.models.model import ModelConfig


def _volcengine_image_size(size: str | None, *, has_reference: bool) -> str:
    """豆包生图尺寸：图生图常用 adaptive；文生图映射为 2K 等。"""
    raw = (size or DEFAULT_IMAGE_SIZE).strip()
    if has_reference and raw.lower() in ("1024x1024", "1280x720", "720x1280"):
        return "adaptive"
    if "x" in raw.lower():
        return "2K"
    return raw or "2K"


async def _decode_image_items(items: list[dict], client: httpx.AsyncClient) -> list[bytes]:
    """从响应 data 数组中解码 b64_json / url 为 bytes。"""
    out: list[bytes] = []
    for item in items:
        b64 = item.get("b64_json")
        if b64:
            out.append(base64.standard_b64decode(b64))
            continue
        img_url = item.get("url")
        if img_url:
            img_resp = await client.get(img_url)
            if img_resp.status_code < 400:
                out.append(img_resp.content)
    return out


async def generate_volcengine_image(
    model: ModelConfig,
    *,
    prompt: str,
    size: str,
    n: int = 1,
    reference_image_data_url: str | None = None,
) -> list[bytes]:
    """``/v1/images/generations``。

    n=1 时单次调用。n>1 时多次调用（每次 n=1），确保精确控制数量。
    Seedream 的 ``sequential_image_generation`` 为 auto 模式，模型会自主决定张数，
    对单场景 prompt 不可靠，因此不走组图模式。
    """
    import logging

    _log = logging.getLogger(__name__)
    api_key = require_volcengine_api_key(model)
    url = f"{volcengine_api_base(model)}/images/generations"
    model_name = model.model_name or "doubao-seedream-4-0-250828"

    is_seededit = "seededit" in model_name.lower() or "-i2i" in model_name.lower()
    if is_seededit and not reference_image_data_url:
        raise BadRequestError(f"模型「{model.name}」为图生图，需提供参考图 attachment")

    n = min(max(n, 1), 4)

    async with httpx.AsyncClient(timeout=HTTP_DEFAULT_TIMEOUT_SEC) as client:
        req_headers = volcengine_headers(api_key)
        out: list[bytes] = []

        for call_idx in range(n):
            body: dict[str, Any] = {
                "model": model_name,
                "prompt": prompt,
                "size": _volcengine_image_size(size, has_reference=bool(reference_image_data_url)),
                "n": 1,
                "response_format": "b64_json",
                "watermark": False,
            }
            if reference_image_data_url:
                body["image"] = reference_image_data_url

            # 只记可安全观察的请求特征：Authorization 是凭据，body 里的 image 是
            # 整段 base64 参考图（可达数 MB），二者都不得进日志。
            _log.info(
                "豆包生图请求（%d/%d）→ POST %s model=%s size=%s has_reference=%s",
                call_idx + 1,
                n,
                url,
                model_name,
                body["size"],
                bool(reference_image_data_url),
            )
            resp = await client.post(url, headers=req_headers, json=body)
            if resp.status_code >= 400:
                _log.warning("豆包生图失败 (%s): %s", resp.status_code, resp.text[:1000])
                if call_idx == 0:
                    raise AppError(f"豆包生图失败 ({resp.status_code}): {resp.text[:500]}", status_code=502)
                continue

            payload = resp.json()
            items = payload.get("data") or []
            _log.info("豆包生图响应（%d/%d）→ data 条目数=%d", call_idx + 1, n, len(items))
            if not items:
                _log.warning("豆包生图返回 data 为空（%d/%d）", call_idx + 1, n)
                continue

            blobs = await _decode_image_items(items, client)
            out.extend(blobs)

        _log.info("豆包生图完成 → 请求 n=%d, 解码成功=%d", n, len(out))
        if not out:
            raise AppError("豆包生图未返回可用图片数据", status_code=502)
        return out
