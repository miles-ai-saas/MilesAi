"""
LangChain 集成包（L3，仅本子包内容）。

- ``chat_models``：``ainvoke_chat`` / ``get_chat_model``
- ``tool_agent``：工具调用循环与契约
- ``toolkit``：平台工具 → LangChain 工具适配

检索、RAG 生成、KB 检索绑定分别见 ``rag.retrieve.multi_kb``、``rag.generate``、
``rag.retrieve.bindings``；本包不再 re-export 上层 L2 内容。
"""

from miles_ai.integrations.langchain.chat_models import ainvoke_chat, get_chat_model

__all__ = ["ainvoke_chat", "get_chat_model"]
