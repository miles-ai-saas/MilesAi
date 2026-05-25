"""音频解析：优先 Whisper 转写，未安装时返回占位说明（仍可入库）。"""

import tempfile
from pathlib import Path


def parse_audio(data: bytes, filename: str) -> str:
    """Whisper 转写或占位文本。"""
    ext = Path(filename).suffix.lower() or ".wav"
    if ext not in {".mp3", ".wav", ".m4a", ".ogg", ".webm"}:
        ext = ".wav"

    transcript = _try_whisper(data, ext)
    if transcript and transcript.strip():
        return f"[音频转写 · {filename}]\n\n{transcript.strip()}"

    return (
        f"[音频 · {filename}]\n"
        "未能转写音频内容。可在 Worker 环境安装 openai-whisper 后重试，"
        "或先将音频转为文本文件上传。"
    )


def _try_whisper(data: bytes, ext: str) -> str | None:
    """openai-whisper base 模型；未安装则返回 None。"""
    try:
        import whisper
    except ImportError:
        return None

    with tempfile.NamedTemporaryFile(suffix=ext, delete=True) as tmp:
        tmp.write(data)
        tmp.flush()
        try:
            model = whisper.load_model("base")
            result = model.transcribe(tmp.name, language="zh")
            return (result.get("text") or "").strip()
        except Exception:
            return None
