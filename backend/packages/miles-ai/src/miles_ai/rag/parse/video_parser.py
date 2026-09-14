"""
视频解析：ffmpeg 抽音轨转写 + 关键帧 OCR（可选）。

无 ffmpeg / Whisper / pytesseract 时仍返回占位文本，保证 ingest 可继续。
供 KB 多模态文档入库；检索时可经 ``query_document_id`` 现场解析为 query。
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from miles_ai.rag.parse.image_parser import parse_image
from miles_ai.rag.parse.media import VIDEO_EXTENSIONS


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

    return (
        f"[视频 · {filename}]\n"
        "未能解析视频内容。请安装 ffmpeg；音轨转写需 openai-whisper（[multimodal]）；"
        "画面文字识别需 pytesseract。也可先提取字幕/文稿为文本文件上传。"
    )


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
                return None
            wav = out.read_bytes()
            return wav if len(wav) > 44 else None
        except (OSError, subprocess.TimeoutExpired):
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
        return None
    if proc.returncode != 0 or not out.is_file():
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
                return None
            raw = (proc.stdout or "").strip()
            return float(raw) if raw else None
        except (OSError, subprocess.TimeoutExpired, ValueError):
            return None
