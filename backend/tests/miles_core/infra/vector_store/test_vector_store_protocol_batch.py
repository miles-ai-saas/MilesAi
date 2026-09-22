"""VectorStore 协议应声明 upsert_chunks。"""

from __future__ import annotations

import typing

from miles_core.infra.vector_store.base import VectorStore


def _protocol_declares(name: str) -> bool:
    attrs = getattr(VectorStore, "__protocol_attrs__", None)
    if attrs is not None and name in attrs:
        return True
    if name in VectorStore.__dict__:
        return True
    try:
        return name in typing.get_type_hints(VectorStore)
    except (NameError, TypeError, AttributeError):
        return False


def test_protocol_requires_upsert_chunks():
    assert _protocol_declares("upsert_chunks")
