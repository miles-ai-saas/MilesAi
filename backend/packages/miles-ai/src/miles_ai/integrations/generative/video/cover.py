"""从视频字节抽取封面图（JPEG），供 media_assets.cover_attachment_id。"""

from __future__ import annotations

from miles_core.logging import get_logger
import shutil
import subprocess
import tempfile
from pathlib import Path

logger = get_logger(__name__)


def extract_video_cover_jpeg(video_bytes: bytes) -> bytes | None:
    """
    使用 ffmpeg 抽取首帧为 JPEG；未安装 ffmpeg 或失败时返回 None（不阻塞主流程）。
    """
    if not video_bytes or len(video_bytes) < 32:
        return None
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        logger.debug("ffmpeg not found, skip video cover extraction")
        return None

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        inp = tmp_path / "input.mp4"
        out = tmp_path / "cover.jpg"
        inp.write_bytes(video_bytes)
        try:
            proc = subprocess.run(
                [
                    ffmpeg,
                    "-y",
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
                timeout=60,
                check=False,
            )
            if proc.returncode != 0 or not out.is_file():
                logger.debug(
                    "ffmpeg cover extraction failed: %s",
                    (proc.stderr or b"")[:500].decode(errors="replace"),
                )
                return None
            data = out.read_bytes()
            return data if len(data) > 100 else None
        except (OSError, subprocess.TimeoutExpired) as exc:
            logger.debug("ffmpeg cover extraction error: %s", exc)
            return None
