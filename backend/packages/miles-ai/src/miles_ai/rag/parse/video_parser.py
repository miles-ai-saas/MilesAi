"""
视频解析：ffmpeg 抽音轨转写 + 关键帧 OCR（可选）。

无 ffmpeg / Whisper / pytesseract 时仍返回占位文本，保证 ingest 可继续。
供 KB 多模态文档入库；检索时可经 ``query_document_id`` 现场解析为 query。

**失败形态可区分**（同 image_parser）：未安装（预期形态，静默、提示安装）与已安装但
执行失败（记日志 —— ffmpeg 在而编解码器缺失 / 超时 / 文件损坏时，若仍提示「请安装
ffmpeg」会把排查方向指反）。占位文案按 ``shutil.which("ffmpeg")`` 分流，不臆断失败原因。
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from miles_ai.rag.parse.image_parser import parse_image
from miles_ai.rag.parse.media import VIDEO_EXTENSIONS
from miles_core.logging import get_logger

logger = get_logger(__name__)

#: ffmpeg 缺失时的占位提示。
_PLACEHOLDER_MISSING = (
    "未能解析视频内容。请安装 ffmpeg；音轨转写需 openai-whisper（随 miles-ai 声明）；画面文字识别需 pytesseract。也可先提取字幕/文稿为文本文件上传。"
)
#: ffmpeg 存在但未产出可入库内容时的占位提示：指向日志，不臆断是「失败」还是
#: 「确实没有音轨与可识别画面文字」。
_PLACEHOLDER_PRESENT = (
    "未能解析视频内容。ffmpeg 已存在，若持续失败请查服务端日志（音轨转写需 openai-whisper，画面文字识别需 pytesseract）。也可先提取字幕/文稿为文本文件上传。"
)


def _stderr_tail(proc: subprocess.CompletedProcess, *, limit: int = 300) -> str:
    """取子进程 stderr 尾部用于日志。

    调用方有的用 ``text=True`` 有的用字节流，故两种都要兼容；截断避免把整段
    ffmpeg 噪声灌进日志。
    """
    raw = getattr(proc, "stderr", None) or ""
    text = raw if isinstance(raw, str) else raw.decode("utf-8", errors="replace")
    return text.strip()[-limit:] or "(空)"


def parse_video(data: bytes, filename: str) -> str:
    """合并音轨转写与关键帧 OCR 为可入库文本。

    纯音频容器（如无视频轨的 .webm）也能解析：ffmpeg 抽音轨后与普通音频同样转写。
    """
    ext = Path(filename).suffix.lower() or ".mp4"
    if ext not in VIDEO_EXTENSIONS:
        ext = ".mp4"

    parts: list[str] = []

    audio_wav = _extract_audio_wav(data, ext)
    if audio_wav:
        from miles_ai.rag.parse.audio_parser import parse_audio

        transcript = parse_audio(audio_wav, f"audio-from-{filename}")
        if transcript and not transcript.startswith("[音频 ·"):
            parts.append(transcript)

    for idx, frame_jpeg in enumerate(_extract_key_frames(data, ext, max_frames=5), start=1):
        frame_text = parse_image(frame_jpeg, f"frame-{idx}-{filename}")
        if frame_text and "未能识别图中文字" not in frame_text:
            parts.append(f"[视频关键帧 {idx} · {filename}]\n\n{frame_text}")

    if parts:
        return "\n\n".join(parts)

    # 按 ffmpeg 是否可用来分流文案：不臆断「失败」还是「确实无可提取内容」，
    # 真实原因已由各 helper 记入日志。
    hint = _PLACEHOLDER_MISSING if shutil.which("ffmpeg") is None else _PLACEHOLDER_PRESENT
    return f"[视频 · {filename}]\n{hint}"


def _extract_audio_wav(data: bytes, ext: str) -> bytes | None:
    """ffmpeg 抽取 mono 16kHz wav；失败返回 None。"""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg or not data:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        inp = tmp_path / f"input{ext}"
        out = tmp_path / "audio.wav"
        inp.write_bytes(data)
        try:
            proc = subprocess.run(
                [
                    ffmpeg,
                    "-y",
                    "-i",
                    str(inp),
                    "-vn",
                    "-acodec",
                    "pcm_s16le",
                    "-ar",
                    "16000",
                    "-ac",
                    "1",
                    str(out),
                ],
                capture_output=True,
                timeout=300,
                check=False,
            )
            if proc.returncode != 0 or not out.is_file():
                logger.warning("ffmpeg 抽取音轨失败（rc=%s）：%s", proc.returncode, _stderr_tail(proc))
                return None
            wav = out.read_bytes()
            return wav if len(wav) > 44 else None
        except (OSError, subprocess.TimeoutExpired):
            logger.warning("ffmpeg 抽取音轨异常", exc_info=True)
            return None


def _frame_timestamps(data: bytes, ext: str, max_frames: int) -> list[float]:
    """均匀分布的时间点（步长下限 0.5s，末端夹在时长内）；时长未知时只取首帧。"""
    duration = _probe_duration(data, ext)
    if duration is None or duration <= 0:
        return [0.0]
    step = max(duration / max(max_frames, 1), 0.5)
    return [min(i * step, max(duration - 0.1, 0)) for i in range(max_frames)]


def _extract_frame(ffmpeg: str, inp: Path, out: Path, ts: float) -> bytes | None:
    """抽取单个时间点的 JPEG 帧；失败、超时或帧过小返回 None。"""
    try:
        proc = subprocess.run(
            [
                ffmpeg,
                "-y",
                "-ss",
                str(ts),
                "-i",
                str(inp),
                "-vframes",
                "1",
                "-q:v",
                "2",
                "-f",
                "image2",
                str(out),
            ],
            capture_output=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        logger.warning("ffmpeg 抽帧异常（ts=%ss）", ts, exc_info=True)
        return None
    if proc.returncode != 0 or not out.is_file():
        logger.warning("ffmpeg 抽帧失败（ts=%ss, rc=%s）：%s", ts, proc.returncode, _stderr_tail(proc))
        return None
    jpeg = out.read_bytes()
    return jpeg if len(jpeg) > 100 else None


def _extract_key_frames(data: bytes, ext: str, *, max_frames: int) -> list[bytes]:
    """均匀抽取关键帧 JPEG 字节列表。"""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg or not data or max_frames < 1:
        return []

    frames: list[bytes] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        inp = tmp_path / f"input{ext}"
        inp.write_bytes(data)
        for ts in _frame_timestamps(data, ext, max_frames):
            out = tmp_path / f"frame_{int(ts * 1000)}.jpg"
            jpeg = _extract_frame(ffmpeg, inp, out, ts)
            if jpeg is not None:
                frames.append(jpeg)
    return frames


def _probe_duration(data: bytes, ext: str) -> float | None:
    """ffprobe 读取时长（秒）。"""
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        inp = Path(tmp) / f"input{ext}"
        inp.write_bytes(data)
        try:
            proc = subprocess.run(
                [
                    ffprobe,
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    str(inp),
                ],
                capture_output=True,
                timeout=60,
                check=False,
                text=True,
            )
            if proc.returncode != 0:
                # 时长探测失败是良性回落（只取首帧），故用 debug 避免刷屏。
                logger.debug("ffprobe 读取时长失败（rc=%s）：%s", proc.returncode, _stderr_tail(proc))
                return None
            raw = (proc.stdout or "").strip()
            return float(raw) if raw else None
        except (OSError, subprocess.TimeoutExpired, ValueError):
            logger.debug("ffprobe 读取时长异常", exc_info=True)
            return None
