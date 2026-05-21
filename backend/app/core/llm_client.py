"""大模型调用 — 委托 LangChain ChatModel 层。"""

from app.ai_stack.langchain.chat_models import ainvoke_chat
from app.models.model import ModelConfig


async def chat_completion(
    model: ModelConfig,
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> str:
    return await ainvoke_chat(
        model,
        messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
