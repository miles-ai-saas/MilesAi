"""内置豆包（火山方舟）模型条目。

数据来源：https://www.volcengine.com/docs/82379/1099475
"""

from __future__ import annotations

from miles_core.models.model.catalog import ModelCapabilityType, ModelVendor


ENTRIES: list[dict] = [
# --- 豆包（火山方舟 OpenAI 兼容，model 填模型 ID 或接入点 ep-xxx）---
    {
        "model_code": "doubao-seed-evolving",
        "name": "豆包-Seed-Evolving",
        "vendor": ModelVendor.DOUBAO.value,
        "provider": "doubao",
        "model_name": "doubao-seed-evolving",
        "model_type": ModelCapabilityType.LLM.value,
        "description": "Seed 最新 Coding & Agent 模型，周级迭代；1M 上下文，深度思考、多模态与工具调用。",
        "context_window": "1M",
        "badge": "latest",
        "sort_order": 20,
        "is_featured": True,
    },
    {
        "model_code": "doubao-seed-2-1-pro-260915",
        "name": "豆包-Seed-2.1-Pro",
        "vendor": ModelVendor.DOUBAO.value,
        "provider": "doubao",
        "model_name": "doubao-seed-2-1-pro-260915",
        "model_type": ModelCapabilityType.LLM.value,
        "description": "Seed 2.1 生产级旗舰，全面升级 Coding、Agent 与多模态，1M 上下文。",
        "context_window": "1M",
        "sort_order": 21,
        "is_featured": True,
    },
    {
        "model_code": "doubao-seed-2-1-lite-260915",
        "name": "豆包-Seed-2.1-Lite",
        "vendor": ModelVendor.DOUBAO.value,
        "provider": "doubao",
        "model_name": "doubao-seed-2-1-lite-260915",
        "model_type": ModelCapabilityType.LLM.value,
        "description": "Seed 2.1 全模态轻量版，1M 上下文，高吞吐与性价比。",
        "context_window": "1M",
        "sort_order": 22,
        "is_featured": True,
    },
    {
        "model_code": "doubao-seed-2-1-turbo-260628",
        "name": "豆包-Seed-2.1-Turbo",
        "vendor": ModelVendor.DOUBAO.value,
        "provider": "doubao",
        "model_name": "doubao-seed-2-1-turbo-260628",
        "model_type": ModelCapabilityType.LLM.value,
        "description": "Seed 2.1 效果与成本均衡版，支持 fast 服务档，256K 上下文。",
        "context_window": "256K",
        "sort_order": 23,
    },
    {
        "model_code": "doubao-seedream-5-0-pro-260628",
        "name": "豆包-Seedream-5.0-Pro",
        "vendor": ModelVendor.DOUBAO.value,
        "provider": "doubao",
        "model_name": "doubao-seedream-5-0-pro-260628",
        "model_type": ModelCapabilityType.IMAGE_GEN.value,
        "description": "Seedream 5.0 Pro 图像创作，文生图 / 图生图 / 多参考图，编辑更可控。",
        "context_window": "—",
        "sort_order": 24,
        "is_featured": True,
    },
    {
        "model_code": "doubao-seedream-5-0-flash-260915",
        "name": "豆包-Seedream-5.0-Flash",
        "vendor": ModelVendor.DOUBAO.value,
        "provider": "doubao",
        "model_name": "doubao-seedream-5-0-flash-260915",
        "model_type": ModelCapabilityType.IMAGE_GEN.value,
        "description": "Seedream 5.0 Flash，更快的文生图 / 图生图。",
        "context_window": "—",
        "sort_order": 25,
    },
    {
        "model_code": "doubao-seedance-2-5-260628",
        "name": "豆包-Seedance-2.5",
        "vendor": ModelVendor.DOUBAO.value,
        "provider": "doubao",
        "model_name": "doubao-seedance-2-5-260628",
        "model_type": ModelCapabilityType.VIDEO_GEN.value,
        "description": "Seedance 2.5 全模态参考生视频，最长约 30 秒，最高 1080p。",
        "context_window": "—",
        "sort_order": 26,
    },
]
