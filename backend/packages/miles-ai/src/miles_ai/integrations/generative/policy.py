"""生图/生视频工具调用策略（确认门槛等）。"""

from __future__ import annotations

import re

from miles_ai.integrations.generative.constants import DEFAULT_IMAGE_SIZE, MAX_IMAGES_PER_REQUEST

_SIZE_RE = re.compile(r"^(\d+)\s*[xX×]\s*(\d+)$")

# 单边 ≥1280 或总像素 > 1024² 视为高分辨率（需二次确认）
_HIGH_RES_EDGE_PX = 1280
_HIGH_RES_PIXELS = 1024 * 1024
# 一次生成 ≥3 张亦需确认
_HIGH_RES_MIN_COUNT = 3


def parse_image_size(size: str | None) -> tuple[int, int] | None:
    """解析 ``宽x高`` 尺寸串（分隔符支持 x/X/×）；为空或无法解析时返回 ``None``。"""
    if not size:
        return None
    m = _SIZE_RE.match(str(size).strip())
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def is_high_resolution_image_size(size: str | None) -> bool:
    """是否为高分辨率尺寸（单边 ≥1280 或总像素 >1024²）。"""
    dims = parse_image_size(size)
    if not dims:
        return False
    w, h = dims
    if max(w, h) >= _HIGH_RES_EDGE_PX:
        return True
    return w * h > _HIGH_RES_PIXELS


def needs_image_tool_confirmation(params: dict) -> bool:
    """内置 ``generate_image`` 是否在默认无确认时仍要求用户确认。"""
    size = params.get("size")
    if not size:
        size = DEFAULT_IMAGE_SIZE
    n = params.get("n")
    try:
        count = int(n) if n is not None else 1
    except (TypeError, ValueError):
        count = 1
    count = min(max(count, 1), MAX_IMAGES_PER_REQUEST)
    if count >= _HIGH_RES_MIN_COUNT:
        return True
    return is_high_resolution_image_size(str(size) if size else None)


def image_tool_confirmation_message(params: dict) -> str:
    """按尺寸与张数生成生图二次确认文案（高分辨率 / 多张分别措辞）。"""
    size = str(params.get("size") or DEFAULT_IMAGE_SIZE)
    n = params.get("n")
    try:
        count = int(n) if n is not None else 1
    except (TypeError, ValueError):
        count = 1
    count = min(max(count, 1), MAX_IMAGES_PER_REQUEST)

    high_res = is_high_resolution_image_size(size)
    multi = count >= _HIGH_RES_MIN_COUNT

    if high_res and multi:
        return f"将生成 {count} 张高分辨率图片（{size}），资源消耗较大。确认后执行。"
    if high_res:
        return f"将生成高分辨率图片（{size}），资源消耗较大。确认后执行。"
    return f"将生成 {count} 张图片，消耗 {count}x 资源。确认后执行。"
