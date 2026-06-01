"""模板市场分类与客户类型标签校验。"""

from __future__ import annotations

from app.biz.schemas.meta import EnumItem
from app.biz.services.meta import INDUSTRIES
from app.common.exceptions import BadRequestError

# 场景主分类（广场浏览）
TEMPLATE_PACK_CATEGORIES = [
    EnumItem("exhibition", "展陈展馆"),
    EnumItem("event", "活动策划"),
    EnumItem("brand", "品牌视觉"),
    EnumItem("video", "影视制作"),
    EnumItem("training", "会务培训"),
    EnumItem("signage", "标识导视"),
    EnumItem("cultural", "文创产品"),
    EnumItem("print", "宣传印刷"),
    EnumItem("general", "通用流程"),
]

SERVICE_LINE_DEFAULT_CATEGORY: dict[str, str] = {
    "brand_identity": "brand",
    "video_production": "video",
    "exhibition": "exhibition",
    "event": "event",
    "training": "training",
    "signage": "signage",
    "cultural_product": "cultural",
    "print": "print",
}

_CATEGORY_KEYS = {item.key for item in TEMPLATE_PACK_CATEGORIES}
_INDUSTRY_KEYS = {item.key for item in INDUSTRIES}


def default_category_for_service_line(service_line: str) -> str:
    return SERVICE_LINE_DEFAULT_CATEGORY.get(service_line, "general")


def validate_category(category: str) -> str:
    key = (category or "").strip()
    if key not in _CATEGORY_KEYS:
        raise BadRequestError("无效模板场景分类")
    return key


def normalize_customer_type_tags(tags: list[str] | None) -> list[str]:
    if not tags:
        return []
    normalized: list[str] = []
    for raw in tags:
        key = (raw or "").strip()
        if not key:
            continue
        if key not in _INDUSTRY_KEYS:
            raise BadRequestError(f"无效客户类型标签: {key}")
        if key not in normalized:
            normalized.append(key)
    return normalized
