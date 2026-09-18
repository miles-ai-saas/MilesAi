"""
检索结果按 ``VectorRef.vector_type``（text/image/audio/video）过滤。
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from miles_core.models.kb import VectorRef


def _allowed_types(media_types: list[str] | None) -> set[str] | None:
    """归一化 media_types 为小写集合；空则不过滤。"""
    if not media_types:
        return None
    cleaned = {t.strip().lower() for t in media_types if t and t.strip()}
    return cleaned or None


async def filter_hits_by_media_types_async(
    db: AsyncSession,
    hits: list[dict[str, Any]],
    media_types: list[str] | None,
) -> list[dict[str, Any]]:
    """异步过滤检索 hit，保留 vector_type 在 media_types 内的分片。"""
    allowed = _allowed_types(media_types)
    if not allowed or not hits:
        return hits

    chunk_ids: list[UUID] = []
    for h in hits:
        cid = h.get("chunk_id")
        if cid:
            try:
                chunk_ids.append(UUID(str(cid)))
            except ValueError:
                # 静默可接受：hit 的 chunk_id 非 UUID 即跳过该项，不影响其余命中。
                continue
    if not chunk_ids:
        return []

    rows = (await db.execute(select(VectorRef.chunk_id, VectorRef.vector_type).where(VectorRef.chunk_id.in_(chunk_ids)))).all()
    type_by_chunk = {str(row[0]): row[1] for row in rows}
    filtered: list[dict[str, Any]] = []
    for h in hits:
        cid = str(h.get("chunk_id") or "")
        vtype = (type_by_chunk.get(cid) or "text").lower()
        if vtype in allowed:
            merged = dict(h)
            merged["vector_type"] = vtype
            filtered.append(merged)
    return filtered


def filter_hits_by_media_types_sync(
    db: Session,
    hits: list[dict[str, Any]],
    media_types: list[str] | None,
) -> list[dict[str, Any]]:
    """同步版 media_types 过滤。"""
    allowed = _allowed_types(media_types)
    if not allowed or not hits:
        return hits

    chunk_ids: list[UUID] = []
    for h in hits:
        cid = h.get("chunk_id")
        if cid:
            try:
                chunk_ids.append(UUID(str(cid)))
            except ValueError:
                # 静默可接受：同上：chunk_id 非 UUID 即跳过该项，不影响其余命中。
                continue
    if not chunk_ids:
        return []

    rows = db.execute(select(VectorRef.chunk_id, VectorRef.vector_type).where(VectorRef.chunk_id.in_(chunk_ids))).all()
    type_by_chunk = {str(row[0]): row[1] for row in rows}
    filtered: list[dict[str, Any]] = []
    for h in hits:
        cid = str(h.get("chunk_id") or "")
        vtype = (type_by_chunk.get(cid) or "text").lower()
        if vtype in allowed:
            merged = dict(h)
            merged["vector_type"] = vtype
            filtered.append(merged)
    return filtered
