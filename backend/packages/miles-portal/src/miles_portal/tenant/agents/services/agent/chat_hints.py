"""对话 system prompt 中的工具协议提示（生图/知识库）。"""

from __future__ import annotations


def _generative_tools_system_hint(*, image_n: int = 1, video_duration: int = 5) -> str:
    """按配置注入的生图/生视频协议；业务 system prompt 不应再手写 tool_call 规则。

    张数以用户输入区为准，由平台在 tool 入参层强制覆盖；模型不得在正文自行「确认」或改写 n。
    """
    dur_hint = (
        f"\n若用户要求生成视频：调用 generate_video；duration 取用户输入区当前值 {video_duration}。"
        if video_duration != 5
        else "\n若用户要求生成视频：调用 generate_video；duration 以用户输入为准。"
    )
    return (
        "\n【生成工具·平台协议】"
        "\n你已挂载 generate_image（以及可用时的 generate_video）。"
        "\n当用户要求生成图片时：必须通过 function calling 发起真正的 tool_call，"
        "把画面描述写入参数 prompt；禁止在回复正文输出生图提示词、JSON、代码块或伪调用。"
        "\n出图数量由输入区控件决定，不可改写："
        f"本次 n={image_n}，调用 generate_image 时必须传 n={image_n}；"
        "禁止根据业务习惯、多视角、参考图数量自行改为其他 n；"
        "禁止在回复正文写「已确认 n=…」或自行宣布张数。"
        "\nsize 仅在用户明确要求时填写，否则可省略（用模型默认）。"
        "\nn>1 表示生成多张彼此独立的完整单图（每张一个主体画面），"
        "禁止在 prompt 里写四宫格/九宫格/分镜拼贴/组图拼接；"
        "除非用户本轮明确要求组图、拼贴或宫格布局。"
        "\n注意：尺寸单边 ≥1280 或 n≥3 需用户二次确认；确认前勿重复调用。"
        "\n同一轮用户消息仅允许调用一次 generate_image / generate_video。"
        f"{dur_hint}"
    )


def _knowledge_tools_system_hint(kb_ids: list[str]) -> str:
    """知识库工具协议：RAG 与 tool calling 共存时由 LLM 自行决定是否检索。"""
    ids = "、".join(kb_ids)
    return (
        "\n【知识库工具】本智能体已绑定知识库（kb_ids："
        f"{ids}）。"
        "\n回答与知识库内容相关的问题时，先通过 function calling 调用 knowledge_search"
        "（query 用用户问题或关键词；kb_ids 可省略，默认检索全部绑定库）。"
        "\n请依据返回片段作答，并在正文中自然引用来源；片段不足以回答时如实说明，不要编造。"
    )
