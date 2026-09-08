# B-2b 实施计划：KB 向量化/检索链的 embed·rerank·日志绑定上移 L1

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 消除 `integrations/langchain/{embeddings,visual_embeddings,vectorstores}.py` 对 `tenant.models.services.{embedding_resolve,rerank_resolve}` 与 `tenant.kb.services.search_log` 的反向 import，把"按 KB 绑定模型解析向量化/重排 + 检索审计"收敛到 L1 装配点。

**Architecture:** 延续 B-1 的 **L1 装配 + 注入** 范式：
- kb 级向量化函数（按 `kb.embedding_model_config_id`/`visual_embedding_model_config_id` resolve 后调 L3 provider）整体迁入 L1 新模块 `tenant/kb/services/embeddings.py`；L3 只保留纯 provider 编排与纯谓词。
- 引入单个中立载体 `KbRetrievalBindings`（L3 dataclass，含 sync/async 两组 embed/rerank 回调）与 L1 工厂 `build_kb_retrieval_bindings()`；`vectorstores` 检索函数改收 `bindings` 参数、不再内部解析。
- 装配通道沿用 B-1 已建通道：RAG LangGraph 走 `configurable["kb_retrieval"]`；画布 KnowledgeSearch 走 `RunContext.kb_retrieval`（与 `resolve_model` 并列透传）。
- `kb_search_logs` 的唯一活跃生产者是工作台检索 API（L1 内部直呼 `write_kb_search_log`）；L3 `search_multi_kb_async` 的默认日志绑定与无调用方的 `retrieve_hits_with_ctx` 一并删除（当前无 Agent 路径经其写日志，行为零变化）。

**Tech Stack:** FastAPI / SQLAlchemy async / LangChain / LangGraph（后端 `backend/`，pytest 验证）。

## Global Constraints

- 分层（[`layering.md`](../../architecture/layering.md) §2.2）：`integrations`（L3）禁止 import `tenant`（L1）；允许 `tenant → integrations/rag` 单向；`rag`（L2）禁止 import `tenant`。本计划收敛后三个 L3 文件与 `rag/`、`flow_runtime/` 内不得再出现 `app.tenant.{models.services, kb.services}` import（`kb/models` 的 ORM 类型 import 允许，如 `models.kb`）。
- 中文 docstring（README §文档注释）：新增/改动模块须写模块与公开方法 docstring。
- 体量：改动文件不得超过 500 行；单文件 ≥400 行新增逻辑优先拆文件。
- 语义保持：非绑定路径行为零变化——CLIP 视觉/文本向量化维度与 provider 选择、rerank 门控（`kb.rerank_model_config_id` 为空跳过）、入库管道逐分片写 chunk/向量顺序均不变。唯一有意行为变化：L3 层不再"默认写 kb_search_log"（无活跃调用方）与 `search_multi_kb`/`search_as_documents`/`retrieve_hits_with_ctx`/`embed_texts_for_kb`(async) 删除（均无生产调用方，见各 Task 的 rg 验证）。
- 测试：全量回归（当前 433 基线）通过；为过测试不得修改非本计划文件语义。
- 提交：每任务单独 commit，message 简体中文，`<type>(<scope>): <简述>`。

---

### Task 1: L1 kb 域向量化模块建立（函数从 L3 原样迁移）

**Files:**
- Create: `backend/app/tenant/kb/services/embeddings.py`
- Test: `backend/tests/rag/test_embedding_models.py`（此 Task 不改测试；Task 3 再切 import）

**Interfaces:**
- Consumes: L3 `build_embeddings`（`integrations/embeddings/runtime.py`）、`invoke_mode_from_model`/`get_embedding_provider(INVOKE_MODE_CLIP)`（`integrations/embeddings/...`）、`ensure_clip_model`（`integrations/langchain/visual_embeddings.py`，L3 保留的纯校验）；L1 `resolve_embedding_model_by_id/sync`、`resolve_rerank_model_by_id/sync`（`tenant/models/services/...`）
- Produces（供 Task 2/3 调用方切换）:
  - `embed_texts_for_kb_sync(db: Session, kb, texts) -> list[list[float]]`
  - `embed_query_for_kb_sync(db: Session, kb, query) -> list[float]`
  - `embed_query_for_kb(db: AsyncSession, tenant_id: UUID, kb, query) -> list[float]`
  - `embed_image_chunks_vectors_sync(db: Session, kb, raw: bytes, chunk_count: int) -> list[list[float]]`
  - `embed_query_visual_async(db: AsyncSession, tenant_id: UUID, kb, query) -> list[float]`
  - `embed_image_bytes_async(db: AsyncSession, tenant_id: UUID, kb, raw: bytes) -> list[float]`
  - `build_kb_retrieval_bindings() -> KbRetrievalBindings`（本 Task 建 L3 中立类型文件 `integrations/langchain/kb_retrieval.py`，类型与工厂同 Task 落地，避免 L1→L3→L1 循环）

- [ ] **Step 1: 先建中立类型模块，再写失败测试（新模块函数可解析且本地 provider 生效）**

`KbRetrievalBindings` 不能定义在 `vectorstores.py`（该文件在 Task 2 之前仍 import L1 resolver，而 L1 kb 域模块要 import 该类型会形成 L1→L3→L1 循环）。故类型放**新 L3 中立文件** `backend/app/integrations/langchain/kb_retrieval.py`（仅依赖 L2 `multi_kb` 的类型别名，与既有 vectorstores→multi_kb import 同向）：

```python
"""KB 检索绑定载体（L3 中立，不依赖 tenant 域）。

供 L1 kb 域 ``tenant.kb.services.embeddings`` 构造、``vectorstores`` 检索函数
注入到 L2 ``rag.retrieve.multi_kb``；类型别名直接复用 multi_kb 的回调签名。
"""

from __future__ import annotations

from dataclasses import dataclass

from app.rag.retrieve.multi_kb import (
    EmbedQueryAsync,
    EmbedQuerySync,
    ResolveRerankAsync,
    ResolveRerankSync,
)


@dataclass(frozen=True)
class KbRetrievalBindings:
    """KB 检索能力载体：embed/rerank 回调。

    sync 组供同步工具/脚本路径，async 组供 Agent RAG 与画布 KnowledgeSearch；
    由 L1 装配并注入，L3/L2 只调用回调、不感知租户细节。
    """

    embed_query_sync: EmbedQuerySync
    resolve_rerank_sync: ResolveRerankSync | None = None
    embed_query: EmbedQueryAsync
    resolve_rerank: ResolveRerankAsync | None = None
```

新建 `backend/tests/rag/test_kb_service_embeddings.py`：

```python
"""L1 kb 域向量化模块：ModelConfig 绑定在 L1 命名空间内完成。"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import numpy as np
import pytest

from app.models.kb import KnowledgeBase
from app.models.model import ModelConfig
from app.models.model.catalog import ModelCapabilityType
from app.integrations.embeddings.constants import EXTRA_EMBEDDING_DIMENSION
from app.tenant.kb.services.embeddings import (
    build_kb_retrieval_bindings,
    embed_query_for_kb_sync,
)


def _local_bge_model() -> ModelConfig:
    return ModelConfig(
        id=uuid4(),
        tenant_id=None,
        name="本地 BGE 中文",
        provider="local",
        model_name="BAAI/bge-base-zh-v1.5",
        model_type=ModelCapabilityType.EMBEDDING.value,
        extra={"invoke_mode": "local", EXTRA_EMBEDDING_DIMENSION: 768},
    )


def test_embed_query_for_kb_sync_local():
    model = _local_bge_model()
    kb = KnowledgeBase(
        id=uuid4(),
        tenant_id=uuid4(),
        name="kb",
        embedding_model_config_id=model.id,
        embedding_dimension=768,
    )
    mock_encoder = MagicMock()
    mock_encoder.encode.return_value = np.array([[0.1] * 768], dtype=np.float32)
    db = MagicMock()
    with (
        patch(
            "app.tenant.kb.services.embeddings.resolve_embedding_model_sync",
            return_value=model,
        ),
        patch(
            "sentence_transformers.SentenceTransformer",
            return_value=mock_encoder,
        ),
    ):
        vec = embed_query_for_kb_sync(db, kb, "hello")
    assert len(vec) == 768


def test_build_kb_retrieval_bindings_shape():
    bindings = build_kb_retrieval_bindings()
    assert callable(bindings.embed_query_sync)
    assert callable(bindings.embed_query)
```

（`len(vec) == 768` 依赖模型 extra 的 `EXTRA_EMBEDDING_DIMENSION: 768`——已与 `tests/rag/test_embedding_models.py::_local_bge_model` 同构；若本地 provider 断言仍失败，以 `len(vec) > 0` 收敛，无行为差异。）

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/rag/test_kb_service_embeddings.py -q`
Expected: FAIL（`ModuleNotFoundError: No module named 'app.tenant.kb.services.embeddings'`）。

- [ ] **Step 3: 新建 L1 kb 域模块并迁移函数**

`backend/app/tenant/kb/services/embeddings.py`（顶部 import 用 `from app.integrations.langchain.kb_retrieval import KbRetrievalBindings`，不 import vectorstores）：

```python
"""知识库向量化（L1 kb 域）：按 KB 绑定模型解析后调用 L3 provider。

分层
----
- 本模块为 **L1 装配层**：按 ``kb.embedding_model_config_id`` / 视觉模型 id
  resolve ``ModelConfig``（含 BYOK 合并），再调用 L3 纯编排
  ``integrations.embeddings.runtime.build_embeddings`` / CLIP provider。
- L3 ``integrations/langchain/embeddings.py`` 不再承载这些解析（B-2b 后仅存纯层）。
- ``build_kb_retrieval_bindings`` 构造供 L3 ``vectorstores`` 检索注入的中立载体。
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.integrations.embeddings.constants import INVOKE_MODE_CLIP
from app.integrations.embeddings.model_meta import invoke_mode_from_model
from app.integrations.embeddings.registry import get_embedding_provider
from app.integrations.embeddings.runtime import build_embeddings
from app.integrations.langchain.kb_retrieval import KbRetrievalBindings
from app.tenant.models.services.embedding_resolve import (
    resolve_embedding_model_by_id,
    resolve_embedding_model_sync,
)

if TYPE_CHECKING:
    from app.models.kb import KnowledgeBase


def embed_texts_for_kb_sync(db: Session, kb: KnowledgeBase, texts: list[str]) -> list[list[float]]:
    """同步批量向量化分片文本（Celery 入库 pipeline 注入）。"""
    model = resolve_embedding_model_sync(db, kb.embedding_model_config_id, kb.tenant_id)
    return build_embeddings(model).embed_documents(texts)


def embed_query_for_kb_sync(db: Session, kb: KnowledgeBase, query: str) -> list[float]:
    """同步 query 向量化（内置工具/脚本路径）。"""
    model = resolve_embedding_model_sync(db, kb.embedding_model_config_id, kb.tenant_id)
    return build_embeddings(model).embed_query(query)


async def embed_query_for_kb(db: AsyncSession, tenant_id: UUID, kb: KnowledgeBase, query: str) -> list[float]:
    """异步 query 向量化（工作台 KB 检索 API 与 Agent async 检索）。"""
    model = await resolve_embedding_model_by_id(db, kb.embedding_model_config_id, tenant_id)
    return build_embeddings(model).embed_query(query)


def _ensure_clip(model) -> None:
    """视觉模型必须为 CLIP（复用 L3 纯校验，避免重复实现）。"""
    from app.integrations.langchain.visual_embeddings import ensure_clip_model

    ensure_clip_model(model)


def embed_image_chunks_vectors_sync(
    db: Session,
    kb: KnowledgeBase,
    raw: bytes,
    chunk_count: int,
) -> list[list[float]]:
    """同步图片向量化：单图向量复制到每个分片（入库 pipeline 注入）。"""
    vec = _embed_image_bytes_sync(db, kb, raw)
    return [vec] * chunk_count


def _embed_image_bytes_sync(db: Session, kb: KnowledgeBase, raw: bytes) -> list[float]:
    if not kb.visual_embedding_model_config_id:
        raise BadRequestError("知识库未配置视觉向量化模型")
    model = resolve_embedding_model_sync(db, kb.visual_embedding_model_config_id, kb.tenant_id)
    _ensure_clip(model)
    provider = get_embedding_provider(INVOKE_MODE_CLIP)
    return provider.embed_images(model, [raw])[0]


async def embed_query_visual_async(
    db: AsyncSession,
    tenant_id: UUID,
    kb: KnowledgeBase,
    query: str,
) -> list[float]:
    """异步视觉文本搜图 query 向量化（工作台 KB API）。"""
    if not kb.visual_embedding_model_config_id:
        raise BadRequestError("知识库未配置视觉向量化模型")
    text = (query or "").strip()
    if not text:
        raise BadRequestError("视觉文本搜图需填写 query")
    model = await resolve_embedding_model_by_id(db, kb.visual_embedding_model_config_id, tenant_id)
    _ensure_clip(model)
    provider = get_embedding_provider(INVOKE_MODE_CLIP)
    return provider.embed_texts(model, [text])[0]


async def embed_image_bytes_async(
    db: AsyncSession,
    tenant_id: UUID,
    kb: KnowledgeBase,
    raw: bytes,
) -> list[float]:
    """异步以图搜图 query_document_id 的图片向量化（工作台 KB API）。"""
    if not kb.visual_embedding_model_config_id:
        raise BadRequestError("知识库未配置视觉向量化模型")
    model = await resolve_embedding_model_by_id(db, kb.visual_embedding_model_config_id, tenant_id)
    _ensure_clip(model)
    provider = get_embedding_provider(INVOKE_MODE_CLIP)
    return provider.embed_images(model, [raw])[0]


def build_kb_retrieval_bindings() -> KbRetrievalBindings:
    """构造 L3 ``vectorstores`` 检索注入的 KB 检索能力载体。"""
    return KbRetrievalBindings(
        embed_query_sync=embed_query_for_kb_sync,
        resolve_rerank_sync=_resolve_rerank_sync,
        embed_query=embed_query_for_kb,
        resolve_rerank=_resolve_rerank_async,
    )


def _resolve_rerank_sync(db: Session, kb: KnowledgeBase, tenant_id: UUID):
    """解析 KB 绑定的 rerank 模型；未配置返回 None（L3 multi_kb 注入形参）。"""
    if not kb.rerank_model_config_id:
        return None
    from app.tenant.models.services.rerank_resolve import resolve_rerank_model_sync

    return resolve_rerank_model_sync(db, kb.rerank_model_config_id, tenant_id)


async def _resolve_rerank_async(db: AsyncSession, kb: KnowledgeBase, tenant_id: UUID):
    """异步解析 rerank 模型（multi_kb_async 使用）。"""
    if not kb.rerank_model_config_id:
        return None
    from app.tenant.models.services.rerank_resolve import resolve_rerank_model_by_id

    return await resolve_rerank_model_by_id(db, kb.rerank_model_config_id, tenant_id)
```

注意：顶部需补 `from app.common.exceptions import BadRequestError`（`_embed_image_bytes_sync`/visual 路径使用）。

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/rag/test_kb_service_embeddings.py -q`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add backend/app/tenant/kb/services/embeddings.py backend/app/integrations/langchain/kb_retrieval.py backend/tests/rag/test_kb_service_embeddings.py
git commit -m "refactor(kb): 新增 kb 域向量化模块与中立 KbRetrievalBindings 载体"
```

---

### Task 2: vectorstores 显式化 + 同步工具链装配 + 死代码清除

**Files:**
- Modify: `backend/app/integrations/langchain/vectorstores.py`、`backend/app/tenant/tools/builtins/handlers.py`、`backend/app/integrations/langchain/tools.py`、`backend/app/integrations/langchain/__init__.py`
- Test: 全量（无既有检索端到端用例，靠回归 + rg 自检）

**Interfaces:**
- Consumes: Task 1 `KbRetrievalBindings` / `build_kb_retrieval_bindings`；L1 `embed_texts_for_kb_sync` 不再被 vectorstores 使用
- Produces: `vectorstores.search_kb(query, *, kb, db, limit=10, mode="default", bindings: KbRetrievalBindings)`；`search_multi_kb`/`search_as_documents`/`_write_search_log`/`search_multi_kb_async(write_log=...)` 删除或签名收敛（async 高层签名 Task 4 再定，此处保留旧名但去掉 write_log 行为——见 Step 4）

设计说明：sync 检索链生产调用方仅 L1 `handlers.handle_knowledge_search` 与 L3 `tools.make_knowledge_search_tool`（schema 壳、.func 从不被工具链执行，见工具执行注释）。本任务把 sync 链切到显式 bindings，并把 schema 壳 func 改为明确报错指引，彻底移除 tools.py 对 `search_kb` 的 import。async 高层 `search_multi_kb_async` 保留签名兼容（bindings 参数 Task 3/4 注入，默认仍走旧绑定过渡）——不，**无中间态**：Task 4 将在同一步把 async 全链切完，故本任务 `search_multi_kb_async` 仅去掉默认日志绑定（`write_log` 参数删除、`_write_search_log`/`write_kb_search_log` import 删除），embed/rerank 显式化在 Task 4。

- [ ] **Step 1: 改造 vectorstores.py sync 段与日志绑定**

`backend/app/integrations/langchain/vectorstores.py` 中：
1. 删除顶部 import：
   - `from app.tenant.kb.services.search_log import write_kb_search_log`
   - `from app.tenant.models.services.rerank_resolve import (resolve_rerank_model_by_id, resolve_rerank_model_sync)`
   - `from app.integrations.langchain.embeddings import embed_query_for_kb, embed_query_for_kb_sync`（改由 bindings 注入，见下）
   - `from app.integrations.langchain.vector.documents import hit_to_document`（`search_as_documents` 删除后无引用）
2. 新增 import：`from app.integrations.langchain.kb_retrieval import KbRetrievalBindings`。
3. 删除 `_resolve_rerank_sync`/`_resolve_rerank_async`/`_write_search_log` 三个私有函数。
3. `search_kb` 签名改为：

```python
def search_kb(
    query: str,
    *,
    kb: KnowledgeBase,
    db: Session,
    limit: int = 10,
    mode: str = "default",
    bindings: KbRetrievalBindings,
) -> list[dict[str, Any]]:
    """单 KB 同步检索（绑定由调用方注入，供 embed/rerank）。"""
    return _search_kb(
        query,
        kb=kb,
        db=db,
        limit=limit,
        mode=mode,
        embed_query_sync=bindings.embed_query_sync,
        resolve_rerank_sync=bindings.resolve_rerank_sync,
    )
```

4. 删除 `search_multi_kb`（sync 多库）与 `search_as_documents` 两个函数（Task 2 Step 2 的 rg 证明无生产调用方）。
5. `search_multi_kb_async` 收敛为"纯转发 + 显式 bindings"，删除 `write_log` 参数与 `on_complete` 日志组装（`source/actor_user_id/agent_id` 一并删除）：

```python
async def search_multi_kb_async(
    query: str,
    *,
    kbs: list[KnowledgeBase],
    db: AsyncSession,
    tenant_id: UUID,
    top_k: int = 5,
    mode: str = "default",
    bindings: KbRetrievalBindings,
) -> list[dict[str, Any]]:
    """多 KB 异步检索（embed/rerank 由 bindings 注入；审计日志由 L1 检索 API 自行负责）。"""
    return await _search_multi_kb_async(
        query,
        kbs=kbs,
        db=db,
        tenant_id=tenant_id,
        top_k=top_k,
        mode=mode,
        embed_query=bindings.embed_query,
        resolve_rerank=bindings.resolve_rerank,
    )
```

同步更新模块 docstring（去掉"可选写 kb_search_logs"的职责描述）。文档注释"Agent / 多 KB RAG 主入口"移到调用方注释。

- [ ] **Step 2: rg 证明 search_multi_kb/search_as_documents/retrieve_hits_with_ctx 无生产调用方**

Run: `cd backend && rg -n "search_multi_kb\(|search_as_documents|retrieve_hits_with_ctx" app tests scripts workers 2>/dev/null`
Expected: 除 `__init__.py` re-export 与测试 mocks 外无生产引用（若有，先顺藤迁移再删）。

- [ ] **Step 3: handlers.py 装配 sync bindings**

`backend/app/tenant/tools/builtins/handlers.py`：
- import 改：`from app.integrations.langchain.vectorstores import search_kb` 保留；新增 `from app.tenant.kb.services.embeddings import build_kb_retrieval_bindings`。
- `handle_knowledge_search`（L52-71）`_run` 内调用改为：

```python
    with get_sync_db() as sync_db:
        kb = load_kb_sync(sync_db, ctx.tenant_id, UUID(str(kb_id)))
        hits = search_kb(
            str(query),
            kb=kb,
            db=sync_db,
            limit=int(params.get("limit", 5)),
            bindings=build_kb_retrieval_bindings(),
        )
```

- [ ] **Step 4: tools.py schema 壳去调用**

`backend/app/integrations/langchain/tools.py`：删除顶部 `from app.integrations.langchain.vectorstores import search_kb`；`make_knowledge_search_tool` 的 `_run` 改为：

```python
    def _run(query: str, kb_id: str, limit: int = 5) -> dict:
        raise NotImplementedError(
            "knowledge_search 工具执行经 builtin 注册表 handle_knowledge_search（L1），"
            "本 schema 壳仅供 LLM 工具描述。"
        )
```

同时该函数不再需要 `get_sync_db`/`load_kb_sync`/`UUID`——检查并清理本文件内因仅此使用而残留的 import（`load_kb_sync`、`get_sync_db` 若他处仍用则保留）。

- [ ] **Step 5: __init__.py re-export 同步**

`backend/app/integrations/langchain/__init__.py`：删除 `"search_multi_kb"`、`"search_as_documents"` 两个名字与对应延迟加载分支（保留 `search_kb`、`search_multi_kb_async`）。

- [ ] **Step 6: 回归 + 残留自检**

Run: `cd backend && .venv/bin/python -m pytest -q`
Expected: PASS（若有失败多半来自直接构造旧签名的测试，按错误把 bindings/纯转发对齐）。
Run: `cd backend && rg -n "tenant\.(kb\.services\.search_log|models\.services\.rerank)" app/integrations/langchain/vectorstores.py`
Expected: 无输出。

- [ ] **Step 7: Commit**

```bash
git add backend/app/integrations/langchain/vectorstores.py backend/app/tenant/tools/builtins/handlers.py backend/app/integrations/langchain/tools.py backend/app/integrations/langchain/__init__.py
git commit -m "refactor(kb): vectorstores 检索改为 bindings 注入并清 sync 死代码"
```

---

### Task 3: L1 调用方切 kb 域模块 + L3 embeddings/visual_embeddings 瘦身

**Files:**
- Modify: `backend/app/tenant/kb/services/kb/search.py`、`backend/app/tenant/kb/services/ingest.py`、`backend/app/integrations/langchain/embeddings.py`、`backend/app/integrations/langchain/visual_embeddings.py`、`backend/app/integrations/langchain/__init__.py`、`backend/tests/rag/test_embedding_models.py`

**Interfaces:**
- Consumes: Task 1 的 L1 模块函数
- Produces: L3 `embeddings.py` 删除（若空壳）或仅保留无 L1 依赖的转发；`visual_embeddings.py` 仅保留 `ensure_clip_model`/`should_use_visual_image_embedding` 纯函数

- [ ] **Step 1: kb/search.py 切 import**

`backend/app/tenant/kb/services/kb/search.py` 顶部两处 import 改为：

```python
from app.tenant.kb.services.embeddings import (
    embed_image_bytes_async,
    embed_query_for_kb,
    embed_query_visual_async,
)
```

（删除对 `app.integrations.langchain.embeddings` 与 `visual_embeddings` 的相应 import；文件内调用签名不变。）

- [ ] **Step 2: ingest.py 切 import**

`backend/app/tenant/kb/services/ingest.py` 顶部：

```python
from app.tenant.kb.services.embeddings import (
    embed_image_chunks_vectors_sync,
    embed_texts_for_kb_sync,
)
```

并将 `run_ingest_pipeline(...)` 调用追加视觉注入（配合 Task 4 Step 2 的 pipeline 形参）：

```python
                embed_texts=embed_texts_for_kb_sync,
                embed_visual_chunks=embed_image_chunks_vectors_sync,
```

- [ ] **Step 3: 删除 L3 embeddings.py 全部函数并移除文件**

确认 `integrations/langchain/embeddings.py` 的函数消费方仅剩：vectorstores（Task 2 已显式化，不再 import）、kb/search（Step 1 已切）、kb/ingest（Step 2 已切）、`__init__.py` 延迟 re-export、`tests/rag/test_embedding_models.py`。

1. 删除 `backend/app/integrations/langchain/embeddings.py` 文件。
2. `__init__.py`：删除 `"embed_query_for_kb"`/`"embed_query_for_kb_sync"`/`"embed_texts_for_kb"`/`"embed_texts_for_kb_sync"` 及对应延迟分支。
3. `tests/rag/test_embedding_models.py`：`from app.integrations.langchain.embeddings import embed_query_for_kb_sync` → `from app.tenant.kb.services.embeddings import embed_query_for_kb_sync`；patch 目标 `"app.integrations.langchain.embeddings.resolve_embedding_model_sync"` → `"app.tenant.kb.services.embeddings.resolve_embedding_model_sync"`。

- [ ] **Step 4: visual_embeddings.py 瘦身**

`backend/app/integrations/langchain/visual_embeddings.py` 删除全部 `embed_*` 函数与 `resolve_embedding_model_*` import、`AsyncSession`/`UUID`/`Session` 等仅 embed 用 import，仅保留 `ensure_clip_model` 与 `should_use_visual_image_embedding`（纯函数，无 L1 依赖）。模块 docstring 更新为"CLIP 视觉向量化的纯校验与谓词（embedding 解析见 L1 kb 域）"。
（Task 1 的 `_ensure_clip` 已 import 它，保留导出名不变。）

- [ ] **Step 5: 回归**

Run: `cd backend && .venv/bin/python -m pytest tests/rag/test_embedding_models.py tests/rag/test_clip_visual_search.py tests/rag/test_kb_service_embeddings.py -q && .venv/bin/python -m pytest -q`
Expected: 全部 PASS。若 `test_clip_visual_search` 引用被删函数则按函数语义在 kb 域模块补用例（保留文件内谓词用例即可）。

- [ ] **Step 6: Commit**

```bash
git add -A backend/app/integrations/langchain/embeddings.py backend/app/integrations/langchain/visual_embeddings.py backend/app/integrations/langchain/__init__.py backend/app/tenant/kb/services/kb/search.py backend/app/tenant/kb/services/ingest.py backend/tests/rag/test_embedding_models.py
git commit -m "refactor(kb): kb 向量化解析迁入 L1 kb 域并移除 L3 embeddings 层"
```

---

### Task 4: rag_answer/retrieve_hits 显式 bindings + L2 pipeline 视觉注入

**Files:**
- Modify: `backend/app/rag/generate/answer.py`、`backend/app/rag/pipeline/ingest.py`
- Test: `backend/tests/rag/test_rag_answer_stream.py`（既有 mock 适配）、`backend/tests/rag/test_rag_pipeline_ingest.py`

**Interfaces:**
- Consumes: `KbRetrievalBindings`（vectorstores）、L1 视觉向量化回调（kb 域 `embed_image_chunks_vectors_sync`）
- Produces:
  - `retrieve_hits(query, *, tenant_id, kb_ids, db, top_k=5, mode="default", bindings: KbRetrievalBindings | None = None)`
  - `rag_answer(..., bindings: KbRetrievalBindings | None = None)`（透传给 retrieve_hits）
  - `run_ingest_pipeline(..., embed_visual_chunks: EmbedVisualChunks | None = None, ...)`

- [ ] **Step 1: answer.py 改造**

`backend/app/rag/generate/answer.py`：
1. import：`from app.integrations.langchain.kb_retrieval import KbRetrievalBindings`；`search_multi_kb_async` 继续从 vectorstores import（Task 2 已收敛为显式 bindings）。
2. `retrieve_hits` 内部替换为：

```python
    kbs = await load_kbs_for_tenant(db, tenant_id, kb_ids)
    if bindings is None:
        raise ValueError("检索链路缺少 KB 检索绑定（bindings），需由 L1 装配")
    return await search_multi_kb_async(
        query,
        kbs=kbs,
        db=db,
        tenant_id=tenant_id,
        top_k=top_k,
        mode=mode,
        bindings=bindings,
    )
```

函数签名加 `bindings: KbRetrievalBindings | None = None`（位于 `mode` 之后）；docstring 说明 `write_log=False` 语义（本模块不写 search_log）。
3. 删除 `retrieve_hits_with_ctx` 函数（Task 2 Step 2 已证无调用方）及仅其使用的 import（如有）。
4. `rag_answer` 签名加 `bindings: KbRetrievalBindings | None = None`，内部 `retrieve_hits(...)` 调用透传 `bindings=bindings`。

- [ ] **Step 2: pipeline 视觉注入**

`backend/app/rag/pipeline/ingest.py`：
1. 新增协议与形参：

```python
class EmbedVisualChunks(Protocol):
    """按 KB 绑定的 CLIP 模型向量化图片字节（每分片一份向量）。"""

    def __call__(self, db: Session, kb: KnowledgeBase, raw: bytes, chunk_count: int) -> list[list[float]]: ...
```

2. `run_ingest_pipeline` 签名：在 `embed_texts` 后插入 `embed_visual_chunks: EmbedVisualChunks | None = None,`。
3. import 改为仅保留纯谓词：`from app.integrations.langchain.visual_embeddings import should_use_visual_image_embedding`（删除 `embed_image_chunks_vectors_sync` import）。
4. 向量化分支改为：

```python
    if should_use_visual_image_embedding(kb, data.filename, data.mime_type):
        if embed_visual_chunks is None:
            raise ValueError("图片入库需注入 embed_visual_chunks（视觉向量化回调）")
        vectors = embed_visual_chunks(db, kb, raw, len(chunks_text))
    else:
        vectors = embed_texts(db, kb, chunks_text)
```

模块 docstring「4. embed_texts」说明同步更新为含视觉注入。

- [ ] **Step 3: 回归适配**

Run: `cd backend && .venv/bin/python -m pytest tests/rag/test_rag_answer_stream.py tests/rag/test_rag_pipeline_ingest.py tests/rag/test_ingest_page_no.py -q && .venv/bin/python -m pytest -q`
Expected: PASS。既有 pipeline 测试若为图片文档，需在调用处补 `embed_visual_chunks=fake`；若仅文本不受影响。

- [ ] **Step 4: Commit**

```bash
git add backend/app/rag/generate/answer.py backend/app/rag/pipeline/ingest.py
git commit -m "refactor(rag): retrieve_hits/入库管道改收 kb 绑定与视觉向量化回调"
```

---

### Task 5: RAG LangGraph 装配通道（runner → rag_qa.retrieve）

**Files:**
- Modify: `backend/app/integrations/langgraph/runner.py`、`backend/app/integrations/langgraph/graphs/rag_qa.py`

**Interfaces:**
- Consumes: `KbRetrievalBindings`（vectorstores）
- Produces: `run_rag_workflow(..., bindings: KbRetrievalBindings | None = None)`，写 `configurable["kb_retrieval"]`；`rag_qa.retrieve` 从 config 取 bindings 并透传 `retrieve_hits`

- [ ] **Step 1: runner.py 加参数并写入 configurable**

`backend/app/integrations/langgraph/runner.py`：`run_rag_workflow` 签名在 `usage_sink` 后加 `bindings: KbRetrievalBindings | None = None`（顶部 `from app.integrations.langchain.kb_retrieval import KbRetrievalBindings`）；docstring 补一行。`run_config` 的 `configurable` dict 加 `"kb_retrieval": bindings,`。

- [ ] **Step 2: rag_qa.retrieve 取 bindings**

`backend/app/integrations/langgraph/graphs/rag_qa.py` `retrieve` 节点改为：

```python
    kb_retrieval = config.get("configurable", {}).get("kb_retrieval") if config else None
    tenant_id = UUID(state["tenant_id"])
    search_q = (state.get("query") or "").strip()
    async with AsyncSessionLocal() as db:
        hits = await retrieve_hits(
            search_q,
            tenant_id=tenant_id,
            kb_ids=state["kb_ids"],
            db=db,
            top_k=state.get("top_k", 5),
            bindings=kb_retrieval,
        )
```

（`retrieve_hits` 的 `bindings` 形参来自 Task 4。）

- [ ] **Step 3: 回归**

Run: `cd backend && .venv/bin/python -m pytest tests/rag tests/tenant/agents tests/integration -q && .venv/bin/python -m pytest -q`
Expected: PASS。RAG 链端到端用例若存在需装配 fake bindings（mock `retrieve_hits` 的用例不受影响）。

- [ ] **Step 4: Commit**

```bash
git add backend/app/integrations/langgraph/runner.py backend/app/integrations/langgraph/graphs/rag_qa.py
git commit -m "refactor(rag): RAG LangGraph 检索绑定经 configurable 注入"
```

---

### Task 6: 画布 KnowledgeSearch 经 RunContext.kb_retrieval 装配

**Files:**
- Modify: `backend/app/flow_runtime/types.py`、`backend/app/flow_runtime/nodes/rag_nodes.py`、`backend/app/flow_runtime/subflow/resolve.py`、`backend/app/integrations/langgraph/compiler/build.py`、`backend/app/integrations/langgraph/compiler/run.py`
- Test: `backend/tests/flow/`（回归为主）

**Interfaces:**
- Consumes: Task 1 的 bindings 载体与 L1 工厂（在 Task 7 的装配点注入）
- Produces: `RunContext.kb_retrieval: Any = None`；节点从 `ctx.kb_retrieval` 取绑定透传 `retrieve_hits`；compiler state 通道 `kb_retrieval`

- [ ] **Step 1: RunContext 加字段**

`backend/app/flow_runtime/types.py` `usage_sink` 后追加：

```python
    # KB 检索能力载体（L1 注入；None 表示未装配，KnowledgeSearch 节点报错）
    kb_retrieval: Any = None
```

- [ ] **Step 2: rag_nodes.knowledge_search 装配**

`backend/app/flow_runtime/nodes/rag_nodes.py` 检索分支（L43-51 附近）改为：

```python
    if not kb_ids:
        return []
    if ctx.kb_retrieval is None:
        raise BadRequestError("运行上下文未提供知识库检索绑定")
    async with AsyncSessionLocal() as db:
        return await retrieve_hits(
            query,
            tenant_id=UUID(ctx.tenant_id),
            kb_ids=kb_ids,
            db=db,
            top_k=top_k,
            mode=retrieval_mode,
            bindings=ctx.kb_retrieval,
        )
```

顶部补 `from app.common.exceptions import BadRequestError` import（当前文件未引用，需新增）。

- [ ] **Step 3: compiler 状态通道**

`backend/app/integrations/langgraph/compiler/build.py`：
1. `_State` dataclass 在 `usage_sink: Any` 后加 `kb_retrieval: Any`。
2. 节点 ctx 重建 `replace(RunContext(...))` 中 `usage_sink=state.get("usage_sink"),` 后加 `kb_retrieval=state.get("kb_retrieval"),`。

`backend/app/integrations/langgraph/compiler/run.py`：`initial` dict 在 `"usage_sink": ctx.usage_sink,` 后加 `"kb_retrieval": ctx.kb_retrieval,`。

- [ ] **Step 4: subflow 透传**

`backend/app/flow_runtime/subflow/resolve.py` `build_child_context` 的 RunContext 构造在 `usage_sink=parent_ctx.usage_sink,` 后加 `kb_retrieval=parent_ctx.kb_retrieval,  # KB 检索绑定透传到子流程`。

- [ ] **Step 5: 回归**

Run: `cd backend && .venv/bin/python -m pytest tests/flow tests/rag -q && .venv/bin/python -m pytest -q`
Expected: PASS（既有用例未装配 `kb_retrieval` 的若含 KnowledgeSearch 检索路径需在测试 ctx 补 fake bindings——用最小 fake：`ctx = RunContext(..., kb_retrieval=object())` 不触发检索的用例不受影响；检索用例按 Task 4 的 `retrieve_hits` mock 处理）。

- [ ] **Step 6: Commit**

```bash
git add backend/app/flow_runtime/types.py backend/app/flow_runtime/nodes/rag_nodes.py backend/app/flow_runtime/subflow/resolve.py backend/app/integrations/langgraph/compiler/build.py backend/app/integrations/langgraph/compiler/run.py
git commit -m "refactor(flow): KnowledgeSearch 节点经 RunContext.kb_retrieval 装配检索绑定"
```

---

### Task 7: L1 装配点注入 bindings（chat_rag / flow debug-run）

**Files:**
- Modify: `backend/app/tenant/agents/services/agent/chat_rag.py`、`backend/app/tenant/flows/services/flow.py`

**Interfaces:**
- Consumes: `build_kb_retrieval_bindings`（Task 1）
- Produces: 全部生产检索路径（Agent RAG/无模型摘要、画布发布对话、画布 debug-run）获得 bindings

- [ ] **Step 1: chat_rag 装配**

`backend/app/tenant/agents/services/agent/chat_rag.py` 顶部加 `from app.tenant.kb.services.embeddings import build_kb_retrieval_bindings`。
1. `flow_run_context`（L78-92）RunContext 构造加 `kb_retrieval=build_kb_retrieval_bindings(),`。
2. `rag_chat` 的 LangGraph 分支：`run_rag_workflow(...)` 调用加 `bindings=build_kb_retrieval_bindings(),`；`rag_answer(...)` 调用加 `bindings=build_kb_retrieval_bindings(),`（两分支共享一个局部变量更佳：方法起始处 `kb_bindings = build_kb_retrieval_bindings()`，后续引用 `kb_bindings`）。
3. `rag_chat` 无模型摘要分支：`retrieve_hits(...)` 调用加 `bindings=kb_bindings,`（该变量在 `if not kb_ids` 前定义）。

- [ ] **Step 2: flow.py debug-run 装配**

`backend/app/tenant/flows/services/flow.py`：RunContext 构造（L245-258）加 `kb_retrieval=build_kb_retrieval_bindings(),`；顶部补对应 import。

- [ ] **Step 3: 回归 + 残留自检**

Run: `cd backend && .venv/bin/python -m pytest tests/tenant/agents tests/flow tests/rag -q && .venv/bin/python -m pytest -q`
Expected: PASS。
Run: `cd backend && rg -rn "app\.tenant\.(models\.services\.(embedding_resolve|rerank_resolve)|kb\.services\.search_log)" app/integrations app/rag app/flow_runtime`
Expected: 无输出（L3/L2/flow_runtime 对该三模块的 import 清零）。

- [ ] **Step 4: Commit**

```bash
git add backend/app/tenant/agents/services/agent/chat_rag.py backend/app/tenant/flows/services/flow.py
git commit -m "refactor(kb): L1 对话与画布入口装配 KB 检索绑定"
```

---

### Task 8: 收尾回归 / ruff / 残留审计 / layering 更新

**Files:**
- Modify: `docs/architecture/layering.md`（仓库根文档，B-1 同址）
- Test: 全量

- [ ] **Step 1: 全量回归 + ruff**

Run: `cd backend && .venv/bin/python -m pytest -q && .venv/bin/ruff check app/tenant/kb/services/embeddings.py app/integrations/langchain app/rag app/flow_runtime`
Expected: 全量 PASS（433 基线）；ruff 无报错（若因删函数残留未用 import，清理）。

- [ ] **Step 2: 残留 import 审计**

Run: `cd backend && rg -rn "from app\.tenant\.(models|kb\.services\.(search_log|embeddings|ingest))|import app\.tenant" app/integrations app/rag app/flow_runtime`
Expected: 无输出（`kb.models`/`models.*` ORM 类型 import 允许，可存在）。
Run: `cd backend && rg -n "resolve_embedding_model|resolve_rerank_model|write_kb_search_log" app/integrations`
Expected: 无输出。

- [ ] **Step 3: layering.md §2.2 更新**

在模型解析/用量记录收敛说明旁补 KB 检索绑定段：`integrations/langchain/{embeddings,visual_embeddings,vectorstores}.py` 与 `rag/`、`flow_runtime` 不再 import `tenant.models.services.{embedding_resolve,rerank_resolve}` 与 `tenant.kb.services.search_log`；kb 级向量化与绑定装配落 `tenant/kb/services/embeddings.py`；KbRetrievalBindings 通道经 RunContext/configurable。同步 §8 修订历史追加一行（日期、范围）。

- [ ] **Step 4: Commit**

```bash
git add docs/architecture/layering.md
git commit -m "docs(architecture): 记录 KB 检索绑定上移 L1 的分层收敛"
```

---

## Self-Review

**1. Spec coverage:**
- `embeddings.py`/`visual_embeddings.py` 对 `embedding_resolve` 反依赖 → Task 3（L3 文件瘦身/删除，函数迁 L1 kb 模块 Task 1）。
- `vectorstores.py` 对 `rerank_resolve`/`write_kb_search_log` 反依赖 → Task 2（bindings 显式化 + 日志绑定删除）+ Task 5-7（async/flow 装配通道）。
- 上层消费方全部适配：kb/search（Task 3）、kb/ingest + L2 pipeline（Task 4）、answer（Task 4）、runner/rag_qa（Task 5）、rag_nodes/RunContext/compiler/subflow（Task 6）、chat_rag/flow 装配（Task 7）。
- L2 `rag/pipeline/ingest.py` 直连 L3 视觉向量化的绕路（取证项）→ Task 4 Step 2 注入化。
- 测试/文档（Task 3 test import 修正、Task 8 回归与 layering）。
- 附加发现（langgraph runner 常量、rag_nodes PromptTemplate）不在本计划（B-2d 范畴）——标注排除。

**2. Placeholder scan:** 各 Step 均含完整代码/命令。Task 1 Step 1 测试中 local provider 维度字段在注释给出精确修正法（非占位：给定 `EXTRA_EMBEDDING_DIMENSION: 768` 值与 import 路径）。Task 3 Step 4 "若残留…则清理" 为确定性清理指令，非占位。无 TBD/TODO。

**3. Type consistency:** `KbRetrievalBindings` 字段（Task 1）与 vectorstores/answer/rag_qa/rag_nodes/RunContext/装配点引用一致；`build_kb_retrieval_bindings` 工厂贯穿 Task 1/7；`bindings` 形参名统一（runner/rag_answer/retrieve_hits/search_* 均用 `bindings`）；`kb_retrieval` 通道名统一（RunContext 字段、configurable key、state key、compiler/subflow 拷贝一致）。Task 4 删除的 `retrieve_hits_with_ctx` 在 Task 2 Step 2 已 rg 验证无调用方；Task 4 的 `rag_answer` 保留（供既有调用）。`search_multi_kb_async` 旧参数 `write_log/source/actor_user_id/agent_id` 在 Task 2 移除后，Task 4 answer.py 调用点同步为新签名，无遗漏。
