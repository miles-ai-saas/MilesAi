"""解析器降级路径的可诊断性：后端「已安装但执行失败」必须留痕，文案不得误导。

背景（实测）：`pytesseract` pip 包与 `tesseract` **二进制**是两个独立依赖。slim 容器
常只装了前者，此时 `pytesseract.image_to_string` 抛 `TesseractNotFoundError`
（实测其 MRO 为 `OSError` → `Exception`），被 `except Exception` 吞掉。后果有两层：

1. **零日志** —— 运维无从发现真因（当前本机即是此形态：pip 包在、二进制缺）；
2. **文案把方向指反** —— 占位文本仍写「可安装 pytesseract 启用 OCR」，而 pytesseract
   本来就是装好的；应排查的是二进制。

后果不止于文案：KB 入库会把占位文本当作正文索引，检索质量静默下降且无人知晓。
故本文件锁住「两种失败可区分」这一行为：未安装 → 提示安装；已安装但失败 → 提示查日志。

``sys.modules`` 注入使两种形态与宿主环境无关（本机装了 pytesseract，CI 可能装有
tesseract 二进制，都不应影响判定）。
"""

from __future__ import annotations

import io
import logging
import sys
import types

import pytest
from PIL import Image

from miles_ai.rag.parse import audio_parser, image_parser, video_parser

_LOGGER_NAMES = (image_parser.__name__, audio_parser.__name__, video_parser.__name__)


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (40, 12), "white").save(buf, format="PNG")
    return buf.getvalue()


def _install_failing_module(monkeypatch, name: str, func_name: str) -> None:
    """注入一个「可导入但调用即抛错」的假模块，模拟已安装但执行失败。"""
    module = types.ModuleType(name)

    def _raise(*_args, **_kwargs):
        raise OSError(f"{name}.{func_name} 执行失败（模拟二进制缺失）")

    setattr(module, func_name, _raise)
    monkeypatch.setitem(sys.modules, name, module)


def _make_unimportable(monkeypatch, name: str) -> None:
    """把模块置为 ``None``，使 ``import name`` 抛 ImportError，模拟未安装。"""
    monkeypatch.setitem(sys.modules, name, None)


def _parser_records(caplog) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name in _LOGGER_NAMES]


@pytest.fixture
def image_bytes() -> bytes:
    return _png_bytes()


def test_ocr_failure_is_logged_and_text_does_not_mislead(monkeypatch, caplog, image_bytes):
    """已安装但执行失败：须记警告日志，且文案不得再让人去「安装 pytesseract」。"""
    _install_failing_module(monkeypatch, "pytesseract", "image_to_string")

    with caplog.at_level(logging.WARNING):
        text = image_parser.parse_image(image_bytes, "demo.png")

    assert text.startswith("[图片 ·"), "占位文本须保留既有前缀（search.py 依赖该判定）"
    assert "未能识别图中文字" in text, "既有子串须保留（video_parser 依赖该判定）"
    assert "可安装 pytesseract" not in text, "已安装却仍提示安装，会把排查方向指反"
    assert "执行失败" in text, "应指出后端已安装但执行失败，并指向日志"

    records = _parser_records(caplog)
    assert records, "OCR 执行失败必须留痕，否则运维无从发现真因"
    assert any(r.exc_info for r in records), "日志应带异常信息（exc_info），而非只有一句概述"


def test_ocr_not_installed_is_quiet_and_suggests_installing(monkeypatch, caplog, image_bytes):
    """未安装：属预期形态，不记警告；文案提示安装。"""
    _make_unimportable(monkeypatch, "pytesseract")

    with caplog.at_level(logging.WARNING):
        text = image_parser.parse_image(image_bytes, "demo.png")

    assert "可安装 pytesseract" in text
    assert not _parser_records(caplog), "未安装是预期形态，不应刷警告日志"


def test_transcribe_failure_is_logged_and_text_does_not_mislead(monkeypatch, caplog):
    """Whisper 已安装但执行失败：同样须留痕且不误导。"""
    module = types.ModuleType("whisper")

    def _raise_model(*_args, **_kwargs):
        raise OSError("模型加载失败（模拟无网络 / 显存不足）")

    module.load_model = _raise_model
    monkeypatch.setitem(sys.modules, "whisper", module)

    with caplog.at_level(logging.WARNING):
        text = audio_parser.parse_audio(b"\x00" * 32, "demo.wav")

    assert "未能转写音频内容" in text
    assert "安装 openai-whisper" not in text, "已安装却仍提示安装，会把排查方向指反"
    assert "执行失败" in text

    records = _parser_records(caplog)
    assert records, "转写失败必须留痕"
    assert any(r.exc_info for r in records), "日志应带异常信息（exc_info）"


def test_transcribe_not_installed_is_quiet_and_suggests_installing(monkeypatch, caplog):
    """未安装：不记警告；文案提示安装。"""
    _make_unimportable(monkeypatch, "whisper")

    with caplog.at_level(logging.WARNING):
        text = audio_parser.parse_audio(b"\x00" * 32, "demo.wav")

    assert "未能转写音频内容" in text
    assert "安装 openai-whisper" in text
    assert not _parser_records(caplog), "未安装是预期形态，不应刷警告日志"


class _FakeProc:
    """最小 ``CompletedProcess`` 替身：只提供 helper 读取的 ``returncode`` / ``stderr``。"""

    def __init__(self, returncode: int = 1, stderr: bytes = b"Unknown decoder 'xyz'") -> None:
        self.returncode = returncode
        self.stdout = b""
        self.stderr = stderr


def test_video_parse_failure_is_logged_and_text_does_not_mislead(monkeypatch, caplog):
    """ffmpeg 已存在但执行失败：须记警告并在文案里指向日志，而非让人去「安装 ffmpeg」。"""
    monkeypatch.setattr(video_parser.shutil, "which", lambda name: "/usr/bin/ffmpeg" if name == "ffmpeg" else None)
    monkeypatch.setattr(video_parser.subprocess, "run", lambda *a, **k: _FakeProc())

    with caplog.at_level(logging.WARNING):
        text = video_parser.parse_video(b"\x00" * 64, "demo.mp4")

    assert text.startswith("[视频 ·"), "占位文本须保留既有前缀（KB 检索依赖该判定）"
    assert "未能解析视频内容" in text
    assert "请安装 ffmpeg" not in text, "ffmpeg 已存在却仍提示安装，会把排查方向指反"
    assert "日志" in text, "应把排查方向指向服务端日志"

    records = _parser_records(caplog)
    assert records, "ffmpeg 执行失败必须留痕，否则运维无从发现真因"
    assert any("ffmpeg" in r.getMessage() for r in records)


def test_video_parse_without_ffmpeg_is_quiet_and_suggests_installing(monkeypatch, caplog):
    """ffmpeg 缺失：属预期形态，不记警告；文案提示安装。"""
    monkeypatch.setattr(video_parser.shutil, "which", lambda name: None)

    with caplog.at_level(logging.WARNING):
        text = video_parser.parse_video(b"\x00" * 64, "demo.mp4")

    assert "请安装 ffmpeg" in text
    assert not _parser_records(caplog), "未安装是预期形态，不应刷警告日志"
