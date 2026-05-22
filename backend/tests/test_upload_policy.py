"""上传白名单与 parse 能力对齐。"""

from app.rag.parse.upload_policy import is_kb_upload_allowed, kb_upload_accept_attribute


def test_office_extensions_allowed():
    assert is_kb_upload_allowed("report.docx", "application/octet-stream")
    assert is_kb_upload_allowed(
        "slides.pptx",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )
    assert is_kb_upload_allowed(
        "sheet.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    assert is_kb_upload_allowed("page.htm", "text/html")


def test_accept_attribute_includes_office():
    accept = kb_upload_accept_attribute()
    assert ".docx" in accept
    assert ".pptx" in accept


def test_unknown_extension_rejected():
    assert not is_kb_upload_allowed("archive.zip", "application/zip")
