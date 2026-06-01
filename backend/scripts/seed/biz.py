"""业务中心种子：八条服务线阶段模板（全局）。"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.biz import BizServiceLineTemplate

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
