"""画布媒体节点测试：媒体字节经 RunContext.media_reader 注入，解析委托 rag.parse。"""

from uuid import uuid4

import pytest

from miles_ai.flow_runtime.nodes import media_nodes
from miles_ai.flow_runtime.types import RunContext
from miles_common.exceptions import BadRequestError
from miles_core.models.media.reader import AttachmentBytes


class FakeReader:
    """记录调用的假 MediaReader：image 供 read_image_bytes，attachment 供任意附件读取。"""

    def __init__(
        self,
        image: AttachmentBytes | None = None,
        attachment: AttachmentBytes | None = None,
    ) -> None:
        self._image = image
        self._attachment = attachment
        self.image_calls = 0
        self.attachment_calls = 0

    async def read_image_bytes(self, attachment_id):
        self.image_calls += 1
        assert self._image is not None
        return self._image

    async def read_attachment_bytes(self, attachment_id):
        self.attachment_calls += 1
        assert self._attachment is not None
        return self._attachment


@pytest.mark.asyncio
async def test_ocr_extract_reads_image_via_reader(monkeypatch):
    aid = uuid4()
    reader = FakeReader(image=AttachmentBytes(data=b"IMG", mime="image/png"))
    ctx = RunContext(tenant_id=str(uuid4()), media_reader=reader)

    seen: list[tuple[bytes, str]] = []

    def _parse_image(data, name):
        seen.append((data, name))
        return "OCR-TEXT"

    monkeypatch.setattr(media_nodes, "parse_image", _parse_image)

    out = await media_nodes.ocr_extract({"attachment_id": str(aid)}, {}, ctx)

    assert out["output"] == "OCR-TEXT"
    assert out["attachment_id"] == str(aid)
    assert out["mime_type"] == "image/png"
    assert seen == [(b"IMG", f"ocr-{aid}")]
    assert reader.image_calls == 1
    assert reader.attachment_calls == 0


@pytest.mark.asyncio
async def test_audio_transcribe_reads_attachment_filename(monkeypatch):
    aid = uuid4()
    reader = FakeReader(attachment=AttachmentBytes(data=b"AUD", mime="audio/mpeg", filename="a.mp3"))
    ctx = RunContext(tenant_id=str(uuid4()), media_reader=reader)

    seen: list[tuple[bytes, str]] = []

    def _parse_audio(data, filename):
        seen.append((data, filename))
        return "ASR"

    monkeypatch.setattr(media_nodes, "parse_audio", _parse_audio)

    out = await media_nodes.audio_transcribe({"attachment_id": str(aid)}, {}, ctx)

    assert out["output"] == "ASR"
    assert out["attachment_id"] == str(aid)
    assert out["filename"] == "a.mp3"
    assert seen == [(b"AUD", "a.mp3")]
    assert reader.attachment_calls == 1
    assert reader.image_calls == 0


@pytest.mark.asyncio
async def test_audio_transcribe_filename_fallback(monkeypatch):
    aid = uuid4()
    reader = FakeReader(attachment=AttachmentBytes(data=b"AUD", mime="audio/mpeg", filename=None))
    ctx = RunContext(tenant_id=str(uuid4()), media_reader=reader)

    monkeypatch.setattr(media_nodes, "parse_audio", lambda data, filename: "ASR")

    out = await media_nodes.audio_transcribe({"attachment_id": str(aid)}, {}, ctx)

    assert out["filename"] == f"audio-{aid}"


@pytest.mark.asyncio
async def test_missing_attachment_id_raises_before_reader_check():
    # ctx 未装配 reader，仍应因缺少 attachment_id 早返回报错
    ctx = RunContext(tenant_id=str(uuid4()))

    with pytest.raises(BadRequestError):
        await media_nodes.ocr_extract({}, {}, ctx)
    with pytest.raises(BadRequestError):
        await media_nodes.audio_transcribe({}, {}, ctx)


@pytest.mark.asyncio
async def test_without_media_reader_raises():
    aid = uuid4()
    ctx = RunContext(tenant_id=str(uuid4()), media_reader=None)

    with pytest.raises(BadRequestError, match="媒体读取器"):
        await media_nodes.ocr_extract({"attachment_id": str(aid)}, {}, ctx)
    with pytest.raises(BadRequestError, match="媒体读取器"):
        await media_nodes.audio_transcribe({"attachment_id": str(aid)}, {}, ctx)


@pytest.mark.asyncio
async def test_resolve_attachment_id_variants(monkeypatch):
    aid = uuid4()

    # inputs.media 列表命中
    reader = FakeReader(image=AttachmentBytes(data=b"IMG", mime="image/png"))
    ctx = RunContext(tenant_id=str(uuid4()), media_reader=reader)
    monkeypatch.setattr(media_nodes, "parse_image", lambda data, name: "OCR-TEXT")
    out = await media_nodes.ocr_extract({}, {"media": [{"attachment_id": str(aid)}]}, ctx)
    assert out["attachment_id"] == str(aid)

    # node_data.input_key 命中 inputs 键
    reader2 = FakeReader(image=AttachmentBytes(data=b"IMG", mime="image/png"))
    ctx2 = RunContext(tenant_id=str(uuid4()), media_reader=reader2)
    out2 = await media_nodes.ocr_extract({"input_key": "file"}, {"file": str(aid)}, ctx2)
    assert out2["attachment_id"] == str(aid)
