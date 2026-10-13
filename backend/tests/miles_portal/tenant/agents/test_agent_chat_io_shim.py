"""chat_io DTO 三方同对象契约：common 真源 ↔ core 兼容壳 ↔ portal schemas。

防未来有人在壳内另起炉灶复制 DTO 定义导致双身份漂移（同字段不同类）。
schemas.agent 已直连 ``miles_common.schemas.chat_io``；core 壳仍供 integrations 使用。
"""

from miles_common.schemas import chat_io as common_chat_io
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
    assert ChatRequest is common_chat_io.ChatRequest
