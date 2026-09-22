"""persist_generated_bytes：对象存储上传前释放 DB 事务。"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from miles_portal.tenant.generative.services import persist as persist_mod


class _TxnDb:
    def __init__(self) -> None:
        self.events: list[str] = []

    async def commit(self) -> None:
        self.events.append("commit")

    async def flush(self) -> None:
        self.events.append("flush")

    async def refresh(self, _obj: object) -> None:
        self.events.append("refresh")


def test_persist_commits_before_object_storage_upload():
    db = _TxnDb()
    ctx = SimpleNamespace(tenant_id=uuid4(), user_id=uuid4())
    att = SimpleNamespace(id=uuid4(), object_key="pending")
    storage = MagicMock()
    storage.default_bucket = "bucket"
    storage.storage.upload_bytes = MagicMock()

    repo = MagicMock()
    repo.create = AsyncMock(return_value=att)

    async def _run() -> None:
        with (
            patch.object(persist_mod, "assert_can_upload_bytes", AsyncMock()),
            patch.object(persist_mod, "AttachmentRepository", return_value=repo),
            patch.object(persist_mod, "resolve_object_storage_async", AsyncMock(return_value=storage)),
            patch.object(persist_mod, "build_attachment_object_key", return_value="t/a/f.png"),
            patch.object(persist_mod, "apply_storage_delta", AsyncMock()) as apply_delta,
            patch.object(persist_mod.asyncio, "to_thread", new_callable=AsyncMock) as to_thread,
        ):
            async def _to_thread(fn, *args, **kwargs):
                db.events.append("upload")
                return fn(*args, **kwargs)

            to_thread.side_effect = _to_thread
            out = await persist_mod.persist_generated_bytes(
                db,  # type: ignore[arg-type]
                ctx,  # type: ignore[arg-type]
                data=b"png",
                filename="f.png",
                mime_type="image/png",
            )
            assert out == att.id
            assert att.object_key == "t/a/f.png"
            apply_delta.assert_awaited()

    asyncio.run(_run())
    assert db.events.index("commit") < db.events.index("upload")
