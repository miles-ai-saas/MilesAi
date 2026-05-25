"""大模型调用 — 委托 LangChain ChatModel 层。

遗留兼容入口；新代码优先 ainvoke_chat 或 get_chat_model。
"""

from app.integrations.langchain.chat_models import ainvoke_chat
from app.models.model import ModelConfig


async def chat_completion(
    model: ModelConfig,
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> str:
    """异步对话补全（无租户 BYOK 合并，调用方须已 resolve 模型）。"""
    return await ainvoke_chat(
        model,
        messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
