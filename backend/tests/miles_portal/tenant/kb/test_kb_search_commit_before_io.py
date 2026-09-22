"""工作台 KB search：embed / 向量后端前须 commit 释放 DB 会话。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from miles_core.tenant import TenantContext
from miles_portal.tenant.kb.schemas.kb import SearchRequest
from miles_portal.tenant.kb.services.kb.search import KnowledgeBaseSearchMixin


class _TxnDb:
    def __init__(self) -> None:
        self.events: list[str] = []

    async def commit(self) -> None:
        self.events.append("commit")


class _SearchSvc(KnowledgeBaseSearchMixin):
    def __init__(self, db: _TxnDb) -> None:
        self.db = db
        self.ctx = TenantContext(
            user_id=uuid4(),
            tenant_id=uuid4(),
            username="t",
            is_superuser=False,
            permissions=frozenset(),
        )
        self.doc_repo = SimpleNamespace()
        self.chunk_repo = SimpleNamespace()

    async def _get_kb_or_raise(self, kb_id):  # noqa: ANN001, ARG002
        return SimpleNamespace(
            id=kb_id,
            tenant_id=self.ctx.tenant_id,
            retrieval_mode="vector",
            rerank_model_config_id=None,
            rerank_candidate_k=50,
            visual_embedding_model_config_id=None,
        )


@pytest.mark.asyncio
async def test_search_commits_before_embed_and_vector():
    db = _TxnDb()
    svc = _SearchSvc(db)
    kb_id = uuid4()

    async def fake_embed(*_a, **_k):
        db.events.append("embed")
        return [0.1, 0.2]

    async def fake_search_chunks(*_a, **_k):
        db.events.append("vector")
        return []

    with (
        patch(
            "miles_portal.tenant.kb.services.kb.search.embed_query_for_kb",
            new_callable=AsyncMock,
            side_effect=fake_embed,
        ),
        patch(
            "miles_portal.tenant.kb.services.kb.search.search_kb_chunks",
            new_callable=AsyncMock,
            side_effect=fake_search_chunks,
        ),
        patch(
            "miles_portal.tenant.kb.services.kb.search.filter_hits_by_media_types_async",
            new_callable=AsyncMock,
            side_effect=lambda _db, hits, _mt: hits,
        ),
        patch(
            "miles_portal.tenant.kb.services.kb.search.write_kb_search_log",
            new_callable=AsyncMock,
        ),
    ):
        await svc.search(kb_id, SearchRequest(query="hello"))

    assert db.events == ["commit", "embed", "vector"]
