"""应用市场官方模板种子数据。"""

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.app_tenant.marketplace.models import AppCategory, MarketplaceApp, MarketplaceAppStatus


def _rag_graph() -> dict:
    # langflow 模板在 app/langflow/templates/，不在 app_tenant 下
    path = Path(__file__).resolve().parents[2] / "langflow" / "templates" / "rag_flow.json"
    return json.loads(path.read_text(encoding="utf-8"))


async def seed_marketplace(session: AsyncSession) -> None:
    existing = await session.scalar(select(MarketplaceApp.id).limit(1))
    if existing:
        return

    categories = [
        ("RAG 应用", "rag", 10),
        ("智能体", "agent", 20),
        ("流程模板", "flow", 30),
        ("多模态", "multimodal", 40),
    ]
    cat_map: dict[str, AppCategory] = {}
    for name, slug, order in categories:
        cat = AppCategory(name=name, slug=slug, sort_order=order)
        session.add(cat)
        cat_map[slug] = cat
    await session.flush()

    graph = _rag_graph()
    apps = [
        {
            "name": "RAG 问答助手",
            "description": "一键安装知识库 + RAG 编排流程 + 智能体，适合企业文档问答场景。",
            "icon": "🤖",
            "category_slug": "rag",
            "manifest": {
                "version": "1.0.0",
                "resources": {
                    "knowledge_base": {
                        "name": "RAG 知识库",
                        "description": "上传企业文档后自动解析与向量化",
                    },
                    "flow": {
                        "name": "RAG 问答流程",
                        "graph_json": graph,
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
            "manifest": {
                "version": "1.0.0",
                "resources": {
                    "flow": {
                        "name": "RAG 标准流程",
                        "graph_json": graph,
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

    for spec in apps:
        app = MarketplaceApp(
            publisher_tenant_id=None,
            category_id=cat_map[spec["category_slug"]].id,
            name=spec["name"],
            description=spec["description"],
            icon=spec["icon"],
            version="1.0.0",
            status=MarketplaceAppStatus.PUBLISHED,
            is_official=True,
            install_count=0,
            manifest=spec["manifest"],
        )
        session.add(app)
    await session.flush()
