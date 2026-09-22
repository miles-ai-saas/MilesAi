"""生图 prompt 护栏：默认禁止组图/宫格，除非用户明确要求。"""

from __future__ import annotations

import re

# 用户明确要求组图/拼贴时才放行
_USER_COLLAGE_RE = re.compile(
    r"组图|拼图|拼接|拼贴|四宫格|九宫格|多宫格|分镜|故事板|"
    r"一张里|同图多|多视角拼|多角度拼|collage|storyboard|grid\s*(of|layout)|"
    r"mood\s*board|联系图",
    re.IGNORECASE,
)

# 模型常写入 prompt 的组图指令（未获用户授权时应弱化）
_LLM_COLLAGE_DIRECTIVE_RE = re.compile(
    r"(?:请)?(?:生成|输出|绘制)?(?:一张)?(?:包含)?(?:四|4|九|9|多)?(?:宫格|分镜|拼贴|拼接|组图)"
    r"(?:布局|构图|展示|画面)?[，,。.\s]*|"
    r"(?:四视图|多视角|多角度)(?:拼接|拼成|组合在)?(?:一张|同一[张幅])[，,。.\s]*|"
    r"(?:grid|collage|storyboard)\s*(?:layout|of\s+\d+)?[，,.\s]*",
    re.IGNORECASE,
)

_SINGLE_SHOT_SUFFIX = "。成片要求：仅一幅独立完整画面，禁止四宫格/九宫格/分镜拼贴/多图拼接；不要在同一张图内排列多个视角、多款产品或多种构图。"


def user_requests_image_collage(text: str | None) -> bool:
    """用户自然语言是否明确要求组图/拼贴。"""
    if not text or not str(text).strip():
        return False
    return bool(_USER_COLLAGE_RE.search(str(text)))


def sanitize_image_prompt(prompt: str, *, allow_collage: bool = False) -> str:
    """未授权组图时：去掉模型擅自加入的宫格指令，并追加单幅成片约束。

    n>1 表示生成多张**各自独立**的图，不是一张里塞多格。
    """
    text = (prompt or "").strip()
    if not text:
        return text
    if allow_collage:
        return text

    cleaned = _LLM_COLLAGE_DIRECTIVE_RE.sub("", text)
    cleaned = re.sub(r"[，,]{2,}", "，", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip("，,。.;； ")
    if not cleaned:
        cleaned = text

    if "禁止四宫格" in cleaned or "独立完整画面" in cleaned or "单张完整" in cleaned:
        return cleaned
    return f"{cleaned}{_SINGLE_SHOT_SUFFIX}"
