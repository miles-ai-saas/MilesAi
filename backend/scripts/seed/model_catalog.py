"""内置大模型目录（深度求索 / 豆包 / 通义千问）。"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.model import ModelConfig
from app.models.model_catalog import (
    DEFAULT_API_BASES,
    ModelCapabilityType,
    ModelPublishStatus,
    ModelVendor,
)

BUILTIN_CATALOG: list[dict] = [
    {
        "model_code": "deepseek-chat",
        "name": "DeepSeek-V3",
        "vendor": ModelVendor.DEEPSEEK.value,
        "provider": "deepseek",
        "model_name": "deepseek-chat",
        "model_type": ModelCapabilityType.LLM.value,
        "description": "深度求索旗舰对话模型，长上下文，适合通用问答与代码。",
        "context_window": "128K",
        "badge": "latest",
        "sort_order": 10,
        "is_featured": True,
    },
    {
        "model_code": "deepseek-reasoner",
        "name": "DeepSeek-R1",
        "vendor": ModelVendor.DEEPSEEK.value,
        "provider": "deepseek",
        "model_name": "deepseek-reasoner",
        "model_type": ModelCapabilityType.REASONING.value,
        "description": "深度求索推理模型，适合复杂分析与链式思考任务。",
        "context_window": "128K",
        "sort_order": 20,
        "is_featured": True,
    },
    {
        "model_code": "doubao-pro-32k",
        "name": "豆包-Pro",
        "vendor": ModelVendor.DOUBAO.value,
        "provider": "doubao",
        "model_name": "doubao-pro-32k",
        "model_type": ModelCapabilityType.LLM.value,
        "description": "字节豆包大模型，火山方舟 OpenAI 兼容接口。",
        "context_window": "32K",
        "sort_order": 30,
        "is_featured": True,
    },
    {
        "model_code": "qwen-plus",
        "name": "通义千问-Plus",
        "vendor": ModelVendor.QWEN.value,
        "provider": "qwen",
        "model_name": "qwen-plus",
        "model_type": ModelCapabilityType.LLM.value,
        "description": "阿里云通义千问增强版，均衡能力与成本。",
        "context_window": "128K",
        "badge": "latest",
        "sort_order": 40,
        "is_featured": True,
    },
    {
        "model_code": "qwen-turbo",
        "name": "通义千问-Turbo",
        "vendor": ModelVendor.QWEN.value,
        "provider": "qwen",
        "model_name": "qwen-turbo",
        "model_type": ModelCapabilityType.LLM.value,
        "description": "通义千问高速版，适合低延迟对话场景。",
        "context_window": "128K",
        "sort_order": 50,
    },
]


async def seed_model_catalog(session: AsyncSession) -> None:
    for item in BUILTIN_CATALOG:
        code = item["model_code"]
        existing = (
            await session.execute(
                select(ModelConfig).where(
                    ModelConfig.tenant_id.is_(None),
                    ModelConfig.model_code == code,
                )
            )
        ).scalar_one_or_none()
        if existing:
            continue
        vendor = item["vendor"]
        session.add(
            ModelConfig(
                tenant_id=None,
                name=item["name"],
                provider=item["provider"],
                model_name=item["model_name"],
                model_code=code,
                vendor=vendor,
                model_type=item["model_type"],
                description=item.get("description"),
                context_window=item.get("context_window"),
                capabilities=[],
                publish_status=ModelPublishStatus.PUBLISHED.value,
                is_featured=item.get("is_featured", False),
                badge=item.get("badge"),
                sort_order=item.get("sort_order", 0),
                api_base=DEFAULT_API_BASES.get(vendor),
                is_active=True,
                extra={},
            )
        )
