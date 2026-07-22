"""租户运行监控：资源统计、任务趋势、依赖健康与告警 Webhook。"""

import asyncio
import csv
import io
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx
from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.service import BaseService
from app.core.soft_delete import append_not_deleted
from app.core.tenant import TenantContext, tenant_filters
from app.models.agent import Agent
from app.models.flow import Flow
from app.models.kb import Document, DocumentStatus, KnowledgeBase
from app.models.model.usage_log import ModelUsageLog
from app.models.platform.system import SystemConfig
from app.models.task.task_record import CeleryTaskRecord
from app.tenant.compliance.models import InterceptLog
from app.tenant.marketplace.models import AppInstall
from app.tenant.monitor.meta import monitor_meta_dict
from app.tenant.monitor.schemas.meta import MonitorMetaOut
from app.tenant.monitor.schemas.monitor import (
    AlertConfig,
    ModelUsageReport,
    ModelUsageRow,
    MonitorReport,
    MonitorStats,
    MonitorTrends,
    TaskTrendPoint,
)
from app.tenant.tasks.schemas.task import TaskSummary
from app.utils.health_checks import collect_health_status

logger = get_logger(__name__)

ALERT_CONFIG_KEY = "monitor.alert"


class MonitorService(BaseService):
    """工作台监控页：租户资源统计、Celery 任务趋势、健康检查与告警配置。"""

    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)

    async def get_meta(self) -> MonitorMetaOut:
        """返回枚举展示字典（无 DB 查询，文案来自 tenant/*/meta.py）。"""
        return MonitorMetaOut.model_validate(monitor_meta_dict())

    async def stats(self) -> MonitorStats:
        """快捷返回 report.stats。"""
        report = await self.report()
        return report.stats

    async def _task_summary(self) -> TaskSummary:
        """按状态统计租户 Celery 任务数量（单次 GROUP BY 查询）。"""
        filters = tenant_filters(self.ctx, CeleryTaskRecord.tenant_id)
        rows = await self.db.execute(
            select(CeleryTaskRecord.status, func.count(CeleryTaskRecord.id))
            .where(*filters)
            .group_by(CeleryTaskRecord.status)
        )
        status_map: dict[str, int] = {row[0].value if hasattr(row[0], "value") else str(row[0]): int(row[1]) for row in rows.all()}

        total = sum(status_map.values())
        return TaskSummary(
            total=total,
            pending=status_map.get("pending", 0),
            running=status_map.get("running", 0),
            success=status_map.get("success", 0),
            failed=status_map.get("failed", 0),
            cancelled=status_map.get("cancelled", 0),
        )

    async def report(self) -> MonitorReport:
        """聚合租户资源统计、任务摘要、文档状态与多模态处理量。"""
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
        logs_today = await self.db.scalar(select(func.count()).select_from(InterceptLog).where(*log_f, InterceptLog.created_at >= today_start))
        pending = await self.db.scalar(
            select(func.count())
            .select_from(Document)
            .where(
                *doc_f,
                Document.status.in_([DocumentStatus.PENDING, DocumentStatus.PARSING, DocumentStatus.EMBEDDING]),
            )
        )
        installs = await self.db.scalar(select(func.count()).select_from(AppInstall).where(*install_f))

        # 多模态处理量：按 mime_type 前缀统计
        image_docs = await self.db.scalar(select(func.count()).select_from(Document).where(*doc_f, Document.mime_type.like("image/%")))
        audio_docs = await self.db.scalar(select(func.count()).select_from(Document).where(*doc_f, Document.mime_type.like("audio/%")))
        video_docs = await self.db.scalar(select(func.count()).select_from(Document).where(*doc_f, Document.mime_type.like("video/%")))

        doc_status_rows = await self.db.execute(select(Document.status, func.count()).where(*doc_f).group_by(Document.status))
        documents_by_status = {(row[0].value if hasattr(row[0], "value") else str(row[0])): row[1] for row in doc_status_rows.all()}

        stats = MonitorStats(
            knowledge_bases=kbs or 0,
            documents=docs or 0,
            image_documents=image_docs or 0,
            audio_documents=audio_docs or 0,
            video_documents=video_docs or 0,
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
        """导出 report 为 CSV 字符串。"""
        report = await self.report()
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["指标", "数值"])
        writer.writerow(["知识库", report.stats.knowledge_bases])
        writer.writerow(["文档", report.stats.documents])
        writer.writerow(["图片(OCR)", report.stats.image_documents])
        writer.writerow(["音频(Whisper)", report.stats.audio_documents])
        writer.writerow(["视频", report.stats.video_documents])
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
        """委托 health_checks.collect_health_status 探测依赖组件。"""
        return await collect_health_status()

    async def get_alert_config(self) -> AlertConfig:
        """读取租户级 monitor.alert 系统配置。"""
        row = await self.db.scalar(select(SystemConfig).where(SystemConfig.key == ALERT_CONFIG_KEY))
        if not row or not row.value:
            return AlertConfig()
        return AlertConfig.model_validate(row.value)

    async def save_alert_config(self, body: AlertConfig) -> AlertConfig:
        """写入或更新 monitor.alert 配置。"""
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

    async def _send_alert_email(self, body: AlertConfig, subject: str, message: str) -> dict:
        """发送告警邮件，未配置 SMTP 时跳过。"""
        settings = get_settings()
        if not body.email_notify_to or not settings.smtp_host:
            return {"ok": False, "message": "未配置邮件收件人或 SMTP"}

        recipients = [addr.strip() for addr in body.email_notify_to.split(",") if addr.strip()]
        if not recipients:
            return {"ok": False, "message": "邮件收件人列表为空"}

        msg = MIMEMultipart()
        msg["From"] = settings.smtp_from
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = f"[MilesAi] {subject}"
        msg.attach(MIMEText(message, "plain", "utf-8"))

        def _send():
            if settings.smtp_tls:
                server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10)
                server.starttls()
            else:
                server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=10)
            try:
                if settings.smtp_user:
                    server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(msg)
            finally:
                server.quit()

        try:
            await asyncio.to_thread(_send)
            return {"ok": True, "message": f"已发送至 {len(recipients)} 位收件人"}
        except Exception as exc:
            return {"ok": False, "message": f"邮件发送失败: {exc}"}

    async def test_alert(self, body: AlertConfig) -> dict:
        """向配置的 Webhook / 邮件收件人发送测试告警。"""
        results = {}

        # Webhook 测试
        if body.webhook_url:
            payload = {
                "event": "test",
                "tenant_id": str(self.ctx.tenant_id),
                "message": "MilesAi 监控告警测试",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.post(body.webhook_url, json=payload)
                results["webhook"] = {"ok": resp.is_success, "status": resp.status_code}
            except Exception as exc:
                results["webhook"] = {"ok": False, "message": str(exc)}
        else:
            results["webhook"] = {"ok": False, "message": "未配置 webhook_url"}

        # 邮件测试
        if body.email_notify_to:
            email_result = await self._send_alert_email(
                body,
                subject="告警测试",
                message=f"租户 {self.ctx.tenant_id} 监控告警通道测试成功。\n时间: {datetime.now(timezone.utc).isoformat()}",
            )
            results["email"] = email_result

        return results

    async def trends(self, *, days: int = 7) -> MonitorTrends:
        """按日聚合 Celery 任务与合规拦截趋势（最多 30 天）。"""
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
            select(cast(InterceptLog.created_at, Date).label("day"), func.count(InterceptLog.id)).where(*log_f).group_by(cast(InterceptLog.created_at, Date))
        )
        intercept_by_day = [{"date": (d.isoformat() if hasattr(d, "isoformat") else str(d)), "count": int(c)} for d, c in log_rows.all()]

        return MonitorTrends(
            task_by_day=sorted(by_day.values(), key=lambda x: x.date),
            intercept_by_day=sorted(intercept_by_day, key=lambda x: str(x["date"])),
        )

    async def model_usage(self, *, days: int = 7) -> ModelUsageReport:
        """按模型聚合 Token 用量（ModelUsageLog）。"""
        days = max(1, min(days, 30))
        start = datetime.now(timezone.utc) - timedelta(days=days - 1)
        filters = tenant_filters(self.ctx, ModelUsageLog.tenant_id)
        filters.append(ModelUsageLog.created_at >= start)
        rows = await self.db.execute(
            select(
                ModelUsageLog.model_config_id,
                ModelUsageLog.model_name,
                func.count(ModelUsageLog.id),
                func.coalesce(func.sum(ModelUsageLog.prompt_tokens), 0),
                func.coalesce(func.sum(ModelUsageLog.completion_tokens), 0),
                func.coalesce(func.sum(ModelUsageLog.total_tokens), 0),
            )
            .where(*filters)
            .group_by(ModelUsageLog.model_config_id, ModelUsageLog.model_name)
            .order_by(func.sum(ModelUsageLog.total_tokens).desc())
        )
        items: list[ModelUsageRow] = []
        total_tokens = 0
        for model_id, name, cnt, prompt, completion, total in rows.all():
            t = int(total or 0)
            total_tokens += t
            items.append(
                ModelUsageRow(
                    model_config_id=model_id,
                    model_name=name or "未知模型",
                    call_count=int(cnt or 0),
                    prompt_tokens=int(prompt or 0),
                    completion_tokens=int(completion or 0),
                    total_tokens=t,
                )
            )
        return ModelUsageReport(days=days, rows=items, total_tokens=total_tokens)

    async def notify_task_failed(self, task_name: str, fail_reason: str) -> None:
        """Celery 任务失败时按配置推送 Webhook（静默忽略发送错误）。"""
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
            logger.warning(
                "任务失败告警 Webhook 发送失败 tenant_id=%s task_name=%s",
                self.ctx.tenant_id,
                task_name,
                exc_info=True,
            )
