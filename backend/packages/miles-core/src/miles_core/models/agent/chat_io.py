"""智能体对话 IO 契约的兼容壳（真实定义已下沉 ``miles_common.schemas.chat_io``）。

保留本路径与 ``__all__`` 以维持既有 import 稳定（``miles_ai`` 3 处、测试 3 处、portal
``agents/schemas/agent.py`` 的 re-export 均指向此处）。新代码请直接 import
``miles_common.schemas.chat_io``。

为何再下沉一层：本模块位于 ``miles_core.models.agent`` 包内，而该包整包被
``.importlinter`` 契约 ``api-layer-no-orm`` 禁止（按聚合包层级拦截，连带禁止包内纯 DTO）。
"""

from miles_common.schemas.chat_io import (
    ChatArtifact,
    ChatMediaIn,
    ChatRequest,
    ChatResponse,
    PendingToolCall,
)

__all__ = [
    "ChatArtifact",
    "ChatMediaIn",
    "ChatRequest",
    "ChatResponse",
    "PendingToolCall",
]
