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
    """写入本请求的生图/生视频偏好（ContextVar，随请求结束由 ``clear_generative_request_prefs`` 清除）。"""
    _image_n.set(image_n)
    _allow_collage.set(bool(allow_collage))
    _video_duration.set(video_duration)


def clear_generative_request_prefs() -> None:
    """清空本请求偏好，避免 ContextVar 残留影响后续请求。"""
    _image_n.set(None)
    _allow_collage.set(False)
    _video_duration.set(None)


def get_request_image_n() -> int | None:
    """读取输入区指定的生图张数；未设置时返回 ``None``。"""
    return _image_n.get()


def get_request_allow_collage() -> bool:
    """输入区是否允许拼图（默认 ``False``）。"""
    return bool(_allow_collage.get())


def get_request_video_duration() -> int | None:
    """读取输入区指定的视频时长（秒）；未设置时返回 ``None``。"""
    return _video_duration.get()


def resolve_image_n(llm_n: object | None, *, fallback: int = 1) -> int:
    """输入区张数优先；否则用 LLM 传入值；再否则 fallback。"""
    preset = get_request_image_n()
    if preset is not None:
        try:
            return min(max(int(preset), 1), 4)
        except (TypeError, ValueError):
            # 静默可接受：请求上下文里的张数可能被写成非数字；视为「未设置」，交给下一优先级。
            pass
    try:
        if llm_n is not None:
            return min(max(int(llm_n), 1), 4)
    except (TypeError, ValueError):
        # 静默可接受：LLM 传入值不可控；非法即回退 fallback。
        pass
    return min(max(int(fallback), 1), 4)
