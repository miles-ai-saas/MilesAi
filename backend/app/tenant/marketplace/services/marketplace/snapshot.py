"""安装快照：安装/升级前写入，回滚时恢复。"""

from uuid import UUID

from sqlalchemy import select

from app.common.exceptions import BadRequestError
from app.tenant.marketplace.models import AppInstall, AppInstallSnapshot
from app.tenant.marketplace.util.install_resources import (
    apply_resources_to_install,
    capture_install_resources,
)

_MAX_SNAPSHOTS_PER_INSTALL = 10


class MarketplaceSnapshotMixin:
    """安装资源快照读写。"""

    async def _save_install_snapshot(self, install: AppInstall, *, version: str) -> None:
        """保存当前资源状态为快照（升级前或安装后）。"""
        resources = await capture_install_resources(self.db, self.ctx, install)
        snap = AppInstallSnapshot(
            install_id=install.id,
            tenant_id=install.tenant_id,
            app_id=install.app_id,
            version=version,
            resources=resources,
        )
        self.db.add(snap)
        await self.db.flush()
        await self._trim_install_snapshots(install.id)

    async def _trim_install_snapshots(self, install_id: UUID) -> None:
        """每安装记录最多保留最近 N 条快照。"""
        stmt = select(AppInstallSnapshot).where(AppInstallSnapshot.install_id == install_id).order_by(AppInstallSnapshot.created_at.desc())
        rows = (await self.db.execute(stmt)).scalars().all()
        for extra in rows[_MAX_SNAPSHOTS_PER_INSTALL:]:
            await self.db.delete(extra)

    async def _get_latest_snapshot(self, install_id: UUID) -> AppInstallSnapshot | None:
        stmt = (
            select(AppInstallSnapshot)
            .where(
                AppInstallSnapshot.install_id == install_id,
                AppInstallSnapshot.tenant_id == self.ctx.tenant_id,
            )
            .order_by(AppInstallSnapshot.created_at.desc())
            .limit(1)
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def _restore_latest_snapshot(self, install: AppInstall) -> AppInstallSnapshot:
        snap = await self._get_latest_snapshot(install.id)
        if not snap:
            raise BadRequestError("没有可回滚的历史版本")
        await apply_resources_to_install(
            self.db,
            self.ctx,
            install,
            snap.resources or {},
            remark=f"市场回滚 v{snap.version}",
        )
        install.installed_version = snap.version
        await self.db.delete(snap)
        await self.db.flush()
        return snap
