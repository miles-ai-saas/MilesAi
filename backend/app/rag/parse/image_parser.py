"""图片解析：优先 OCR 提取文本，未安装依赖时返回可检索的占位说明。"""

from io import BytesIO


def parse_image(data: bytes, filename: str) -> str:
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

    return (
        f"[图片 · {filename} · {width}x{height} · {mode}]\n"
        "未能识别图中文字。可安装 pytesseract 启用 OCR，或上传含文字层的 PDF/文档。"
    )


def _try_ocr(image) -> str | None:
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
