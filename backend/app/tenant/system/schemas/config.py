"""系统配置读写与运行时信息响应模型。"""

from pydantic import BaseModel, Field


# 系统配置项输出。
class SystemConfigOut(BaseModel):
    key: str = Field(description="配置键")
    value: dict = Field(description="配置值")
    description: str | None = Field(default=None, description="配置说明")
    is_encrypted: bool = Field(default=False, description="是否加密存储")


# 系统配置写入请求（仅配置值与说明）。
class SystemConfigUpsert(BaseModel):
    value: dict = Field(description="配置值")
    description: str | None = Field(default=None, description="配置说明")


# 运行时组件状态与脱敏配置预览。
class RuntimeInfoOut(BaseModel):
    components: dict[str, str] = Field(description="运行时组件状态")
    settings_preview: dict[str, str | int | bool | None] = Field(description="配置项预览（脱敏）")


# 配置项定义元数据（管理端展示，合并默认值）。
class ConfigDefinitionOut(BaseModel):
    key: str = Field(description="配置键")
    label: str = Field(description="展示标签")
    category: str = Field(description="配置分类")
    description: str = Field(description="配置说明")
    value_type: str = Field(default="json", description="值类型")
    default_value: dict | str | int | float | bool | None = Field(default=None, description="默认值")
