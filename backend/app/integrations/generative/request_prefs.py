"""单次对话请求的生图/生视频偏好（ContextVar）。

输入区参数不应写入 Agent.config（避免脏写库），经 ContextVar 在同请求内传递给
tool invoke / handle_generate_*。
"""

from __future__ import annotations

from contextvars import ContextVar

_image_n: ContextVar[int | None] = ContextVar("generative_request_image_n", default=None)
_allow_collage: ContextVar[bool] = ContextVar("generative_request_allow_collage", default=False)
_video_duration: ContextVar[int | None] = ContextVar("generative_request_video_duration", default=None)


def set_generative_request_prefs(
    *,
    image_n: int | None = None,
    allow_collage: bool = False,
    video_duration: int | None = None,
) -> None:
    _image_n.set(image_n)
    _allow_collage.set(bool(allow_collage))
    _video_duration.set(video_duration)


def clear_generative_request_prefs() -> None:
    _image_n.set(None)
    _allow_collage.set(False)
    _video_duration.set(None)


def get_request_image_n() -> int | None:
    return _image_n.get()


def get_request_allow_collage() -> bool:
    return bool(_allow_collage.get())


def get_request_video_duration() -> int | None:
    return _video_duration.get()


def resolve_image_n(llm_n: object | None, *, fallback: int = 1) -> int:
    """输入区张数优先；否则用 LLM 传入值；再否则 fallback。"""
    preset = get_request_image_n()
    if preset is not None:
        try:
            return min(max(int(preset), 1), 4)
        except (TypeError, ValueError):
            pass
    try:
        if llm_n is not None:
            return min(max(int(llm_n), 1), 4)
    except (TypeError, ValueError):
        pass
    return min(max(int(fallback), 1), 4)
