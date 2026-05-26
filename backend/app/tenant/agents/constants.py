"""子智能体 role_hint 取值与展示文案（校验、meta、DeepAgents 共用）。"""

SUB_AGENT_ROLE_HINTS = frozenset({
    "retrieval",
    "ocr",
    "summary",
    "compliance",
    "custom",
})

# value -> (label, hint)
SUB_AGENT_ROLE_DISPLAY: dict[str, tuple[str, str | None]] = {
    "retrieval": ("检索", "知识检索"),
    "ocr": ("OCR", "OCR 识别"),
    "summary": ("总结", "摘要归纳"),
    "compliance": ("合规", "合规审查"),
    "custom": ("自定义", "自定义"),
}

# DeepAgents 子智能体描述（优先 hint 长文案）
SUB_AGENT_ROLE_LABELS: dict[str, str] = {
    role: (hint or label)
    for role, (label, hint) in SUB_AGENT_ROLE_DISPLAY.items()
}
