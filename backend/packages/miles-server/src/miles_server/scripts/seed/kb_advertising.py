"""广告知识库种子：创建 KB、上传示例文档并同步向量化入库。

命令：``milesai seed kb-advertising``
依赖：``seed tenant``、``seed model-catalog``；对象存储与向量库需可用。

幂等：按租户 + 知识库名「广告知识库」、文档文件名去重；已 READY 的文档跳过。

对象存储为同步实现，故经 ``asyncio.to_thread`` 离线
（见 ``tests/test_no_blocking_calls_in_async.py``）。
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from miles_core.config import get_settings
from miles_core.infra.storage import build_object_key, upload_bytes
from miles_core.models.kb import Document, DocumentStatus, KnowledgeBase
from miles_core.models.model import ModelConfig
from miles_core.models.model.catalog import ModelCapabilityType
from miles_core.models.platform.tenant import Tenant
from miles_core.soft_delete import mark_deleted, not_deleted
from miles_integrations.embeddings.model_meta import embedding_dimension_from_model
from miles_portal.deletion.cascade import before_delete_kb
from miles_portal.tenant.kb.services.ingest import run_ingest
from miles_portal.tenant.kb.services.quota import apply_storage_delta

KB_NAME = "广告知识库"
KB_DESCRIPTION = "广告法合规、文案写作与违规案例示例资料，供 RAG 检索演示。"
# 与「测试」知识库一致：通义 text-embedding-v4（非默认 BGE）
SEED_EMBEDDING_MODEL_CODE = "qwen-text-embedding-v4"
DATA_DIR = Path(__file__).resolve().parent / "data" / "advertising"

SEED_DOCUMENTS: list[tuple[str, str]] = [
    ("01-ad-law-overview.md", "text/markdown"),
    ("02-copywriting-guide.md", "text/markdown"),
    ("03-violation-cases.md", "text/markdown"),
]


async def _resolve_seed_embedding_model(session: AsyncSession) -> ModelConfig:
    model = await session.scalar(
        select(ModelConfig).where(
            ModelConfig.tenant_id.is_(None),
            ModelConfig.model_code == SEED_EMBEDDING_MODEL_CODE,
            ModelConfig.model_type == ModelCapabilityType.EMBEDDING.value,
            ModelConfig.is_active.is_(True),
            not_deleted(ModelConfig),
        )
    )
    if not model:
        raise RuntimeError("未找到通义 text-embedding-v4 内置模型，请先执行: milesai seed model-catalog")
    return model


async def _retire_kb(session: AsyncSession, kb: KnowledgeBase) -> None:
    docs = (await session.execute(select(Document).where(Document.kb_id == kb.id, not_deleted(Document)))).scalars().all()
    for doc in docs:
        await mark_deleted(session, doc)
    await before_delete_kb(session, kb.id)
    await mark_deleted(session, kb)
    await session.flush()


async def _get_or_create_kb(session: AsyncSession, tenant_id) -> KnowledgeBase:
    target_model = await _resolve_seed_embedding_model(session)
    row = await session.scalar(
        select(KnowledgeBase).where(
            KnowledgeBase.tenant_id == tenant_id,
            KnowledgeBase.name == KB_NAME,
            not_deleted(KnowledgeBase),
        )
    )
    if row and row.embedding_model_config_id != target_model.id:
        print(f">>> 广告知识库向量化模型不匹配，重建为 {SEED_EMBEDDING_MODEL_CODE} （与测试知识库一致）")
        await _retire_kb(session, row)
        row = None
    if row:
        return row

    kb = KnowledgeBase(
        tenant_id=tenant_id,
        name=KB_NAME,
        description=KB_DESCRIPTION,
        is_public=False,
        embedding_model_config_id=target_model.id,
        embedding_dimension=embedding_dimension_from_model(target_model),
        chunk_size=500,
        chunk_overlap=50,
        retrieval_mode="vector",
    )
    session.add(kb)
    await session.flush()
    return kb


async def _ensure_document(
    session: AsyncSession,
    *,
    kb: KnowledgeBase,
    filename: str,
    mime_type: str,
    content: bytes,
) -> str | None:
    """创建或复用文档行并上传 OSS；返回需 ingest 的 document_id，已 READY 则 None。"""
    existing = await session.scalar(
        select(Document).where(
            Document.kb_id == kb.id,
            Document.filename == filename,
            not_deleted(Document),
        )
    )
    if existing and existing.status == DocumentStatus.READY:
        return None

    is_new = existing is None
    if existing and existing.status in (
        DocumentStatus.PARSE_FAILED,
        DocumentStatus.EMBED_FAILED,
        DocumentStatus.PENDING,
        DocumentStatus.PARSING,
        DocumentStatus.EMBEDDING,
    ):
        doc = existing
        doc.status = DocumentStatus.PENDING
        doc.fail_reason = None
    else:
        settings = get_settings()
        doc = Document(
            tenant_id=kb.tenant_id,
            kb_id=kb.id,
            filename=filename,
            mime_type=mime_type,
            file_size=len(content),
            object_bucket=settings.object_storage_bucket,
            object_key="pending",
            status=DocumentStatus.PENDING,
        )
        session.add(doc)
        await session.flush()

    object_key = build_object_key(str(kb.tenant_id), str(kb.id), str(doc.id), filename)
    doc.object_key = object_key
    doc.file_size = len(content)
    doc.mime_type = mime_type
    await asyncio.to_thread(upload_bytes, content, object_key, mime_type, bucket=doc.object_bucket)
    if is_new:
        await apply_storage_delta(session, kb.tenant_id, len(content))
    await session.flush()
    return str(doc.id)


async def _prepare_advertising_kb(session: AsyncSession) -> list[str]:
    tenant_ids = list((await session.execute(select(Tenant.id))).scalars().all())
    if not tenant_ids:
        raise RuntimeError("无租户，请先执行: milesai seed tenant")

    doc_ids: list[str] = []
    for tenant_id in tenant_ids:
        kb = await _get_or_create_kb(session, tenant_id)
        for filename, mime_type in SEED_DOCUMENTS:
            path = DATA_DIR / filename
            if not path.is_file():
                raise FileNotFoundError(f"种子文档不存在: {path}")
            content = path.read_bytes()
            doc_id = await _ensure_document(
                session,
                kb=kb,
                filename=filename,
                mime_type=mime_type,
                content=content,
            )
            if doc_id:
                doc_ids.append(doc_id)
    return doc_ids


async def seed_advertising_kb(session: AsyncSession) -> None:
    """写入 KB/文档元数据，提交后同步执行 ingest（Parse → Embed → Index）。"""
    doc_ids = await _prepare_advertising_kb(session)
    await session.commit()

    if not doc_ids:
        print(">>> 广告知识库已存在且文档均已向量化，跳过 ingest")
        return

    print(f">>> 广告知识库：开始向量化 {len(doc_ids)} 篇文档")
    for doc_id in doc_ids:
        print(f"    ingest {doc_id}")
        run_ingest(doc_id)
    print(">>> 广告知识库向量化完成")
