"""schemas.agent 对 models/agent/chat_io 的 re-export shim 契约守卫。

防未来有人在 shim 内另起炉灶复制 DTO 定义导致双身份漂移（同字段不同类）。
"""

from miles_core.models.agent.chat_io import (
    ChatArtifact,
    ChatMediaIn,
    ChatRequest,
    ChatResponse,
    PendingToolCall,
)
from miles_portal.tenant.agents.schemas import agent as schemas_agent


def test_chat_io_shim_exports_same_objects():
    assert schemas_agent.ChatRequest is ChatRequest
    assert schemas_agent.ChatResponse is ChatResponse
    assert schemas_agent.ChatArtifact is ChatArtifact
    assert schemas_agent.ChatMediaIn is ChatMediaIn
    assert schemas_agent.PendingToolCall is PendingToolCall
