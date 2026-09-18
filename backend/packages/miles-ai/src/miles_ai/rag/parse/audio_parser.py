"""
音频解析：可选 openai-whisper 转写。

无 Whisper 时返回占位说明，流程可继续；与 image_parser 策略一致。
供 ingest 入库与画布 ``AudioTranscribe`` / ``media_nodes`` 节点共用。

**两种失败形态可区分**（同 image_parser）：未安装（静默、提示安装）与已安装但执行失败
（记日志 —— 常见于模型下载失败 / 显存不足，此时提示「安装 openai-whisper」会误导）。
"""

import tempfile
from pathlib import Path

from miles_core.logging import get_logger

logger = get_logger(__name__)

#: 未安装 Whisper。
_PLACEHOLDER_MISSING = "可在 Worker 环境安装 openai-whisper 后重试，或先将音频转为文本文件上传。"
#: 已安装但执行失败；指向日志而非「安装」。
_PLACEHOLDER_FAILED = "Whisper 后端已安装但执行失败（详见服务端日志），或先将音频转为文本文件上传。"


def parse_audio(data: bytes, filename: str) -> str:
    """Whisper 转写或占位文本。"""
    ext = Path(filename).suffix.lower() or ".wav"
    if ext not in {".mp3", ".wav", ".m4a", ".ogg", ".webm"}:
        ext = ".wav"

    transcript, failed = _try_whisper(data, ext)
    if transcript and transcript.strip():
        return f"[音频转写 · {filename}]\n\n{transcript.strip()}"

    hint = _PLACEHOLDER_FAILED if failed else _PLACEHOLDER_MISSING
    return f"[音频 · {filename}]\n未能转写音频内容。{hint}"


def _try_whisper(data: bytes, ext: str) -> tuple[str | None, bool]:
    """openai-whisper base 模型；返回 ``(文本, 是否已安装但执行失败)``。

    未安装与「已安装但加载/转写失败」须区分：后者写日志并带 ``exc_info``，
    否则运维只看到「未能转写」，无从得知是模型下载失败还是显存不足。
    """
    try:
        import whisper
    except ImportError:
        return None, False

    with tempfile.NamedTemporaryFile(suffix=ext, delete=True) as tmp:
        tmp.write(data)
        tmp.flush()
        try:
            model = whisper.load_model("base")
            result = model.transcribe(tmp.name, language="zh")
            return (result.get("text") or "").strip(), False
        except Exception:  # 转写失败须降级而非中断入库
            logger.warning("音频转写执行失败（whisper base / zh）", exc_info=True)
            return None, True
