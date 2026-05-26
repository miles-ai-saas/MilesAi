"""
A2A Peer 登记用例（L2）：拉取 Agent Card、探测 RPC 与状态维护。

状态机
------
``PENDING`` → 同步 Card 成功 → ``ACTIVE``；失败记 ``last_error`` 为 ``ERROR``。

下游：CUSTOM Agent 通过 ``peer_refs`` 引用；A2A 宿主通过 ``host_bindings`` 绑定。
对话 HTTP 不在本 Service，见 ``tenant.a2a.invoke`` + ``client.invoke_a2a_peer``。
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.tenant.a2a.card_client import (
    card_display_name,
    count_card_skills,
    fetch_agent_card,
    resolve_agent_card_url,
)
from app.tenant.a2a.models import A2aPeer, A2aPeerStatus
from app.tenant.a2a.meta import a2a_meta_dict
from app.tenant.a2a.schemas.meta import A2aMetaOut
from app.tenant.a2a.schemas.peer import (
    A2aPeerCreate,
    A2aPeerOut,
    A2aPeerProbeResult,
    A2aPeerSyncResult,
    A2aPeerUpdate,
)
from app.common.exceptions import BadRequestError, NotFoundError
from app.common.schema import PageParams, PageResult
from app.core.service import BaseService
from app.core.soft_delete import is_marked_deleted, mark_deleted, not_deleted
from app.core.tenant import TenantContext, assert_tenant_access, tenant_filters


def _peer_out(row: A2aPeer) -> A2aPeerOut:
    """ORM → API 出参。"""
    card = row.agent_card_json or {}
    return A2aPeerOut(
        id=row.id,
        tenant_id=row.tenant_id,
        name=row.name,
        description=row.description,
        base_url=row.base_url,
        agent_card_url=row.agent_card_url,
        card_display_name=row.card_display_name,
        status=row.status,
        skills_count=count_card_skills(card),
        last_synced_at=row.last_synced_at,
        last_error=row.last_error,
        created_at=row.created_at,
    )


class A2aPeerService(BaseService):
    """租户级外部 A2A Agent 目录 CRUD 与 Card 同步。"""

    def __init__(self, db: AsyncSession, ctx: TenantContext) -> None:
        super().__init__(db, ctx)

    async def get_meta(self) -> A2aMetaOut:
        """返回枚举展示字典（无 DB 查询，文案来自 tenant/*/meta.py）。"""
        return A2aMetaOut.model_validate(a2a_meta_dict())

    async def _get_peer_or_raise(self, peer_id: UUID) -> A2aPeer:
        """加载 Peer 并校验租户与未删除。"""
        row = await self.db.get(A2aPeer, peer_id)
        if not row or is_marked_deleted(row):
            raise NotFoundError("A2A 外部 Agent 不存在")
        assert_tenant_access(self.ctx, row.tenant_id)
        return row

    async def list_peers(self, params: PageParams) -> PageResult[A2aPeerOut]:
        """分页列出已登记的外部 Agent。"""
        filters = [*tenant_filters(self.ctx, A2aPeer.tenant_id), not_deleted(A2aPeer)]
        total = await self.db.scalar(select(func.count(A2aPeer.id)).where(*filters))
        stmt = (
            select(A2aPeer)
            .where(*filters)
            .order_by(A2aPeer.created_at.desc())
            .offset(params.offset)
            .limit(params.size)
        )
        items = (await self.db.execute(stmt)).scalars().all()
        return PageResult(
            items=[_peer_out(i) for i in items],
            total=total or 0,
            page=params.page,
            size=params.size,
        )

    async def create_peer(self, body: A2aPeerCreate) -> A2aPeerOut:
        """创建 Peer 行（状态 PENDING，需 sync-card 后 ACTIVE）。"""
        card_url = resolve_agent_card_url(body.base_url)
        existing = await self.db.scalar(
            select(A2aPeer.id).where(
                A2aPeer.tenant_id == self.ctx.tenant_id,
                A2aPeer.name == body.name.strip(),
                not_deleted(A2aPeer),
            )
        )
        if existing:
            raise BadRequestError(f"已存在同名外部 Agent「{body.name}」")

        row = A2aPeer(
            tenant_id=self.ctx.tenant_id,
            name=body.name.strip(),
            description=body.description,
            base_url=body.base_url.strip(),
            agent_card_url=card_url,
            auth_config=body.auth_config or {},
            status=A2aPeerStatus.PENDING,
        )
        self.db.add(row)
        await self.db.flush()
        return _peer_out(row)

    async def get_peer(self, peer_id: UUID) -> A2aPeerOut:
        """获取单个 Peer 详情。"""
        return _peer_out(await self._get_peer_or_raise(peer_id))

    async def update_peer(self, peer_id: UUID, body: A2aPeerUpdate) -> A2aPeerOut:
        """更新名称/URL 等；base_url 变更时重算 agent_card_url。"""
        row = await self._get_peer_or_raise(peer_id)
        data = body.model_dump(exclude_unset=True)
        if "name" in data and data["name"]:
            data["name"] = data["name"].strip()
        if "base_url" in data and data["base_url"]:
            data["agent_card_url"] = resolve_agent_card_url(data["base_url"])
            data["base_url"] = data["base_url"].strip()
        for key, value in data.items():
            setattr(row, key, value)
        await self.db.flush()
        return _peer_out(row)

    async def delete_peer(self, peer_id: UUID) -> None:
        """软删 Peer（绑定表由 FK 级联或业务先解绑）。"""
        row = await self._get_peer_or_raise(peer_id)
        await mark_deleted(self.db, row)

    async def sync_peer_card(self, peer_id: UUID) -> A2aPeerSyncResult:
        """拉取并缓存 Agent Card，成功置 ACTIVE，失败置 ERROR。"""
        row = await self._get_peer_or_raise(peer_id)
        source = row.base_url or row.agent_card_url
        try:
            card, card_url = await fetch_agent_card(source)
            now = datetime.now(timezone.utc)
            row.agent_card_json = card
            row.agent_card_url = card_url
            row.card_display_name = card_display_name(card)
            row.last_synced_at = now
            row.last_error = None
            row.status = A2aPeerStatus.ACTIVE
            await self.db.flush()
            skills = count_card_skills(card)
            msg = f"已同步 Agent Card，识别到 {skills} 个 skill"
            return A2aPeerSyncResult(peer=_peer_out(row), card_url=card_url, message=msg)
        except BadRequestError as e:
            row.status = A2aPeerStatus.ERROR
            row.last_error = str(e)
            await self.db.flush()
            raise

    async def probe_url(self, base_or_card_url: str) -> A2aPeerProbeResult:
        """登记前探测 URL 是否可拉取 Card（不写库）。"""
        try:
            card, card_url = await fetch_agent_card(base_or_card_url)
            name = card_display_name(card)
            skills = count_card_skills(card)
            return A2aPeerProbeResult(
                ok=True,
                card_url=card_url,
                card_display_name=name,
                skills_count=skills,
                message=f"连通正常 · {skills} 个 skill" + (f" · {name}" if name else ""),
            )
        except BadRequestError as e:
            return A2aPeerProbeResult(
                ok=False,
                card_url=resolve_agent_card_url(base_or_card_url),
                message=str(e),
            )
