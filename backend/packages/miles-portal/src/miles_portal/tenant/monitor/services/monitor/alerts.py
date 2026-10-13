"""监控告警：配置、Webhook/邮件推送。"""

from __future__ import annotations

import asyncio
import smtplib
from datetime import UTC, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx
from sqlalchemy import select

from miles_core.config import get_settings
from miles_core.logging import get_logger
from miles_core.models.platform.system import SystemConfig
from miles_portal.tenant.monitor.schemas.monitor import AlertConfig
from miles_portal.tenant.monitor.services.monitor.constants import ALERT_CONFIG_KEY, alert_config_key

logger = get_logger(__name__)


class MonitorAlertsMixin:
    async def get_alert_config(self) -> AlertConfig:
        """读取租户级 monitor.alert 配置（兼容旧全局键）。"""
        key = alert_config_key(self.ctx.tenant_id)
        row = await self.db.scalar(select(SystemConfig).where(SystemConfig.key == key))
        if (not row or not row.value) and key != ALERT_CONFIG_KEY:
            row = await self.db.scalar(select(SystemConfig).where(SystemConfig.key == ALERT_CONFIG_KEY))
        if not row or not row.value:
            return AlertConfig()
        return AlertConfig.model_validate(row.value)

    async def save_alert_config(self, body: AlertConfig) -> AlertConfig:
        """写入或更新当前租户的 monitor.alert 配置。"""
        key = alert_config_key(self.ctx.tenant_id)
        row = await self.db.scalar(select(SystemConfig).where(SystemConfig.key == key))
        if row:
            row.value = body.model_dump()
        else:
            row = SystemConfig(
                key=key,
                value=body.model_dump(),
                description="监控告警 Webhook 配置（租户级）",
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
                "timestamp": datetime.now(UTC).isoformat(),
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
                message=f"租户 {self.ctx.tenant_id} 监控告警通道测试成功。\n时间: {datetime.now(UTC).isoformat()}",
            )
            results["email"] = email_result

        return results

    async def _post_alert_webhook(self, cfg: AlertConfig, payload: dict) -> None:
        """向配置的 Webhook 发送 JSON；失败仅记日志。"""
        if not cfg.webhook_url:
            return
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(cfg.webhook_url, json=payload)
        except Exception:
            logger.warning(
                "告警 Webhook 发送失败 tenant_id=%s event=%s",
                self.ctx.tenant_id,
                payload.get("event"),
                exc_info=True,
            )

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
            "timestamp": datetime.now(UTC).isoformat(),
        }
        await self._post_alert_webhook(cfg, payload)

    async def notify_tokens_monthly_threshold(
        self,
        *,
        used: int,
        limit: int,
        percent: int,
        warn_percent: int,
        cfg: AlertConfig | None = None,
    ) -> None:
        """本月 Token 达阈值时推送 Webhook / 邮件（静默忽略发送错误）。"""
        cfg = cfg or await self.get_alert_config()
        if not cfg.enabled or not cfg.notify_on_tokens_monthly_threshold:
            return
        if not cfg.webhook_url and not cfg.email_notify_to:
            return
        now = datetime.now(UTC).isoformat()
        message = (
            f"租户 {self.ctx.tenant_id} 本月 Token 已用 {used}/{limit}（{percent}%），"
            f"达到告警阈值 {warn_percent}%。"
        )
        payload = {
            "event": "tokens_monthly_threshold",
            "tenant_id": str(self.ctx.tenant_id),
            "tokens_used": used,
            "tokens_max": limit,
            "percent": percent,
            "warn_percent": warn_percent,
            "message": message,
            "timestamp": now,
        }
        await self._post_alert_webhook(cfg, payload)
        if cfg.email_notify_to:
            await self._send_alert_email(cfg, subject="本月 Token 用量告警", message=f"{message}\n时间: {now}")

