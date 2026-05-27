"""
应用市场官方模板种子数据。

``_rag_graph()`` 加载 ``flow_runtime/templates/rag_flow.json`` 作为上架应用的默认画布；
与 ``tenant.marketplace.util.load_rag_graph_template`` 同源。结构说明见 ``templates/README.md``。

官方应用标签绑定在默认租户（``seed_tenant_name``）下，``publisher_tenant_id`` 指向该租户，
广场展示与按 slug 筛选均按发布方租户解析。
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.flow_runtime.templates.registry import load_flow_template_graph
from app.models.tag import EntityTagBinding, TagEntityType, TenantTag
from app.models.tenant import Tenant
from app.tenant.categories.services.category import slugify
from app.tenant.marketplace.models import AppCategory, MarketplaceApp, MarketplaceAppStatus


def _rag_graph() -> dict:
    return load_flow_template_graph("rag")


# 官方应用市场推荐标签（默认租户内 (tenant_id, slug) 唯一）
OFFICIAL_MARKETPLACE_TAG_NAMES: tuple[str, ...] = (
    "官方",
    "RAG",
    "知识库",
    "流程编排",
    "多模态",
    "开箱即用",
)

OFFICIAL_APP_SPECS: list[dict] = [
    {
        "name": "RAG 问答助手",
        "description": "一键安装知识库 + RAG 编排流程 + 智能体，适合企业文档问答场景。",
        "icon": "🤖",
        "category_slug": "rag",
        "tag_names": ("官方", "RAG", "知识库", "流程编排", "开箱即用"),
        "manifest": {
            "version": "1.0.0",
            "resources": {
                "knowledge_base": {
                    "name": "RAG 知识库",
                    "description": "上传企业文档后自动解析与向量化",
                },
                "flow": {
                    "name": "RAG 问答流程",
                    "graph_json": None,  # filled at seed time
                    "auto_publish": True,
                },
                "agent": {
                    "name": "RAG 问答助手",
                    "system_prompt": "你是企业知识库助手，请严格依据检索到的资料回答，不要编造事实。",
                    "bind_kb": True,
                    "bind_flow": True,
                },
            },
        },
    },
    {
        "name": "RAG 编排流程",
        "description": "仅安装可视化 RAG 流程模板，可在流程编排中继续编辑。",
        "icon": "🔀",
        "category_slug": "flow",
        "tag_names": ("官方", "RAG", "流程编排"),
        "manifest": {
            "version": "1.0.0",
            "resources": {
                "flow": {
                    "name": "RAG 标准流程",
                    "graph_json": None,
                    "auto_publish": False,
                },
            },
        },
    },
    {
        "name": "多模态知识库套件",
        "description": "安装支持图片 OCR、音频转写的知识库，适合票据、课件、会议录音等场景。",
        "icon": "🖼️",
        "category_slug": "multimodal",
        "tag_names": ("官方", "多模态", "知识库", "开箱即用"),
        "manifest": {
            "version": "1.0.0",
            "resources": {
                "knowledge_base": {
                    "name": "多模态知识库",
                    "description": "支持上传 JPG/PNG 图片与 MP3/WAV 音频，自动解析后入库检索",
                },
                "agent": {
                    "name": "多模态问答助手",
                    "system_prompt": "你是多模态知识库助手，请结合 OCR/转写后的文本内容回答，并说明信息来源类型。",
                    "bind_kb": True,
                    "bind_flow": False,
                },
            },
        },
    },
    {
        "name": "知识库对话助手",
        "description": "安装空知识库与检索对话智能体，适合快速搭建问答入口。",
        "icon": "📚",
        "category_slug": "agent",
        "tag_names": ("官方", "知识库", "开箱即用"),
        "manifest": {
            "version": "1.0.0",
            "resources": {
                "knowledge_base": {
                    "name": "对话知识库",
                    "description": "请上传文档后开始问答",
                },
                "agent": {
                    "name": "知识库助手",
                    "system_prompt": "你是知识库助手，结合检索结果回答用户问题。",
                    "bind_kb": True,
                    "bind_flow": False,
                },
            },
        },
    },
]


async def seed_marketplace_categories(session: AsyncSession) -> dict[str, AppCategory]:
    """幂等写入市场分类；返回 slug -> 行。"""
    categories = [
        ("RAG 应用", "rag", 10),
        ("智能体", "agent", 20),
        ("流程模板", "flow", 30),
        ("多模态", "multimodal", 40),
    ]
    cat_map: dict[str, AppCategory] = {}
    for name, slug, order in categories:
        exists = await session.scalar(select(AppCategory.id).where(AppCategory.slug == slug))
        if exists:
            row = await session.get(AppCategory, exists)
            if row:
                cat_map[slug] = row
            continue
        cat = AppCategory(name=name, slug=slug, sort_order=order)
        session.add(cat)
        cat_map[slug] = cat
    await session.flush()
    return cat_map


async def _default_tenant_id(session: AsyncSession) -> UUID | None:
    settings = get_settings()
    return await session.scalar(
        select(Tenant.id).where(Tenant.name == settings.seed_tenant_name).limit(1)
    )


async def _ensure_tenant_tag(session: AsyncSession, tenant_id: UUID, name: str) -> TenantTag:
    slug = slugify(name)
    tag_id = await session.scalar(
        select(TenantTag.id).where(TenantTag.tenant_id == tenant_id, TenantTag.slug == slug).limit(1)
    )
    if tag_id:
        row = await session.get(TenantTag, tag_id)
        if row:
            return row
    row = TenantTag(tenant_id=tenant_id, name=name, slug=slug)
    session.add(row)
    await session.flush()
    return row


async def _replace_marketplace_app_tags(
    session: AsyncSession,
    tenant_id: UUID,
    app_id: UUID,
    tags: list[TenantTag],
) -> None:
    et = TagEntityType.MARKETPLACE_APP.value
    await session.execute(
        delete(EntityTagBinding).where(
            EntityTagBinding.tenant_id == tenant_id,
            EntityTagBinding.entity_type == et,
            EntityTagBinding.entity_id == app_id,
        )
    )
    for tag in tags:
        session.add(
            EntityTagBinding(
                tenant_id=tenant_id,
                entity_type=et,
                entity_id=app_id,
                tag_id=tag.id,
            )
        )
    await session.flush()


def _manifest_with_graph(spec: dict, graph: dict) -> dict:
    manifest = spec["manifest"]
    resources = manifest.get("resources") or {}
    flow = resources.get("flow")
    if flow and flow.get("graph_json") is None:
        flow = {**flow, "graph_json": graph}
        resources = {**resources, "flow": flow}
    return {**manifest, "resources": resources}


async def _sync_official_app_tags(session: AsyncSession, tenant_id: UUID) -> None:
    """幂等：补齐官方应用发布方、标签库与绑定。"""
    tag_by_name: dict[str, TenantTag] = {}
    for name in OFFICIAL_MARKETPLACE_TAG_NAMES:
        tag_by_name[name] = await _ensure_tenant_tag(session, tenant_id, name)

    for spec in OFFICIAL_APP_SPECS:
        app = await session.scalar(
            select(MarketplaceApp).where(
                MarketplaceApp.is_official.is_(True),
                MarketplaceApp.name == spec["name"],
            )
        )
        if not app:
            continue
        if app.publisher_tenant_id is None:
            app.publisher_tenant_id = tenant_id
        tags = [tag_by_name[n] for n in spec["tag_names"] if n in tag_by_name]
        await _replace_marketplace_app_tags(session, tenant_id, app.id, tags)

    await session.flush()


async def seed_marketplace(session: AsyncSession) -> None:
    cat_map = await seed_marketplace_categories(session)
    tenant_id = await _default_tenant_id(session)
    if not tenant_id:
        return

    graph = _rag_graph()

    existing = await session.scalar(
        select(MarketplaceApp.id).where(MarketplaceApp.is_official.is_(True)).limit(1)
    )
    if not existing:
        for spec in OFFICIAL_APP_SPECS:
            session.add(
                MarketplaceApp(
                    publisher_tenant_id=tenant_id,
                    category_id=cat_map[spec["category_slug"]].id,
                    name=spec["name"],
                    description=spec["description"],
                    icon=spec["icon"],
                    version="1.0.0",
                    status=MarketplaceAppStatus.PUBLISHED,
                    is_official=True,
                    install_count=0,
                    manifest=_manifest_with_graph(spec, graph),
                )
            )
        await session.flush()

    await _sync_official_app_tags(session, tenant_id)
