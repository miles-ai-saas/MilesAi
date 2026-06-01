"""业务中心种子：八条服务线阶段模板（全局）。"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.biz import BizServiceLineTemplate
from app.models.biz.template_pack import BizServiceLineTemplatePack

DEFAULT_SERVICE_LINE_STAGES: dict[str, list[str]] = {
    "brand_identity": ["调研", "VI 方案", "升级实施", "手册交付"],
    "video_production": ["脚本", "分镜", "拍摄", "剪辑", "成片"],
    "exhibition": ["概念", "空间布局", "效果图", "施工图", "落地"],
    "event": ["方案", "预算", "执行", "复盘"],
    "training": ["需求", "课程设计", "师资", "执行", "评估"],
    "signage": ["点位规划", "造型设计", "效果图", "工艺清单"],
    "cultural_product": ["产品线规划", "设计", "打样", "量产"],
    "print": ["版式", "装帧", "打样", "印刷", "入库"],
}

DEFAULT_SERVICE_LINE_AI: dict[str, dict] = {
    "brand_identity": {
        "agent_tag": "biz-brand",
        "flow_template_id": "simple_llm",
        "chat_hint": "你正在协助品牌形象/VI 项目，请结合当前阶段给出专业、可落地的建议。",
        "quick_prompts": ["生成 VI 设计说明提纲", "撰写品牌手册章节目录", "比选方案优劣势对比"],
    },
    "video_production": {
        "agent_tag": "biz-video",
        "flow_template_id": "simple_llm",
        "chat_hint": "你正在协助影视拍摄项目，关注脚本、分镜与成片质量。",
        "quick_prompts": ["撰写分镜脚本框架", "提炼宣传片核心卖点", "列出拍摄筹备 checklist"],
    },
    "exhibition": {
        "agent_tag": "biz-exhibition",
        "flow_template_id": "rag",
        "chat_hint": "你正在协助展览展示项目，关注空间叙事与落地可行性。",
        "quick_prompts": ["展陈动线说明", "空间分区功能描述", "材质与工艺建议"],
    },
    "event": {
        "agent_tag": "biz-event",
        "flow_template_id": "simple_llm",
        "chat_hint": "你正在协助活动策划项目，关注方案创意、预算与执行风险。",
        "quick_prompts": ["活动流程时间表", "预算科目拆分建议", "应急预案要点"],
    },
    "training": {
        "agent_tag": "biz-training",
        "flow_template_id": "simple_llm",
        "chat_hint": "你正在协助会务培训项目，关注课程结构与学员体验。",
        "quick_prompts": ["课程大纲草案", "讲师介绍文案", "现场执行分工表"],
    },
    "signage": {
        "agent_tag": "biz-signage",
        "flow_template_id": "simple_llm",
        "chat_hint": "你正在协助标识导视项目，关注信息层级与工艺落地。",
        "quick_prompts": ["导视分级说明", "标识材质工艺表", "安装点位清单模板"],
    },
    "cultural_product": {
        "agent_tag": "biz-cultural",
        "flow_template_id": "simple_llm",
        "chat_hint": "你正在协助文创产品项目，关注产品线规划与打样迭代。",
        "quick_prompts": ["产品线规划表", "产品卖点描述", "包装文案草案"],
    },
    "print": {
        "agent_tag": "biz-print",
        "flow_template_id": "simple_llm",
        "chat_hint": "你正在协助宣传品印刷项目，关注版式、装帧与印刷工艺。",
        "quick_prompts": ["宣传品规格说明", "装帧工艺对比", "印刷色域注意事项"],
    },
}


# 模板市场：场景分类 + 客户类型标签（industry key）
MARKETPLACE_TEMPLATE_PACKS: list[dict] = [
    {
        "category": "exhibition",
        "service_line": "exhibition",
        "name": "政府展馆精简版",
        "description": "适用于政府/国企展馆项目，压缩为概念—效果图—落地三阶段，加快审批节奏。",
        "stages": ["概念方案", "效果图", "落地实施"],
        "ai_config": {
            "agent_tag": "biz-exhibition",
            "flow_template_id": "rag",
            "chat_hint": "政府展馆项目，关注合规表述与空间叙事。",
            "quick_prompts": ["展陈大纲（政务版）", "空间分区说明", "材质环保说明"],
        },
        "publisher_name": "Miles 官方",
        "publisher_type": "platform",
        "tags": ["government"],
        "is_featured": True,
        "sort_order": 10,
    },
    {
        "category": "exhibition",
        "service_line": "exhibition",
        "name": "沉浸式体验全案版",
        "description": "文旅/商业沉浸式展陈，增加数字内容与运营交接阶段。",
        "stages": ["概念", "空间布局", "数字内容", "效果图", "施工图", "落地", "运营交接"],
        "ai_config": {
            "agent_tag": "biz-exhibition",
            "flow_template_id": "rag",
            "chat_hint": "沉浸式体验项目，关注叙事动线与互动装置。",
            "quick_prompts": ["沉浸式动线脚本", "互动装置清单", "运营手册目录"],
        },
        "publisher_name": "Miles 官方",
        "publisher_type": "platform",
        "tags": ["tourism", "commercial"],
        "is_featured": False,
        "sort_order": 20,
    },
    {
        "category": "event",
        "service_line": "event",
        "name": "大型峰会版",
        "description": "千人级峰会/论坛，含嘉宾、媒体与复盘完整链路。",
        "stages": ["策划", "招商赞助", "嘉宾邀约", "现场执行", "媒体传播", "复盘"],
        "ai_config": {
            "agent_tag": "biz-event",
            "flow_template_id": "simple_llm",
            "chat_hint": "大型峰会项目，关注议程、嘉宾与现场管控。",
            "quick_prompts": ["峰会议程草案", "嘉宾接待流程", "应急预案要点"],
        },
        "publisher_name": "Miles 官方",
        "publisher_type": "platform",
        "tags": ["enterprise", "government"],
        "is_featured": True,
        "sort_order": 10,
    },
    {
        "category": "event",
        "service_line": "event",
        "name": "小型沙龙版",
        "description": "50 人以内精品沙龙，三阶段快速交付。",
        "stages": ["方案", "执行", "复盘"],
        "ai_config": {
            "agent_tag": "biz-event",
            "flow_template_id": "simple_llm",
            "chat_hint": "小型沙龙活动，注重体验细节与预算控制。",
            "quick_prompts": ["沙龙流程表", "物料清单", "签到与互动设计"],
        },
        "publisher_name": "Miles 官方",
        "publisher_type": "platform",
        "tags": ["enterprise"],
        "is_featured": False,
        "sort_order": 20,
    },
    {
        "category": "brand",
        "service_line": "brand_identity",
        "name": "快启 VI 精简版",
        "description": "初创/快消品牌快速 VI 交付，压缩调研与实施周期。",
        "stages": ["定位", "VI 核心", "手册交付"],
        "ai_config": {
            "agent_tag": "biz-brand",
            "flow_template_id": "simple_llm",
            "chat_hint": "快启 VI 项目，优先核心识别系统。",
            "quick_prompts": ["品牌定位一句话", "核心 VI 清单", "应用规范摘要"],
        },
        "publisher_name": "Miles 官方",
        "publisher_type": "platform",
        "tags": ["enterprise"],
        "is_featured": True,
        "sort_order": 10,
    },
    {
        "category": "video",
        "service_line": "video_production",
        "name": "短视频快产版",
        "description": "15–60 秒短视频/信息流广告，四阶段快速出片。",
        "stages": ["创意", "脚本", "拍摄", "剪辑出片"],
        "ai_config": {
            "agent_tag": "biz-video",
            "flow_template_id": "simple_llm",
            "chat_hint": "短视频项目，关注前 3 秒钩子与转化。",
            "quick_prompts": ["短视频脚本框架", "分镜表模板", "标题与封面文案"],
        },
        "publisher_name": "Miles 官方",
        "publisher_type": "platform",
        "tags": ["commercial", "enterprise"],
        "is_featured": True,
        "sort_order": 10,
    },
    {
        "category": "training",
        "service_line": "training",
        "name": "企业内训标准版",
        "description": "企业内部培训项目标准五阶段，含评估与跟进。",
        "stages": ["需求调研", "课程设计", "讲师匹配", "现场执行", "效果评估"],
        "ai_config": {
            "agent_tag": "biz-training",
            "flow_template_id": "simple_llm",
            "chat_hint": "企业内训项目，关注学习目标与评估指标。",
            "quick_prompts": ["培训目标 SMART 化", "课程大纲", "评估问卷要点"],
        },
        "publisher_name": "Miles 官方",
        "publisher_type": "partner",
        "tags": ["enterprise"],
        "is_featured": False,
        "sort_order": 10,
    },
    {
        "category": "print",
        "service_line": "print",
        "name": "画册精装版",
        "description": "高端画册/年报印刷，增加装帧工艺与色彩管理阶段。",
        "stages": ["版式", "装帧设计", "工艺打样", "色彩管理", "印刷", "入库"],
        "ai_config": {
            "agent_tag": "biz-print",
            "flow_template_id": "simple_llm",
            "chat_hint": "精装画册项目，关注装帧工艺与色彩还原。",
            "quick_prompts": ["装帧工艺对比", "纸张选型建议", "色彩打样 checklist"],
        },
        "publisher_name": "印刷工艺联盟",
        "publisher_type": "partner",
        "tags": ["enterprise", "government"],
        "is_featured": False,
        "sort_order": 10,
    },
]


async def seed_biz_service_line_template_packs(session: AsyncSession) -> None:
    """幂等写入平台模板市场条目。"""
    for spec in MARKETPLACE_TEMPLATE_PACKS:
        existing = await session.scalar(
            select(BizServiceLineTemplatePack).where(
                BizServiceLineTemplatePack.tenant_id.is_(None),
                BizServiceLineTemplatePack.service_line == spec["service_line"],
                BizServiceLineTemplatePack.name == spec["name"],
            )
        )
        if existing:
            existing.category = spec.get("category", existing.category or "general")
            existing.description = spec.get("description")
            existing.stages = spec["stages"]
            existing.ai_config = spec.get("ai_config", {})
            existing.publisher_name = spec.get("publisher_name", "Miles 官方")
            existing.publisher_type = spec.get("publisher_type", "platform")
            existing.tags = spec.get("tags", [])
            existing.is_featured = spec.get("is_featured", False)
            existing.sort_order = spec.get("sort_order", 0)
            existing.is_active = True
            existing.status = "published"
            continue
        session.add(
            BizServiceLineTemplatePack(
                tenant_id=None,
                category=spec.get("category", "general"),
                service_line=spec["service_line"],
                name=spec["name"],
                description=spec.get("description"),
                stages=spec["stages"],
                ai_config=spec.get("ai_config", {}),
                publisher_name=spec.get("publisher_name", "Miles 官方"),
                publisher_type=spec.get("publisher_type", "platform"),
                tags=spec.get("tags", []),
                is_featured=spec.get("is_featured", False),
                sort_order=spec.get("sort_order", 0),
                is_active=True,
                status="published",
            )
        )
    await session.flush()


async def seed_biz_service_line_templates(session: AsyncSession) -> None:
    """幂等写入全局服务线阶段模板。"""
    for service_line, stages in DEFAULT_SERVICE_LINE_STAGES.items():
        existing = await session.scalar(
            select(BizServiceLineTemplate).where(
                BizServiceLineTemplate.tenant_id.is_(None),
                BizServiceLineTemplate.service_line == service_line,
            )
        )
        if existing:
            existing.stages = stages
            existing.ai_config = DEFAULT_SERVICE_LINE_AI.get(service_line, {})
            existing.is_active = True
            continue
        session.add(
            BizServiceLineTemplate(
                tenant_id=None,
                service_line=service_line,
                stages=stages,
                ai_config=DEFAULT_SERVICE_LINE_AI.get(service_line, {}),
                is_active=True,
            )
        )
    await session.flush()
