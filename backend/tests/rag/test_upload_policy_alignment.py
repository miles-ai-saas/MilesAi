"""上传白名单 ↔ 解析能力对齐守卫。

白名单与各解析后端的能力声明分散在不同模块，容易各写一份而漂移（Office 收进来了但
Docling 读不了 / media 认得的类型却不让上传）。此处以集合关系与往返断言锁死不变式。
"""

from __future__ import annotations

from miles_ai.rag.parse.backends.docling import DOCLING_EXTENSIONS
from miles_ai.rag.parse.media import AUDIO_EXTENSIONS, IMAGE_EXTENSIONS, VIDEO_EXTENSIONS
from miles_ai.rag.parse.upload_policy import (
    KB_ALLOWED_EXTENSIONS,
    KB_ALLOWED_MIMES,
    OFFICE_EXTENSIONS,
    is_kb_upload_allowed,
    kb_upload_accept_attribute,
)


def test_office_whitelist_subset_of_docling_capability():
    """Office 白名单必须都在 Docling 可解析集合内，否则「允许上传却必解析失败」。"""
    assert OFFICE_EXTENSIONS <= DOCLING_EXTENSIONS


def test_media_recognized_extensions_are_uploadable():
    """media 判定（图/音/视频）认得的扩展名必须都可上传，避免判定与白名单漂移。"""
    assert (IMAGE_EXTENSIONS | AUDIO_EXTENSIONS | VIDEO_EXTENSIONS) <= KB_ALLOWED_EXTENSIONS


def test_upload_policy_reuses_media_sets():
    """白名单的多模态扩展名/MIME 直接来自 media，不得另写一份。"""
    assert IMAGE_EXTENSIONS <= KB_ALLOWED_EXTENSIONS
    assert AUDIO_EXTENSIONS <= KB_ALLOWED_EXTENSIONS
    assert VIDEO_EXTENSIONS <= KB_ALLOWED_EXTENSIONS


def test_every_whitelisted_extension_round_trips():
    """白名单里的每个扩展名都能被 ``is_kb_upload_allowed`` 接受（含纯扩展名、MIME 缺失场景）。"""
    rejected = [ext for ext in KB_ALLOWED_EXTENSIONS if not is_kb_upload_allowed(f"sample{ext}", "")]
    assert not rejected, f"白名单扩展名未被接受：{sorted(rejected)}"


def test_every_whitelisted_mime_round_trips():
    rejected = [mime for mime in KB_ALLOWED_MIMES if not is_kb_upload_allowed("sample", mime)]
    assert not rejected, f"白名单 MIME 未被接受：{sorted(rejected)}"


def test_accept_attribute_covers_all_extensions():
    """前端 ``accept`` 属性需覆盖白名单全部扩展名，避免前端选不到后端允许的类型。"""
    accept = set(kb_upload_accept_attribute().split(","))
    assert KB_ALLOWED_EXTENSIONS <= accept
