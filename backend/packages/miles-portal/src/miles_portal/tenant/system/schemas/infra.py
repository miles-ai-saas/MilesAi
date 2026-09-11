"""基础设施组件健康探测响应模型。"""

from typing import Literal

from pydantic import BaseModel, Field

InfraStatusValue = Literal["ok", "unavailable", "skipped"]


# 单个基础设施组件的探测结果。
class InfraComponentStatusOut(BaseModel):
    id: str = Field(description="组件标识")
    label: str = Field(description="展示名称")
    status: InfraStatusValue = Field(description="探测结果")
    latency_ms: int | None = Field(default=None, description="探测耗时（毫秒）")
    message: str | None = Field(default=None, description="失败原因")


# 整体健康状态与各组件明细。
class InfraStatusOut(BaseModel):
    healthy: bool = Field(description="是否全部可用")
    status: str = Field(description="healthy | degraded")
    components: list[InfraComponentStatusOut] = Field(description="各组件状态")
    settings_preview: dict[str, str | None] = Field(description="部署配置预览（脱敏）")


# 连接测试请求（可选组件子集）。
class InfraTestConnectionIn(BaseModel):
    components: list[str] | None = Field(
        default=None,
        description="待探测组件 ID；为空则探测全部",
    )


# 连接测试结果。
class InfraTestConnectionOut(BaseModel):
    results: list[InfraComponentStatusOut] = Field(description="探测结果")
