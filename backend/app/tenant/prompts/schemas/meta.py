"""prompts 模块 GET /prompt-templates/meta 响应体。"""

from pydantic import BaseModel

from app.common.schemas.enum_meta import EnumOption


class PromptMetaOut(BaseModel):
    """提示词模板启用状态枚举。"""

    active_states: list[EnumOption]
    schema_version: str = "1"
