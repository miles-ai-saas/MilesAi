"""租户运行监控：资源统计、任务趋势、依赖健康与告警 Webhook。"""

import csv
import io
from datetime import datetime, timezone

import httpx
from datetime import timedelta

from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.health_checks import collect_health_status
from app.core.tenant import TenantContext, tenant_filters
from app.models.agent import Agent
from app.tenant.compliance.models import InterceptLog
from app.models.flow import Flow
from app.models.kb import Document, DocumentStatus, KnowledgeBase
from app.tenant.marketplace.models import AppInstall
from app.models.system import SystemConfig
from app.core.soft_delete import append_not_deleted
from app.models.task import CeleryTaskRecord, TaskStatus
from app.tenant.monitor.schemas.monitor import (
    AlertConfig,
    MonitorReport,
    MonitorStats,
    MonitorTrends,
    TaskTrendPoint,
)
from app.tenant.tasks.schemas.task import TaskSummary
from app.core.soft_delete import append_not_deleted
from app.core.service import BaseService

ALERT_CONFIG_KEY = "monitor.alert"


class MonitorService(BaseService):
    """工作台监控页：租户资源统计、Celery 任务趋势、健康检查与告警配置。"""

    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)

    async def stats(self) -> MonitorStats:
        """快捷返回 report.stats。"""
        report = await self.report()
        return report.stats

    async def _task_summary(self) -> TaskSummary:
        filters = tenant_filters(self.ctx, CeleryTaskRecord.tenant_id)
        summary = TaskSummary()
        for status in TaskStatus:
            count = await self.db.scalar(
                select(func.count())
                .select_from(CeleryTaskRecord)
                .where(*filters, CeleryTaskRecord.status == status)
            )
            n = count or 0
            summary.total += n
            if status == TaskStatus.PENDING:
                summary.pending = n
            elif status == TaskStatus.RUNNING:
                summary.running = n
            elif status == TaskStatus.SUCCESS:
                summary.success = n
            elif status == TaskStatus.FAILED:
                summary.failed = n
            elif status == TaskStatus.CANCELLED:
                summary.cancelled = n
        return summary

    async def report(self) -> MonitorReport:
        kb_f = append_not_deleted(tenant_filters(self.ctx, KnowledgeBase.tenant_id), KnowledgeBase)
        doc_f = append_not_deleted(tenant_filters(self.ctx, Document.tenant_id), Document)
        agent_f = append_not_deleted(tenant_filters(self.ctx, Agent.tenant_id), Agent)
        flow_f = append_not_deleted(tenant_filters(self.ctx, Flow.tenant_id), Flow)
        log_f = tenant_filters(self.ctx, InterceptLog.tenant_id)
        install_f = tenant_filters(self.ctx, AppInstall.tenant_id)

        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

        kbs = await self.db.scalar(select(func.count()).select_from(KnowledgeBase).where(*kb_f))
        docs = await self.db.scalar(select(func.count()).select_from(Document).where(*doc_f))
        agents = await self.db.scalar(select(func.count()).select_from(Agent).where(*agent_f))
        flows = await self.db.scalar(select(func.count()).select_from(Flow).where(*flow_f))
        logs_today = await self.db.scalar(
            select(func.count())
            .select_from(InterceptLog)
            .where(*log_f, InterceptLog.created_at >= today_start)
        )
        pending = await self.db.scalar(
            select(func.count())
            .select_from(Document)
            .where(
                *doc_f,
                Document.status.in_(
                    [DocumentStatus.PENDING, DocumentStatus.PARSING, DocumentStatus.EMBEDDING]
                ),
            )
        )
        installs = await self.db.scalar(select(func.count()).select_from(AppInstall).where(*install_f))

        doc_status_rows = await self.db.execute(
            select(Document.status, func.count())
            .where(*doc_f)
            .group_by(Document.status)
        )
        documents_by_status = {
            (row[0].value if hasattr(row[0], "value") else str(row[0])): row[1]
            for row in doc_status_rows.all()
        }

        stats = MonitorStats(
            knowledge_bases=kbs or 0,
            documents=docs or 0,
            agents=agents or 0,
            flows=flows or 0,
            intercept_logs_today=logs_today or 0,
            pending_documents=pending or 0,
        )
        return MonitorReport(
            stats=stats,
            tasks=await self._task_summary(),
            documents_by_status=documents_by_status,
            marketplace_installs=installs or 0,
        )

    async def export_report_csv(self) -> str:
        report = await self.report()
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["指标", "数值"])
        writer.writerow(["知识库", report.stats.knowledge_bases])
        writer.writerow(["文档", report.stats.documents])
        writer.writerow(["智能体", report.stats.agents])
        writer.writerow(["流程", report.stats.flows])
        writer.writerow(["今日拦截", report.stats.intercept_logs_today])
        writer.writerow(["待处理文档", report.stats.pending_documents])
        writer.writerow(["应用安装数", report.marketplace_installs])
        writer.writerow([])
        writer.writerow(["任务状态", "数量"])
        writer.writerow(["pending", report.tasks.pending])
        writer.writerow(["running", report.tasks.running])
        writer.writerow(["success", report.tasks.success])
        writer.writerow(["failed", report.tasks.failed])
        writer.writerow(["cancelled", report.tasks.cancelled])
        writer.writerow([])
        writer.writerow(["文档状态", "数量"])
        for status, count in report.documents_by_status.items():
            writer.writerow([status, count])
        return buf.getvalue()

    async def health(self) -> dict:
        return await collect_health_status()

    async def get_alert_config(self) -> AlertConfig:
        row = await self.db.scalar(select(SystemConfig).where(SystemConfig.key == ALERT_CONFIG_KEY))
        if not row or not row.value:
            return AlertConfig()
        return AlertConfig.model_validate(row.value)

    async def save_alert_config(self, body: AlertConfig) -> AlertConfig:
        row = await self.db.scalar(select(SystemConfig).where(SystemConfig.key == ALERT_CONFIG_KEY))
        if row:
            row.value = body.model_dump()
        else:
            row = SystemConfig(
                key=ALERT_CONFIG_KEY,
                value=body.model_dump(),
                description="监控告警 Webhook 配置",
            )
            self.db.add(row)
        await self.db.flush()
        return body

    async def test_alert(self, body: AlertConfig) -> dict:
        if not body.webhook_url:
            return {"ok": False, "message": "未配置 webhook_url"}
        payload = {
            "event": "test",
            "tenant_id": str(self.ctx.tenant_id),
            "message": "MilesAi 监控告警测试",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(body.webhook_url, json=payload)
            return {"ok": resp.is_success, "status": resp.status_code}
        except Exception as exc:
            return {"ok": False, "message": str(exc)}

    async def trends(self, *, days: int = 7) -> MonitorTrends:
        days = max(1, min(days, 30))
        start = datetime.now(timezone.utc) - timedelta(days=days - 1)
        task_f = append_not_deleted(
            tenant_filters(self.ctx, CeleryTaskRecord.tenant_id),
            CeleryTaskRecord,
        )
        task_f.append(CeleryTaskRecord.created_at >= start)

        rows = await self.db.execute(
            select(
                cast(CeleryTaskRecord.created_at, Date).label("day"),
                CeleryTaskRecord.status,
                func.count(CeleryTaskRecord.id),
            )
            .where(*task_f)
            .group_by(cast(CeleryTaskRecord.created_at, Date), CeleryTaskRecord.status)
        )
        by_day: dict[str, TaskTrendPoint] = {}
        for day, status, cnt in rows.all():
            key = day.isoformat() if hasattr(day, "isoformat") else str(day)
            if key not in by_day:
                by_day[key] = TaskTrendPoint(date=key)
            p = by_day[key]
            n = int(cnt)
            p.total += n
            st = status.value if hasattr(status, "value") else str(status)
            if st == "pending":
                p.pending += n
            elif st == "running":
                p.running += n
            elif st == "success":
                p.success += n
            elif st == "failed":
                p.failed += n
            elif st == "cancelled":
                p.cancelled += n

        log_f = append_not_deleted(tenant_filters(self.ctx, InterceptLog.tenant_id), InterceptLog)
        log_f.append(InterceptLog.created_at >= start)
        log_rows = await self.db.execute(
            select(cast(InterceptLog.created_at, Date).label("day"), func.count(InterceptLog.id))
            .where(*log_f)
            .group_by(cast(InterceptLog.created_at, Date))
        )
        intercept_by_day = [
            {"date": (d.isoformat() if hasattr(d, "isoformat") else str(d)), "count": int(c)}
            for d, c in log_rows.all()
        ]

        return MonitorTrends(
            task_by_day=sorted(by_day.values(), key=lambda x: x.date),
            intercept_by_day=sorted(intercept_by_day, key=lambda x: str(x["date"])),
        )

    async def notify_task_failed(self, task_name: str, fail_reason: str) -> None:
        cfg = await self.get_alert_config()
        if not cfg.enabled or not cfg.webhook_url or not cfg.notify_on_task_failed:
            return
        payload = {
            "event": "task_failed",
            "tenant_id": str(self.ctx.tenant_id),
            "task_name": task_name,
            "fail_reason": fail_reason[:500],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(cfg.webhook_url, json=payload)
        except Exception:
            pass
