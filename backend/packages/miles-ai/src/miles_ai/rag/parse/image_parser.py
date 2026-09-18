"""
图片解析：Pillow 读图 + 可选 pytesseract OCR。

无 OCR 时仍返回占位文本，保证 ingest 不失败（检索质量依赖 pytesseract 与系统 tesseract-ocr）。
供 ingest 入库与画布 ``OcrExtract`` / ``media_nodes`` 节点共用。

**两种失败形态可区分**（占位文案与日志都据此分流）：未安装（预期形态，静默且提示安装）
与已安装但执行失败（须记日志 —— 常见于 pip 包在而 tesseract **二进制**缺失，此时若仍
提示「安装 pytesseract」会把排查方向指反）。
"""

from io import BytesIO

from miles_core.logging import get_logger

logger = get_logger(__name__)

#: 未安装 OCR 后端。
_PLACEHOLDER_MISSING = "可安装 pytesseract 启用 OCR，或上传含文字层的 PDF/文档。"
#: 后端已安装但执行失败；指向日志而非「安装」。
_PLACEHOLDER_FAILED = "OCR 后端已安装但执行失败（详见服务端日志），或上传含文字层的 PDF/文档。"


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

    ocr_text, ocr_failed = _try_ocr(image)
    if ocr_text and ocr_text.strip():
        header = f"[图片 OCR · {filename} · {width}x{height}]"
        return f"{header}\n\n{ocr_text.strip()}"

    # 占位文本仍可分片入库，避免 ingest 失败；检索质量依赖 pytesseract 与系统 tesseract-ocr
    hint = _PLACEHOLDER_FAILED if ocr_failed else _PLACEHOLDER_MISSING
    return f"[图片 · {filename} · {width}x{height} · {mode}]\n未能识别图中文字。{hint}"


def _try_ocr(image) -> tuple[str | None, bool]:
    """pytesseract 可选；返回 ``(文本, 是否已安装但执行失败)``。

    失败分两种，排查方向不同，故必须区分：未安装（装包即解）与已安装但执行失败
    （多为 tesseract 二进制缺失 / 训练数据不全）。后者写日志并带 ``exc_info``，
    否则运维只能看到占位文本、无从发现真因。

    先试 ``chi_sim+eng`` 再回落默认语言（与既有行为一致）；仅当两次都失败才记日志，
    避免「缺 chi_sim 训练数据但回落成功」的正常情形每次调用都刷警告。
    """
    try:
        import pytesseract
    except ImportError:
        return None, False

    first_error: Exception | None = None
    try:
        return pytesseract.image_to_string(image, lang="chi_sim+eng"), False
    except Exception as exc:  # OCR 失败须降级而非中断入库
        first_error = exc

    try:
        return pytesseract.image_to_string(image), False
    except Exception:
        logger.warning("图片 OCR 执行失败（首选 chi_sim+eng 的错误：%s）", first_error, exc_info=True)
        return None, True
