"""展示名 → slug（纯函数，供运营端与租户域复用）。"""

from __future__ import annotations

import hashlib
import re

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    """将展示名转为 slug；供运营端与标签模块复用。"""
    raw = name.strip().lower()
    s = _SLUG_RE.sub("-", raw).strip("-")
    if s:
        return s[:64]
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return f"c-{digest}"
