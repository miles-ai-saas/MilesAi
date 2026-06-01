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
            existing.is_active = True
            continue
        session.add(
            BizServiceLineTemplate(
                tenant_id=None,
                service_line=service_line,
                stages=stages,
                is_active=True,
            )
        )
    await session.flush()
