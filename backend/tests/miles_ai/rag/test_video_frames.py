"""``_extract_key_frames`` 的特征化测试。

该函数以 tempdir → for → try → if → if 五层嵌套执行 ffmpeg 抽帧，此前无覆盖。
重构（抽单帧 helper）前先在此锁定：ffmpeg 缺失/空数据/帧数下限的短路、时间点
计算（含短视频的夹取）、以及各类失败帧的丢弃规则。
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

from miles_ai.rag.parse import video_parser

_REAL_TIMEOUT = subprocess.TimeoutExpired


def _patch_which(monkeypatch, available: set[str]) -> None:
    """只替换 video_parser 内部的 shutil 引用，避免影响全局 shutil。"""
    monkeypatch.setattr(
        video_parser,
        "shutil",
        SimpleNamespace(which=lambda name: f"/usr/bin/{name}" if name in available else None),
    )


class _RunRecorder:
    """记录 subprocess.run 调用并把输出文件写到 ``args[-1]``。"""

    def __init__(self, *, payload: bytes = b"J" * 200, returncode: int = 0, write_file: bool = True, exc=None):  # noqa: ANN001
        self.payload = payload
        self.returncode = returncode
        self.write_file = write_file
        self.exc = exc
        self.calls: list[list[str]] = []

    def __call__(self, args, **kwargs):  # noqa: ANN001
        self.calls.append(args)
        if self.exc is not None:
            raise self.exc
        if self.write_file:
            Path(args[-1]).write_bytes(self.payload)
        return SimpleNamespace(returncode=self.returncode, stdout="")

    @property
    def seek_times(self) -> list[str]:
        return [args[args.index("-ss") + 1] for args in self.calls if "-ss" in args]


def _patch_run(monkeypatch, recorder: _RunRecorder) -> None:
    monkeypatch.setattr(
        video_parser,
        "subprocess",
        SimpleNamespace(run=recorder, TimeoutExpired=_REAL_TIMEOUT),
    )


def _patch_duration(monkeypatch, value: float | None) -> None:
    monkeypatch.setattr(video_parser, "_probe_duration", lambda data, ext: value)


# --------------------------------------------------------------------------- #
# 短路
# --------------------------------------------------------------------------- #


def test_no_ffmpeg_returns_empty(monkeypatch):
    _patch_which(monkeypatch, set())
    assert video_parser._extract_key_frames(b"\x00", ".mp4", max_frames=5) == []


def test_empty_data_returns_empty(monkeypatch):
    _patch_which(monkeypatch, {"ffmpeg"})
    assert video_parser._extract_key_frames(b"", ".mp4", max_frames=5) == []


def test_max_frames_below_one_returns_empty(monkeypatch):
    _patch_which(monkeypatch, {"ffmpeg"})
    assert video_parser._extract_key_frames(b"\x00", ".mp4", max_frames=0) == []


# --------------------------------------------------------------------------- #
# 单帧成功
# --------------------------------------------------------------------------- #


def test_single_frame_when_duration_unknown(monkeypatch):
    _patch_which(monkeypatch, {"ffmpeg"})
    _patch_duration(monkeypatch, None)
    recorder = _RunRecorder(payload=b"J" * 200)
    _patch_run(monkeypatch, recorder)

    frames = video_parser._extract_key_frames(b"\x00" * 16, ".mp4", max_frames=5)

    assert len(frames) == 1
    assert frames[0] == b"J" * 200
    assert recorder.seek_times == ["0.0"]


def test_non_positive_duration_treated_as_unknown(monkeypatch):
    _patch_which(monkeypatch, {"ffmpeg"})
    _patch_duration(monkeypatch, 0.0)
    recorder = _RunRecorder()
    _patch_run(monkeypatch, recorder)

    frames = video_parser._extract_key_frames(b"\x00" * 16, ".mp4", max_frames=5)

    assert len(frames) == 1
    assert recorder.seek_times == ["0.0"]


# --------------------------------------------------------------------------- #
# 时间点计算
# --------------------------------------------------------------------------- #


def test_timestamps_evenly_spaced_by_step(monkeypatch):
    _patch_which(monkeypatch, {"ffmpeg"})
    _patch_duration(monkeypatch, 10.0)
    recorder = _RunRecorder()
    _patch_run(monkeypatch, recorder)

    frames = video_parser._extract_key_frames(b"\x00" * 16, ".mp4", max_frames=5)

    assert recorder.seek_times == ["0.0", "2.0", "4.0", "6.0", "8.0"]
    assert len(frames) == 5


def test_short_duration_clamps_to_last_frame(monkeypatch):
    """时长很短时步长下限 0.5 会把时间点压到 ``duration - 0.1``，出现重复取帧。"""
    _patch_which(monkeypatch, {"ffmpeg"})
    _patch_duration(monkeypatch, 0.2)
    recorder = _RunRecorder()
    _patch_run(monkeypatch, recorder)

    frames = video_parser._extract_key_frames(b"\x00" * 16, ".mp4", max_frames=5)

    assert recorder.seek_times == ["0.0", "0.1", "0.1", "0.1", "0.1"]
    assert len(frames) == 5


# --------------------------------------------------------------------------- #
# 失败帧的丢弃规则
# --------------------------------------------------------------------------- #


def test_frame_at_or_below_100_bytes_is_dropped(monkeypatch):
    _patch_which(monkeypatch, {"ffmpeg"})
    _patch_duration(monkeypatch, None)
    _patch_run(monkeypatch, _RunRecorder(payload=b"J" * 100))

    assert video_parser._extract_key_frames(b"\x00" * 16, ".mp4", max_frames=5) == []


def test_nonzero_returncode_drops_frame(monkeypatch):
    _patch_which(monkeypatch, {"ffmpeg"})
    _patch_duration(monkeypatch, None)
    _patch_run(monkeypatch, _RunRecorder(returncode=1))

    assert video_parser._extract_key_frames(b"\x00" * 16, ".mp4", max_frames=5) == []


def test_missing_output_file_drops_frame(monkeypatch):
    _patch_which(monkeypatch, {"ffmpeg"})
    _patch_duration(monkeypatch, None)
    _patch_run(monkeypatch, _RunRecorder(write_file=False))

    assert video_parser._extract_key_frames(b"\x00" * 16, ".mp4", max_frames=5) == []


def test_timeout_is_swallowed(monkeypatch):
    _patch_which(monkeypatch, {"ffmpeg"})
    _patch_duration(monkeypatch, None)
    _patch_run(monkeypatch, _RunRecorder(exc=_REAL_TIMEOUT("ffmpeg", 120)))

    assert video_parser._extract_key_frames(b"\x00" * 16, ".mp4", max_frames=5) == []


def test_oserror_is_swallowed(monkeypatch):
    _patch_which(monkeypatch, {"ffmpeg"})
    _patch_duration(monkeypatch, None)
    _patch_run(monkeypatch, _RunRecorder(exc=OSError("spawn failed")))

    assert video_parser._extract_key_frames(b"\x00" * 16, ".mp4", max_frames=5) == []


def test_partial_failure_keeps_successful_frames(monkeypatch):
    """个别时间点抽帧失败不影响已完成帧的收集。"""
    _patch_which(monkeypatch, {"ffmpeg"})
    _patch_duration(monkeypatch, 4.0)
    recorder = _RunRecorder()

    def run(args, **kwargs):  # noqa: ANN001
        # 第 2 个时间点（-ss 1.0）失败，其余正常
        if "-ss" in args and args[args.index("-ss") + 1] == "1.0":
            return SimpleNamespace(returncode=1, stdout="")
        return recorder(args, **kwargs)

    _patch_run(monkeypatch, run)

    frames = video_parser._extract_key_frames(b"\x00" * 16, ".mp4", max_frames=4)

    assert len(frames) == 3
