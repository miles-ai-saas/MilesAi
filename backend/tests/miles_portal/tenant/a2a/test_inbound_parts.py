"""A2A 入站 text/file/data parts 解析与落库接线。"""

from __future__ import annotations

import base64
from types import SimpleNamespace
from uuid import uuid4

import pytest

from miles_common.exceptions import BadRequestError
from miles_common.schemas.chat_io import ChatMediaIn
from miles_portal.tenant.a2a import inbound_parts as pure
from miles_portal.tenant.a2a.services import inbound_parts as svc
from miles_portal.tenant.attachments.schemas.attachment import AttachmentOut


def _png_b64() -> str:
    # 1x1 PNG
    raw = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )
    return base64.b64encode(raw).decode("ascii")


def test_parse_joins_text_and_data():
    params = {
        "message": {
            "parts": [
                {"kind": "text", "text": "看这张图"},
                {"kind": "data", "data": {"city": "上海"}},
            ]
        }
    }
    parsed = pure.parse_inbound_parts(params)
    assert parsed.texts == ["看这张图"]
    assert parsed.data_texts == ['{"city": "上海"}']
    assert pure.compose_inbound_query(parsed) == '看这张图\n[结构化数据]\n{"city": "上海"}'


def test_parse_file_bytes_image():
    params = {
        "message": {
            "parts": [
                {
                    "kind": "file",
                    "file": {
                        "name": "dot.png",
                        "mimeType": "image/png",
                        "bytes": _png_b64(),
                    },
                }
            ]
        }
    }
    parsed = pure.parse_inbound_parts(params)
    assert len(parsed.files) == 1
    assert pure.is_inbound_image(parsed.files[0])
    assert parsed.files[0].filename == "dot.png"


def test_parse_file_data_uri():
    params = {
        "message": {
            "parts": [
                {
                    "kind": "file",
                    "file": {
                        "name": "dot.png",
                        "uri": f"data:image/png;base64,{_png_b64()}",
                    },
                }
            ]
        }
    }
    parsed = pure.parse_inbound_parts(params)
    assert parsed.files[0].mime_type == "image/png"
    assert pure.is_inbound_image(parsed.files[0])


def test_parse_rejects_remote_http_uri():
    params = {
        "message": {
            "parts": [
                {
                    "kind": "file",
                    "file": {
                        "name": "x.png",
                        "mimeType": "image/png",
                        "uri": "https://example.com/x.png",
                    },
                }
            ]
        }
    }
    with pytest.raises(BadRequestError, match="data:"):
        pure.parse_inbound_parts(params)


def test_parse_rejects_empty_parts():
    with pytest.raises(BadRequestError, match="没有可用"):
        pure.parse_inbound_parts({"message": {"parts": []}})


def test_parse_accepts_legacy_type_discriminator():
    """文档常误写 type；与 kind 等价接受。"""
    parsed = pure.parse_inbound_parts(
        {"message": {"parts": [{"type": "text", "text": "hi"}]}}
    )
    assert parsed.texts == ["hi"]


@pytest.mark.asyncio
async def test_resolve_inbound_uploads_image_to_media(monkeypatch):  # noqa: ANN001
    att_id = uuid4()
    uploaded: list = []

    class _FakeAttachmentService:
        def __init__(self, _db, _ctx) -> None:  # noqa: ANN001
            pass

        async def upload(self, file, meta):  # noqa: ANN001
            uploaded.append((file.filename, file.headers.get("content-type"), meta.purpose))
            return AttachmentOut(
                id=att_id,
                tenant_id=uuid4(),
                uploaded_by=uuid4(),
                filename=file.filename or "x",
                mime_type="image/png",
                file_size=10,
                object_bucket="b",
                purpose=meta.purpose,
                resource_type=meta.resource_type,
                resource_id=meta.resource_id,
                created_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
            )

    monkeypatch.setattr(svc, "AttachmentService", _FakeAttachmentService)
    agent_id = uuid4()
    inbound = await svc.resolve_inbound_chat_input(
        SimpleNamespace(),
        SimpleNamespace(tenant_id=uuid4(), user_id=uuid4()),
        {
            "message": {
                "parts": [
                    {"kind": "text", "text": "描述一下"},
                    {
                        "kind": "file",
                        "file": {
                            "name": "dot.png",
                            "mimeType": "image/png",
                            "bytes": _png_b64(),
                        },
                    },
                ]
            }
        },
        agent_id=agent_id,
    )
    assert inbound.query == "描述一下"
    assert inbound.media == [ChatMediaIn(attachment_id=att_id)]
    assert uploaded[0][0] == "dot.png"
    assert uploaded[0][2] == svc.PURPOSE_A2A_INBOUND


@pytest.mark.asyncio
async def test_resolve_non_image_file_becomes_query_note(monkeypatch):  # noqa: ANN001
    att_id = uuid4()

    class _FakeAttachmentService:
        def __init__(self, _db, _ctx) -> None:  # noqa: ANN001
            pass

        async def upload(self, file, meta):  # noqa: ANN001
            return AttachmentOut(
                id=att_id,
                tenant_id=uuid4(),
                uploaded_by=uuid4(),
                filename=file.filename or "x",
                mime_type="application/pdf",
                file_size=10,
                object_bucket="b",
                purpose=meta.purpose,
                resource_type=meta.resource_type,
                resource_id=meta.resource_id,
                created_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
            )

    monkeypatch.setattr(svc, "AttachmentService", _FakeAttachmentService)
    pdf_bytes = base64.b64encode(b"%PDF-1.4 stub").decode("ascii")
    inbound = await svc.resolve_inbound_chat_input(
        SimpleNamespace(),
        SimpleNamespace(tenant_id=uuid4(), user_id=uuid4()),
        {
            "message": {
                "parts": [
                    {
                        "kind": "file",
                        "file": {
                            "name": "doc.pdf",
                            "mimeType": "application/pdf",
                            "bytes": pdf_bytes,
                        },
                    }
                ]
            }
        },
        agent_id=uuid4(),
    )
    assert inbound.media == []
    assert str(att_id) in inbound.query
    assert "doc.pdf" in inbound.query


@pytest.mark.asyncio
async def test_run_published_agent_chat_forwards_media(monkeypatch):  # noqa: ANN001
    from miles_common.schemas.chat_io import ChatResponse
    from miles_portal.tenant.a2a.services import server as server_svc

    seen: dict = {}
    media = [ChatMediaIn(attachment_id=uuid4())]

    class _FakeAgentService:
        def __init__(self, _db, _ctx) -> None:  # noqa: ANN001
            pass

        async def chat(self, agent_id, body, *, on_delta=None):  # noqa: ANN001
            seen["body"] = body
            return ChatResponse(answer="ok")

    monkeypatch.setattr("miles_portal.tenant.agents.services.agent.AgentService", _FakeAgentService)
    await server_svc.run_published_agent_chat(
        SimpleNamespace(),
        SimpleNamespace(),
        uuid4(),
        "",
        media=media,
        conversation_id="ctx",
    )
    assert seen["body"].media == media
    assert seen["body"].query == ""
