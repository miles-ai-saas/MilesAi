"""
图片解析：Pillow 读图 + 可选 pytesseract OCR。

无 OCR 时仍返回占位文本，保证 ingest 不失败（检索质量依赖后续安装 multimodal 依赖）。
"""

from io import BytesIO


def parse_image(data: bytes, filename: str) -> str:
    """OCR 或占位文本，保证 ingest 可继续。"""
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("图片解析需要安装 Pillow：pip install Pillow") from exc

    image = Image.open(BytesIO(data))
    image.load()
    width, height = image.size
    mode = image.mode

    ocr_text = _try_ocr(image)
    if ocr_text and ocr_text.strip():
        header = f"[图片 OCR · {filename} · {width}x{height}]"
        return f"{header}\n\n{ocr_text.strip()}"

    # 占位文本仍可分片入库，避免 ingest 失败；检索质量依赖后续安装 [multimodal]
    return (
        f"[图片 · {filename} · {width}x{height} · {mode}]\n"
        "未能识别图中文字。可安装 pytesseract 启用 OCR，或上传含文字层的 PDF/文档。"
    )


def _try_ocr(image) -> str | None:
    """pytesseract 可选；失败返回 None。"""
    try:
        import pytesseract
    except ImportError:
        return None
    try:
        return pytesseract.image_to_string(image, lang="chi_sim+eng")
    except Exception:
        try:
            return pytesseract.image_to_string(image)
        except Exception:
            return None
