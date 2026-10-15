"""内置 DeepSeek 模型条目。

数据来源：https://api-docs.deepseek.com/quick_start/pricing
"""

from __future__ import annotations

from miles_core.models.model.catalog import ModelCapabilityType, ModelVendor


ENTRIES: list[dict] = [
# --- 深度求索 ---
    {
        "model_code": "deepseek-flash",
        "name": "DeepSeek-Flash",
        "vendor": ModelVendor.DEEPSEEK.value,
        "provider": "deepseek",
        "model_name": "deepseek-flash",
        "model_type": ModelCapabilityType.LLM.value,
        "description": "DeepSeek-V4.1-Flash，1M 上下文，原生多模态，支持思考/非思考；默认对话与高性价比场景。",
        "context_window": "1M",
        "badge": "latest",
        "sort_order": 10,
        "is_featured": True,
    },
    {
        "model_code": "deepseek-v4-pro",
        "name": "DeepSeek-V4-Pro",
        "vendor": ModelVendor.DEEPSEEK.value,
        "provider": "deepseek",
        "model_name": "deepseek-v4-pro",
        "model_type": ModelCapabilityType.LLM.value,
        "description": "V4 Pro 旗舰（V4-Pro-0813），1M 上下文，支持思考模式，适合复杂推理与编程。",
        "context_window": "1M",
        "sort_order": 11,
        "is_featured": True,
    },
]
