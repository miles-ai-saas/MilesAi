# B-2c 实施计划：generative 模型解析上移 L1（含 flow ctx 注入与 job 执行编排收口）

> **归档：** 已实施并合并（engine DI 收敛，2026-09-10 校核）。**收敛记录：** [layering.md](../../architecture/layering.md) §8；执行明细见 `.superpowers/sdd/progress.md`。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 消除 `integrations/generative/{image,tts,video}/service.py` 对 `tenant.models.services.model_resolve` 的反向 import——把 `resolve_image_gen_model`/`resolve_tts_model`/`resolve_video_gen_model` 与默认模型选取 `pick_default_generative_model` 收敛到 L1 新模块 `tenant/models/services/generative_model_resolve.py`；同步把 generative job 执行编排从 L3 `jobs/runner.py` 上移 L1，flow 画布生图/生视频节点改经 `RunContext` 注入解析器。

**Architecture:** 延续 B-1 / B-2b 的 **L1 装配 + 注入** 范式：

- 三个 L3 service 只保留「生成引擎」（`generate_*_for_model` 接收已解析 `ModelConfig`）；模型解析整体迁入 L1 `generative_model_resolve.py`（与 `model_resolve`/`embedding_resolve`/`rerank_resolve` 同目录对称）。
- `jobs/runner.py` 本质是「worker 内取 job → 合成 ctx → 解析 → 生成 → 落库」的用例编排，整体上移 L1 `tenant/generative/services/job_execution.py`（紧邻既有 `job.py`）。
- flow 画布生图/生视频节点同步分支不再 import 任何 resolver，改读 `RunContext.resolve_generative_image`/`resolve_generative_video`（签名与 L1 resolver 一致）；装配点 `chat_rag.flow_run_context` 与 `flow.py` debug ctx 注入 L1 函数引用。透传通道沿用 B-2b 已建通道（compiler state / run initial / subflow child ctx）。

**Tech Stack:** FastAPI / SQLAlchemy async / LangGraph（后端 `backend/`，pytest 验证）。

## Global Constraints

- 分层（[`layering.md`](../../architecture/layering.md) §2.2）：`integrations`（L3）与 `flow_runtime` 禁止 import `tenant`（L1）；允许 `tenant → integrations/generative` 单向。本计划完成后，`app/integrations/generative/{image,tts,video}/service.py`、`app/flow_runtime/` 内不得再出现 `app.tenant.models.services.model_resolve` / `app.tenant.models.services.generative_model_resolve` 的 import（含函数级 lazy）。L3 `generative/model_resolve.py` 删除。
- 中文 docstring（README §文档注释）：新增/改动模块须写模块与公开方法 docstring。
- 体量：改动文件不得超过 500 行；单文件 ≥400 行新增逻辑优先拆文件。
- 语义保持：解析优先级「显式 id > agent 绑定模型 > agent_config 默认 id > 租户/平台默认（vendor 优先）」与生成行为零变化；异步 job 的执行结果、进度消息、取消语义不变。
- 测试：全量回归通过（执行前先记录基线 `uv run pytest -q | tail -1`，与收尾对比不得减少）；为过测试不得修改非本计划文件语义。
- 提交：每任务单独 commit，message 简体中文，`<type>(<scope>): <简述>`（本系列统一 `engine` scope）。

---

### Task 1: generative job 执行编排上移 L1（`job_execution.py`）

**Files:**
- Create: `backend/app/tenant/generative/services/job_execution.py`
- Delete: `backend/app/integrations/generative/jobs/runner.py`
- Modify: `backend/app/integrations/generative/jobs/__init__.py`
- Modify: `backend/app/workers/tasks/generative.py`
- Modify: `backend/app/tenant/generative/services/job.py`
- Modify: `backend/app/tenant/agents/ws/job_watch.py`

**Interfaces:**
- Consumes: L3 `generate_image_for_model`/`generate_video_for_model`/`resolve_image_gen_model`/`resolve_video_gen_model`（`integrations.generative` 顶层，本 Task 未切换，Task 4 再切 resolve 到 L1）；L3 `jobs/errors`、`jobs/progress`、`persist`；`app.infra.db.get_worker_session`。
- Produces（供本计划后续 Task 与 workers/job 服务引用）:
  - `run_generative_video_job_async(job_id: UUID) -> None`
  - `run_generative_image_job_async(job_id: UUID) -> None`
  - `get_generative_job_for_tenant(db, ctx, job_id) -> GenerativeJob`

- [ ] **Step 1: 确认基线与无外部引用**

Run（backend/ 下）：
```bash
rg -n "generative\.jobs\.runner|jobs import.*runner|from app\.integrations\.generative\.jobs import" app tests
```
Expected：`app` 下仅 4 处 `from app.integrations.generative.jobs.runner import ...`（workers/tasks、tenant/generative/services/job.py、tenant/agents/ws/job_watch.py）；tests 无命中。

Run：`uv run pytest -q | tail -1` 记录基线条数（本计划收尾时对比）。

- [ ] **Step 2: 建立 L1 执行模块**

新建 `backend/app/tenant/generative/services/job_execution.py`：把 `integrations/generative/jobs/runner.py` 的全部内容**原样复制**（含 `run_generative_video_job_async`/`run_generative_image_job_async`/`get_generative_job_for_tenant`/`_sync_chat_after_job`/`_optional_uuid`，280 行整体移动、不改函数体），仅两处调整：

模块 docstring 改为：

```python
"""Worker 内执行 generative_jobs（asyncio）。

执行编排用例上移 L1（原 ``integrations/generative/jobs/runner.py``）：
worker 进程内取 job → 合成最小 TenantContext → 解析模型 → 调用 L3 生成引擎 → 落库/推送进度。
供 ``workers/tasks/generative.py``（Celery 任务）与 ``tenant.generative.services.job`` 查询复用。
"""
```

`_sync_chat_after_job` 的函数级 lazy import 保留原样（L1 → L1 合法）：

```python
async def _sync_chat_after_job(db, job: GenerativeJob) -> None:
    """任务终态写回对话消息，失败不影响主流程。"""
    try:
        from app.tenant.agents.services.chat_artifact_sync import sync_job_result_to_chat_messages

        await sync_job_result_to_chat_messages(db, job)
        await db.commit()
    except Exception:
        logger.exception("sync chat artifacts for generative job %s failed", job.id)
```

其余 import（顶层 `app.integrations.generative`、`jobs/errors`、`jobs/progress`、`persist`、`get_worker_session`、`GenerativeJob`、`User`、`TenantContext` 等）与全部函数体照搬。

- [ ] **Step 3: 删除 L3 runner 并收口 jobs/__init__**

删除 `backend/app/integrations/generative/jobs/runner.py`。

`backend/app/integrations/generative/jobs/__init__.py` 全文替换为：

```python
"""异步生成任务提交与执行。

- 提交：``submit_video_generative_job``（L1 ``job.py`` 调用）
- 执行编排：已上移 L1 ``tenant.generative.services.job_execution``（worker 用例）
"""

from app.integrations.generative.jobs.submit import submit_video_generative_job

__all__ = ["submit_video_generative_job"]
```

- [ ] **Step 4: 更新三处引用方**

`backend/app/workers/tasks/generative.py` 的 import 段（现 L11-16）改为：

```python
from app.integrations.generative.jobs.errors import GenerativeJobCancelled, GenerativeJobNotFound
from app.tenant.generative.services.job_execution import (
    run_generative_image_job_async,
    run_generative_video_job_async,
)
```

`backend/app/tenant/generative/services/job.py` L20 改为：

```python
from app.tenant.generative.services.job_execution import get_generative_job_for_tenant
```

`backend/app/tenant/agents/ws/job_watch.py` L16 改为：

```python
from app.tenant.generative.services.job_execution import get_generative_job_for_tenant
```

- [ ] **Step 5: 回归验证**

Run（backend/ 下）：
```bash
uv run ruff check app/tenant/generative/services/job_execution.py app/workers/tasks/generative.py app/tenant/generative/services/job.py app/tenant/agents/ws/job_watch.py app/integrations/generative/jobs
uv run pytest -q | tail -1
rg -n "generative\.jobs\.runner" app || echo "无残留 runner 引用"
```
Expected：ruff 无新错误；pytest 条数与 Step 1 基线一致；rg 无输出。

- [ ] **Step 6: Commit**

```bash
git add backend/app/tenant/generative/services/job_execution.py backend/app/integrations/generative/jobs/runner.py backend/app/integrations/generative/jobs/__init__.py backend/app/workers/tasks/generative.py backend/app/tenant/generative/services/job.py backend/app/tenant/agents/ws/job_watch.py
git commit -m "refactor(engine): generative job 执行编排由 L3 runner 上移 L1

worker 内取任务/合成租户上下文/落库属用例职责，与 L3 生成引擎解耦；
解析器切换 L1 见后续 generative_model_resolve 收敛。"
```

---

### Task 2: 建立 L1 解析模块 `generative_model_resolve`（TDD）

**Files:**
- Create: `backend/app/tenant/models/services/generative_model_resolve.py`
- Test: `backend/tests/tenant/generative/test_generative_model_resolve.py`（追加用例）

**Interfaces:**
- Consumes: `resolve_model_for_invoke`（`tenant/models/services/model_resolve.py`，同目录）、`ModelConfig`/`ModelCapabilityType`/`ModelVendor`（`app/models/model*.py`）；实现从 L3 三个 service 与 `model_resolve.py` 原样迁移。
- Produces（供 Task 3 装配点注入与 Task 4 调用方切换）:
  - `async pick_default_generative_model(db, *, model_type: str, tenant_id: UUID) -> ModelConfig | None`
  - `async resolve_image_gen_model(db, ctx, *, model_config_id, agent_model=None, agent_config=None) -> ModelConfig`
  - `async resolve_video_gen_model(db, ctx, *, model_config_id, agent_model=None, agent_config=None) -> ModelConfig`
  - `async resolve_tts_model(db, ctx, *, model_config_id, agent_model=None, agent_config=None) -> ModelConfig`

- [ ] **Step 1: 先写失败测试（三个优先级用例）**

在 `backend/tests/tenant/generative/test_generative_model_resolve.py` 顶部 import 区追加，并追加三个用例函数（文件已有 `_model` 帮助函数与 `ModelVendor`/`ModelCapabilityType` import，直接复用）：

```python
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from app.tenant.models.services import generative_model_resolve as gm


def _run(coro):
    return asyncio.run(coro)


def _async_db(row=None):
    """mock 异步会话：db.execute 返回 Result，scalar_one_or_none 命中 row。"""
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = row
    db.execute.return_value = result
    return db


def test_image_resolve_prefers_explicit_id_over_agent_model(monkeypatch):
    explicit = _model(ModelVendor.QWEN.value, ModelCapabilityType.IMAGE_GEN.value)
    agent_model = _model(ModelVendor.DOUBAO.value, ModelCapabilityType.IMAGE_GEN.value)
    seen: list = []

    async def fake_resolve(_db, model, _tenant_id):
        seen.append(model.id)
        return model

    monkeypatch.setattr(gm, "resolve_model_for_invoke", fake_resolve)

    async def forbidden_default(**kwargs):
        raise AssertionError("显式 id 命中后不应再取默认模型")

    monkeypatch.setattr(gm, "pick_default_generative_model", forbidden_default)
    ctx = SimpleNamespace(tenant_id=uuid4())

    db = _async_db(row=explicit)
    out = _run(gm.resolve_image_gen_model(db, ctx, model_config_id=explicit.id, agent_model=agent_model))
    assert out is explicit
    assert seen == [explicit.id]


def test_image_resolve_falls_back_to_agent_model(monkeypatch):
    agent_model = _model(ModelVendor.QWEN.value, ModelCapabilityType.IMAGE_GEN.value)
    seen: list = []

    async def fake_resolve(_db, model, _tenant_id):
        seen.append(model.id)
        return model

    monkeypatch.setattr(gm, "resolve_model_for_invoke", fake_resolve)

    async def forbidden_default(**kwargs):
        raise AssertionError("agent 绑定模型命中后不应再取默认")

    monkeypatch.setattr(gm, "pick_default_generative_model", forbidden_default)
    ctx = SimpleNamespace(tenant_id=uuid4())

    db = _async_db()  # 无显式 id，不应执行 SELECT
    out = _run(gm.resolve_image_gen_model(db, ctx, model_config_id=None, agent_model=agent_model))
    assert out is agent_model
    assert seen == [agent_model.id]


def test_video_resolve_falls_back_to_tenant_default(monkeypatch):
    wrong = _model(ModelVendor.DOUBAO.value, ModelCapabilityType.IMAGE_GEN.value)  # agent 绑 image_gen，与 video_gen 不匹配
    default_row = _model(ModelVendor.QWEN.value, ModelCapabilityType.VIDEO_GEN.value)
    seen: list = []

    async def fake_resolve(_db, model, _tenant_id):
        seen.append(model.id)
        return model

    monkeypatch.setattr(gm, "resolve_model_for_invoke", fake_resolve)

    async def pick_default(**kwargs):
        return default_row

    monkeypatch.setattr(gm, "pick_default_generative_model", pick_default)
    ctx = SimpleNamespace(tenant_id=uuid4())

    db = _async_db()
    out = _run(gm.resolve_video_gen_model(db, ctx, model_config_id=None, agent_model=wrong))
    assert out is default_row
    assert seen == [default_row.id]
```

- [ ] **Step 2: 运行确认失败**

Run（backend/ 下）：`uv run pytest tests/tenant/generative/test_generative_model_resolve.py -q`
Expected：FAIL——`ModuleNotFoundError: No module named 'app.tenant.models.services.generative_model_resolve'`（三个新用例 Error）。

- [ ] **Step 3: 新建 L1 解析模块（迁移实现）**

新建 `backend/app/tenant/models/services/generative_model_resolve.py`，全文如下（内容分别取自 L3 `model_resolve.py` 与三个 service 的 resolver，逐字迁移）：

```python
"""生成类模型（image_gen / video_gen / tts）解析入口（L1）。

对话/工具/画布链路解析可用生成模型的唯一 L1 归口：显式 ``model_config_id``
> agent 绑定模型（若类型匹配）> ``agent_config`` 中 ``generative_*_model_id``
> 租户/平台默认（``pick_default_generative_model``，vendor 优先），最后经
``resolve_model_for_invoke`` 合并 BYOK 凭证。

调用方：
- ``tenant.tools.builtins.generative``（工具 handler）
- ``tenant.generative.services.job_execution``（worker 编排，image/video）
- 画布生图/生视频节点：经 ``RunContext.resolve_generative_image/video`` 注入本模块函数引用
（见 ``flow_runtime/nodes/image_generate.py`` / ``video_generate.py``）。
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BadRequestError
from app.core.tenant import TenantContext
from app.models.model import ModelConfig
from app.models.model.catalog import ModelCapabilityType, ModelVendor
from app.tenant.models.services.model_resolve import resolve_model_for_invoke

# 未显式指定 model_config_id 时的厂商优先顺序：万相(qwen) → 豆包 → 其它
_VENDOR_PRIORITY = case(
    (ModelConfig.vendor == ModelVendor.QWEN.value, 0),
    (ModelConfig.vendor == ModelVendor.DOUBAO.value, 1),
    else_=2,
)


async def pick_default_generative_model(
    db: AsyncSession,
    *,
    model_type: str,
    tenant_id: UUID,
) -> ModelConfig | None:
    """
    在租户级、平台级各取一条启用的生成模型，按 vendor 优先级返回首个命中。

    ``image_gen`` / ``video_gen`` 均优先 ``vendor=qwen``（通义万相）。
    """
    for tid in (tenant_id, None):
        stmt = (
            select(ModelConfig)
            .where(
                ModelConfig.is_active.is_(True),
                ModelConfig.model_type == model_type,
            )
            .order_by(_VENDOR_PRIORITY, ModelConfig.created_at.desc())
            .limit(1)
        )
        if tid is not None:
            stmt = stmt.where(ModelConfig.tenant_id == tid)
        else:
            stmt = stmt.where(ModelConfig.tenant_id.is_(None))
        row = (await db.execute(stmt)).scalar_one_or_none()
        if row:
            return row
    return None


async def resolve_image_gen_model(
    db: AsyncSession,
    ctx: TenantContext,
    *,
    model_config_id: UUID | None,
    agent_model: ModelConfig | None = None,
    agent_config: dict | None = None,
) -> ModelConfig:
    """解析生图用 ModelConfig（显式 id > agent 配置 > 智能体绑定模型若为 image_gen）。"""
    cfg = agent_config or {}
    raw_id = model_config_id
    if not raw_id and cfg.get("generative_image_model_id"):
        raw_id = UUID(str(cfg["generative_image_model_id"]))

    if raw_id:
        row = (
            await db.execute(
                select(ModelConfig).where(
                    ModelConfig.id == raw_id,
                    ModelConfig.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        if not row:
            raise BadRequestError("生图模型配置不存在或已禁用")
        if row.model_type != ModelCapabilityType.IMAGE_GEN.value:
            raise BadRequestError(f"模型「{row.name}」不是 image_gen 类型")
        return await resolve_model_for_invoke(db, row, ctx.tenant_id)

    if agent_model and agent_model.model_type == ModelCapabilityType.IMAGE_GEN.value:
        return await resolve_model_for_invoke(db, agent_model, ctx.tenant_id)

    row = await pick_default_generative_model(
        db=db,
        model_type=ModelCapabilityType.IMAGE_GEN.value,
        tenant_id=ctx.tenant_id,
    )
    if not row:
        raise BadRequestError("未找到可用的 image_gen 模型，请配置通义万相或其它 image_gen 模型")
    return await resolve_model_for_invoke(db, row, ctx.tenant_id)


async def resolve_video_gen_model(
    db: AsyncSession,
    ctx: TenantContext,
    *,
    model_config_id: UUID | None,
    agent_model: ModelConfig | None = None,
    agent_config: dict | None = None,
) -> ModelConfig:
    """解析生视频模型：显式 id > ``generative_video_model_id`` > 租户/平台默认 video_gen。"""
    cfg = agent_config or {}
    raw_id = model_config_id
    if not raw_id and cfg.get("generative_video_model_id"):
        raw_id = UUID(str(cfg["generative_video_model_id"]))

    if raw_id:
        row = (
            await db.execute(
                select(ModelConfig).where(
                    ModelConfig.id == raw_id,
                    ModelConfig.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        if not row:
            raise BadRequestError("生视频模型配置不存在或已禁用")
        if row.model_type != ModelCapabilityType.VIDEO_GEN.value:
            raise BadRequestError(f"模型「{row.name}」不是 video_gen 类型")
        return await resolve_model_for_invoke(db, row, ctx.tenant_id)

    if agent_model and agent_model.model_type == ModelCapabilityType.VIDEO_GEN.value:
        return await resolve_model_for_invoke(db, agent_model, ctx.tenant_id)

    row = await pick_default_generative_model(
        db=db,
        model_type=ModelCapabilityType.VIDEO_GEN.value,
        tenant_id=ctx.tenant_id,
    )
    if not row:
        raise BadRequestError("未找到可用的 video_gen 模型，请配置通义万相生视频模型")
    return await resolve_model_for_invoke(db, row, ctx.tenant_id)


async def resolve_tts_model(
    db: AsyncSession,
    ctx: TenantContext,
    *,
    model_config_id: UUID | None,
    agent_model: ModelConfig | None = None,
    agent_config: dict | None = None,
) -> ModelConfig:
    """解析 TTS 模型：显式 id > agent_model > 租户/平台默认 tts。"""
    cfg = agent_config or {}
    raw_id = model_config_id
    if not raw_id and cfg.get("generative_tts_model_id"):
        raw_id = UUID(str(cfg["generative_tts_model_id"]))

    if raw_id:
        row = (
            await db.execute(
                select(ModelConfig).where(
                    ModelConfig.id == raw_id,
                    ModelConfig.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        if not row:
            raise BadRequestError("TTS 模型配置不存在或已禁用")
        if row.model_type != ModelCapabilityType.TTS.value:
            raise BadRequestError(f"模型「{row.name}」不是 tts 类型")
        return await resolve_model_for_invoke(db, row, ctx.tenant_id)

    if agent_model and agent_model.model_type == ModelCapabilityType.TTS.value:
        return await resolve_model_for_invoke(db, agent_model, ctx.tenant_id)

    row = await pick_default_generative_model(
        db=db,
        model_type=ModelCapabilityType.TTS.value,
        tenant_id=ctx.tenant_id,
    )
    if not row:
        raise BadRequestError("未找到可用的 tts 模型，请配置语音合成模型（如 DashScope CosyVoice）")
    return await resolve_model_for_invoke(db, row, ctx.tenant_id)
```

- [ ] **Step 4: 运行确认通过**

Run（backend/ 下）：`uv run pytest tests/tenant/generative/test_generative_model_resolve.py -q`
Expected：PASS（既有 2 用例 + 新 3 用例）。

- [ ] **Step 5: 全量回归 + Commit**

Run：`uv run ruff check app/tenant/models/services/generative_model_resolve.py`（无错误）后：
```bash
git add backend/app/tenant/models/services/generative_model_resolve.py backend/tests/tenant/generative/test_generative_model_resolve.py
git commit -m "refactor(engine): generative 三 service 模型解析收敛至 L1 新模块

image/tts/video 解析逻辑原封迁入 generative_model_resolve，先落位与
单测（含默认厂商优先级），L3 原实现待调用方切换后移除。"
```

---

### Task 3: flow 画布节点解析器改为 `RunContext` 注入并装配

**Files:**
- Modify: `backend/app/flow_runtime/types.py`
- Modify: `backend/app/flow_runtime/nodes/image_generate.py`
- Modify: `backend/app/flow_runtime/nodes/video_generate.py`
- Modify: `backend/app/integrations/langgraph/compiler/build.py`
- Modify: `backend/app/integrations/langgraph/compiler/run.py`
- Modify: `backend/app/flow_runtime/subflow/resolve.py`
- Modify: `backend/app/tenant/flows/services/flow.py`
- Modify: `backend/app/tenant/agents/services/agent/chat_rag.py`
- Test: `backend/tests/flow/test_generative_nodes.py`（新建）

**Interfaces:**
- Consumes: Task 2 的 `resolve_image_gen_model`/`resolve_video_gen_model`（注入到装配点）。
- Produces:
  - `RunContext.resolve_generative_image: Callable[..., Awaitable[ModelConfig]] | None`（签名同 L1 resolver：`(db, ctx, *, model_config_id, agent_model=None, agent_config=None) -> ModelConfig`；None = 未装配，节点同步分支直接报错）
  - `RunContext.resolve_generative_video: ... | None`（同上）

- [ ] **Step 1: 先写失败测试（未装配报错 + 装配后可同步执行）**

新建 `backend/tests/flow/test_generative_nodes.py`：

```python
"""画布生图/生视频节点：同步分支的模型解析器来自 RunContext 注入（L1）。"""

import asyncio
from uuid import uuid4

import pytest

from app.common.exceptions import BadRequestError
from app.flow_runtime.nodes import image_generate as image_node
from app.flow_runtime.nodes import video_generate as video_node
from app.flow_runtime.types import RunContext
from app.integrations.generative.types import ImageGenerateResult


def _run(coro):
    return asyncio.run(coro)


class _FakeSession:
    """替代 AsyncSessionLocal 的假会话（同步分支自开会话处使用）。"""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def commit(self):
        pass


def test_image_generate_sync_without_resolver_raises():
    ctx = RunContext(tenant_id=str(uuid4()), generative_image_async=False, agent_config={})
    node = {"prompt": "画一只猫", "model_config_id": str(uuid4())}
    with pytest.raises(BadRequestError):
        _run(image_node.image_generate(node, {}, ctx))


def test_video_generate_sync_without_resolver_raises():
    ctx = RunContext(tenant_id=str(uuid4()), generative_video_async=False)
    node = {"prompt": "一段小短片"}
    with pytest.raises(BadRequestError):
        _run(video_node.video_generate(node, {}, ctx))


def test_image_generate_sync_with_injected_resolver(monkeypatch):
    monkeypatch.setattr(image_node, "AsyncSessionLocal", _FakeSession)

    mid, att = uuid4(), uuid4()

    async def fake_resolve(db, ctx, *, model_config_id, agent_model=None, agent_config=None):
        assert model_config_id == mid
        return type("Model", (), {"id": mid})()

    async def fake_generate(db, ctx, model, **kwargs):
        return ImageGenerateResult(attachment_ids=[att], mime_type="image/png", media_asset_ids=[])

    monkeypatch.setattr(image_node, "generate_image_for_model", fake_generate)

    ctx = RunContext(
        tenant_id=str(uuid4()),
        user_id=str(uuid4()),  # tenant_context_from_run 需要 user_id
        generative_image_async=False,
        agent_config={},
        resolve_generative_image=fake_resolve,
    )
    node = {"prompt": "画一只猫", "model_config_id": str(mid)}
    out = _run(image_node.image_generate(node, {}, ctx))
    assert out["kind"] == "image"
    assert str(out["attachment_id"]) == str(att)
```

Run（backend/ 下）：`uv run pytest tests/flow/test_generative_nodes.py -q`
Expected：前两个 FAIL（`BadRequestError` 未抛出——当前同步分支直接 import 调用 resolver），第三个 Error（`TypeError: unexpected keyword argument 'resolve_generative_image'`）。

- [ ] **Step 2: `RunContext` 增加两个解析器字段**

`backend/app/flow_runtime/types.py` 的 `RunContext`（`kb_retrieval` 字段后）追加：

```python
    # 生图/生视频模型解析回调（L1 注入；签名同
    # ``tenant.models.services.generative_model_resolve.resolve_{image,video}_gen_model``；
    # None 表示未装配，ImageGenerate/VideoGenerate 同步分支直接报错）
    resolve_generative_image: Callable[..., Awaitable[ModelConfig]] | None = None
    resolve_generative_video: Callable[..., Awaitable[ModelConfig]] | None = None
```

- [ ] **Step 3: 节点同步分支改读注入解析器**

`backend/app/flow_runtime/nodes/image_generate.py`：

- 顶层 import 改为只取生成引擎：

```python
from app.integrations.generative import generate_image_for_model
```

- 同步分支（`async with AsyncSessionLocal() as db:` 之前）插入解析器获取与空值校验，并把调用点 `resolve_image_gen_model(...)` 替换为 `resolver(...)`：

```python
    resolver = ctx.resolve_generative_image
    if resolver is None:
        raise BadRequestError("生图模型解析器未装配（resolve_generative_image），无法同步生图")

    async with AsyncSessionLocal() as db:
        tenant_ctx = tenant_context_from_run(ctx)
        model = await resolver(
            db,
            tenant_ctx,
            model_config_id=UUID(str(model_id)),
            agent_config=ctx.agent_config,
        )
```

`backend/app/flow_runtime/nodes/video_generate.py` 同理：

```python
from app.integrations.generative import generate_video_for_model
```

```python
    resolver = ctx.resolve_generative_video
    if resolver is None:
        raise BadRequestError("生视频模型解析器未装配（resolve_generative_video），无法同步生视频")

    async with AsyncSessionLocal() as db:
        tenant_ctx = tenant_context_from_run(ctx)
        model = await resolver(
            db,
            tenant_ctx,
            model_config_id=model_id,
            agent_config=ctx.agent_config,
        )
```

- [ ] **Step 4: LangGraph 编译通道透传两个字段**

`backend/app/integrations/langgraph/compiler/build.py`：

- `_State`（`kb_retrieval: Any` 后）追加：

```python
        # L1 注入的生图/生视频模型解析回调（随 ctx 透传，ImageGenerate/VideoGenerate 同步分支）
        resolve_generative_image: Any
        resolve_generative_video: Any
```

- `run_node` 内 `RunContext(...)`（`kb_retrieval=state.get("kb_retrieval"),` 后）追加：

```python
                resolve_generative_image=state.get("resolve_generative_image"),
                resolve_generative_video=state.get("resolve_generative_video"),
```

`backend/app/integrations/langgraph/compiler/run.py` 的 `initial` dict（`"kb_retrieval": ctx.kb_retrieval,` 后）追加：

```python
        "resolve_generative_image": ctx.resolve_generative_image,
        "resolve_generative_video": ctx.resolve_generative_video,
```

- [ ] **Step 5: SubFlow 子 ctx 透传**

`backend/app/flow_runtime/subflow/resolve.py` 的 `RunContext(...)` 构造（`kb_retrieval=parent_ctx.kb_retrieval,` 后）追加：

```python
        resolve_generative_image=parent_ctx.resolve_generative_image,  # 画布生图模型解析器透传到子流程
        resolve_generative_video=parent_ctx.resolve_generative_video,  # 画布生视频模型解析器透传到子流程
```

- [ ] **Step 6: L1 装配点注入真实解析器**

`backend/app/tenant/flows/services/flow.py`：

- import 区（`from app.tenant.flows.services.run_context import make_flow_model_resolver` 附近）追加：

```python
from app.tenant.models.services.generative_model_resolve import (
    resolve_image_gen_model,
    resolve_video_gen_model,
)
```

- debug ctx 构造（`kb_retrieval=build_kb_retrieval_bindings(),` 后）追加：

```python
                resolve_generative_image=resolve_image_gen_model,
                resolve_generative_video=resolve_video_gen_model,
```

`backend/app/tenant/agents/services/agent/chat_rag.py`：

- import 区（`from app.tenant.models.services.model_resolve import resolve_model_for_invoke` 附近）追加：

```python
from app.tenant.models.services.generative_model_resolve import (
    resolve_image_gen_model,
    resolve_video_gen_model,
)
```

- `flow_run_context` 构造（`kb_retrieval=build_kb_retrieval_bindings(),` 后）追加：

```python
            resolve_generative_image=resolve_image_gen_model,
            resolve_generative_video=resolve_video_gen_model,
```

- [ ] **Step 7: 测试通过 + 回归**

Run（backend/ 下）：
```bash
uv run pytest tests/flow/test_generative_nodes.py tests/flow/test_flow_runtime_constants.py tests/flow/test_langgraph_compiler.py tests/flow/test_subflow.py -q
uv run pytest -q | tail -1
uv run ruff check app/flow_runtime/types.py app/flow_runtime/nodes/image_generate.py app/flow_runtime/nodes/video_generate.py app/integrations/langgraph/compiler/build.py app/integrations/langgraph/compiler/run.py app/flow_runtime/subflow/resolve.py app/tenant/flows/services/flow.py app/tenant/agents/services/agent/chat_rag.py tests/flow/test_generative_nodes.py
```
Expected：新测试 PASS；pytest 条数与 Task 1 基线一致（可能 +3）；ruff 无新错误。

- [ ] **Step 8: Commit**

```bash
git add backend/app/flow_runtime/types.py backend/app/flow_runtime/nodes/image_generate.py backend/app/flow_runtime/nodes/video_generate.py backend/app/integrations/langgraph/compiler/build.py backend/app/integrations/langgraph/compiler/run.py backend/app/flow_runtime/subflow/resolve.py backend/app/tenant/flows/services/flow.py backend/app/tenant/agents/services/agent/chat_rag.py backend/tests/flow/test_generative_nodes.py
git commit -m "refactor(engine): 画布生图/生视频节点模型解析改由 RunContext 注入

节点不再 import L1 解析器，同步分支自 ctx 取 resolve_generative_image/video，
装配点在 flow debug 与 agent 对话入口注入，为移除 L3 解析实现铺路。"
```

---

### Task 4: 三 service 移除解析实现并收口 L3 导出

**Files:**
- Modify: `backend/app/integrations/generative/image/service.py`
- Modify: `backend/app/integrations/generative/video/service.py`
- Modify: `backend/app/integrations/generative/tts/service.py`
- Modify: `backend/app/integrations/generative/__init__.py`
- Modify: `backend/app/integrations/generative/tts/__init__.py`
- Modify: `backend/app/integrations/generative/registry.py`
- Delete: `backend/app/integrations/generative/model_resolve.py`
- Modify: `backend/app/tenant/tools/builtins/generative.py`
- Modify: `backend/app/tenant/generative/services/job_execution.py`

**Interfaces:**
- Consumes: Task 1 `job_execution.py`、Task 2 `generative_model_resolve.py`、Task 3 ctx 注入完成（此时无 L3/flow 调用方再 import L3 resolve）。
- Produces: 收敛终态——`app/integrations/generative/{image,tts,video}/service.py` 只保留 `generate_*_for_model` 引擎；L3 不再存在任何解析实现。

- [ ] **Step 1: 前置确认无残留引用方**

Run（backend/ 下）：
```bash
rg -n "resolve_(image|video|tts)_gen_model|pick_default_generative_model" app/flow_runtime app/rag app/tenant/tools app/tenant/agents/ws app/tenant/generative/services app/workers
```
Expected：`app/tenant/tools/builtins/generative.py` 3 处、`app/tenant/generative/services/job_execution.py` 2 处（Task 4 即将切换）；`flow_runtime`/`rag`/`workers` 无命中（Task 1/3 已清理）。

- [ ] **Step 2: 三个 service 删除 resolver 与相关 import**

`image/service.py`：
- 删除 `resolve_image_gen_model` 整个函数（docstring 起至 `return await resolve_model_for_invoke(...)` 结束的完整函数块）。
- 删除顶层 import：`from app.integrations.generative.model_resolve import pick_default_generative_model`、`from app.tenant.models.services.model_resolve import resolve_model_for_invoke`。
- 删除仅被 resolver 使用的 `from sqlalchemy import select`。
- 保留：`UUID`、`AsyncSession`、`BadRequestError`、`TenantContext`、`ModelConfig`、`ModelCapabilityType`（`_generate_bytes` 用）、`resolve_invoke_mode` 等。

`video/service.py`：同上（删除 `resolve_video_gen_model`、两个 L1/L3 import 行、仅 resolver 用的 `from sqlalchemy import select`）。

`tts/service.py`：同上（删除 `resolve_tts_model`、两个 import 行、仅 resolver 用的 `select`）。

删完后可用 `uv run ruff check <file> --fix` 自动收敛未使用 import（仅清理本任务删除引入的 F401，勿动其它历史告警）。

- [ ] **Step 3: 收口 L3 导出与删除 model_resolve 模块**

`backend/app/integrations/generative/__init__.py` 全文替换（re-export 仅保留生成引擎；docstring 注明解析已上移 L1）：

```python
"""
文生图 / 生视频 / TTS 集成（不走 LiteLLM chat）。

- 智能体：``generate_image`` / ``generate_video`` / ``generate_speech`` 内置工具 → ``tenant.tools.invoke``
- 流程画布：``ImageGenerate`` / ``VideoGenerate`` 节点 → ``flow_runtime.nodes.*``
- 厂商：``httpx`` 直调；万相见 ``dashscope_client``；豆包视频见 ``volcengine_client`` / ``volcengine_video``
- TTS：DashScope CosyVoice → ``tts/providers/dashscope_tts``
- 产出物：``persist_generated_bytes`` 写入对象存储；预览走鉴权 ``GET /attachments/{id}/content``，非签名 URL

模型解析（``resolve_image_gen_model`` / ``resolve_video_gen_model`` / ``resolve_tts_model`` /
``pick_default_generative_model``）已上移 L1 ``tenant.models.services.generative_model_resolve``，
本层只暴露接收已解析 ``ModelConfig`` 的生成引擎。
"""

from app.integrations.generative.image.service import generate_image_for_model
from app.integrations.generative.tts.service import generate_speech_for_model
from app.integrations.generative.types import ImageGenerateResult, VideoGenerateResult
from app.integrations.generative.video.service import generate_video_for_model

__all__ = [
    "ImageGenerateResult",
    "VideoGenerateResult",
    "generate_image_for_model",
    "generate_speech_for_model",
    "generate_video_for_model",
]
```

`backend/app/integrations/generative/tts/__init__.py` 全文替换：

```python
"""TTS 语音合成 Integration Layer（re-export service 入口；模型解析见 L1 ``generative_model_resolve``）。"""

from app.integrations.generative.tts.service import generate_speech_for_model

__all__ = ["generate_speech_for_model"]
```

删除 `backend/app/integrations/generative/model_resolve.py`。

`backend/app/integrations/generative/registry.py` 模块 docstring 第 9 行（`未指定 ``model_config_id`` 时默认模型由 ``model_resolve.pick_default_generative_model``` 所在句）改为：

```text
未指定 ``model_config_id`` 时默认模型由 L1 ``tenant.models.services.generative_model_resolve.pick_default_generative_model`` 选取
```

- [ ] **Step 4: 调用方解析 import 切换到 L1**

`backend/app/tenant/tools/builtins/generative.py`：

- 模块 docstring 倒数第 3 行（`→ 本模块 ``handle_generate_*`` → ``integrations.generative`` 解析模型并生成附件。`）改为 `→ 本模块 ``handle_generate_*`` → L1 解析模型 + ``integrations.generative`` 生成引擎。`
- L18 顶层 import 拆分（生成引擎走 L3，解析走 L1）：

```python
from app.integrations.generative import generate_speech_for_model
from app.tenant.models.services.generative_model_resolve import resolve_tts_model
```

- L108（`handle_generate_video` 内）函数级 import 拆分：

```python
    from app.integrations.generative import generate_video_for_model
    from app.tenant.models.services.generative_model_resolve import resolve_video_gen_model
```

- L202（`handle_generate_image` 内）函数级 import 拆分：

```python
    from app.integrations.generative import generate_image_for_model
    from app.tenant.models.services.generative_model_resolve import resolve_image_gen_model
```

`backend/app/tenant/generative/services/job_execution.py` 顶层 import（`from app.integrations.generative import (...)` 块）改为：

```python
from app.integrations.generative import generate_image_for_model, generate_video_for_model
from app.tenant.models.services.generative_model_resolve import (
    resolve_image_gen_model,
    resolve_video_gen_model,
)
```

（`resolve_*` 从 L3 顶层包 import 移至 L1；函数体调用不变。）

- [ ] **Step 5: 验证 L3 反依赖清零**

Run（backend/ 下）：
```bash
uv run ruff check app/integrations/generative app/tenant/tools/builtins/generative.py app/tenant/generative/services/job_execution.py
rg -n "app\.tenant\.models\.services" app/integrations app/rag app/flow_runtime || echo "integrations/rag/flow_runtime 对 tenant.models.services 引用清零"
rg -n "resolve_(image|video|tts)_gen_model|pick_default_generative_model" app/integrations app/flow_runtime || echo "L3/flow 内无生成模型解析符号"
uv run pytest -q | tail -1
```
Expected：ruff 无新错误；两条 rg 均无命中（echo 兜底）；pytest 条数与 Task 1 基线一致。`app/rag` 若对 `tenant.models.services` 存在历史引用且与生成解析无关，仅记录不动（本计划范围限定 generative 解析）。

- [ ] **Step 6: Commit**

```bash
git add backend/app/integrations/generative/image/service.py backend/app/integrations/generative/video/service.py backend/app/integrations/generative/tts/service.py backend/app/integrations/generative/__init__.py backend/app/integrations/generative/tts/__init__.py backend/app/integrations/generative/registry.py backend/app/integrations/generative/model_resolve.py backend/app/tenant/tools/builtins/generative.py backend/app/tenant/generative/services/job_execution.py
git commit -m "refactor(engine): generative 三 service 解析实现移除并收口 L3 导出

resolve_*_gen_model 与 pick_default_generative_model 由 L1 generative_model_resolve
承接，工具 handler 与 job_execution 切 L1 后删除 L3 实现与 model_resolve 模块，
integrations/flow_runtime 对 tenant.models.services 引用清零。"
```

---

### Task 5: 回归审计与 `layering.md` 收敛记录

**Files:**
- Modify: `docs/architecture/layering.md`

- [ ] **Step 1: 全量回归 + 定向 rg 终审**

Run（backend/ 下）：
```bash
uv run ruff check app/tenant/models/services/generative_model_resolve.py app/tenant/generative/services/job_execution.py app/integrations/generative app/flow_runtime/nodes app/integrations/langgraph/compiler app/flow_runtime/types.py app/flow_runtime/subflow/resolve.py
rg -n "app\.tenant\.models\.services" app/integrations app/rag app/flow_runtime || echo "integrations/rag/flow_runtime 对 tenant.models.services 引用清零"
rg -n "generative_model_resolve" app/flow_runtime app/integrations || echo "L3/flow 内无 generative_model_resolve 引用"
uv run pytest -q | tail -1
```
Expected：ruff 无错误；rg 无输出；pytest 条数 ≥ Task 1 基线。

- [ ] **Step 2: 更新收敛记录**

`docs/architecture/layering.md`：

- L101（2026-09-08 B-1 收敛记录）句尾「残留在 `integrations`（embeddings/visual_embeddings/vectorstores/generative）与 flow `grade_nodes` 的反依赖归入 B-2 收敛。」改为：

```text
；`grade_nodes`、KB 向量化/检索绑定（B-2b，见下）与 `generative` 模型解析（B-2c，见下）已随后收敛。
```

- 在 L103（B-2b 收敛记录）之后追加一段：

```markdown
> **收敛记录（2026-09-09，B-2c）**：generative 模型解析与 job 执行编排上移 L1——`resolve_image_gen_model`/`resolve_tts_model`/`resolve_video_gen_model`/`pick_default_generative_model` 落 `tenant/models/services/generative_model_resolve.py`，`integrations/generative/{image,tts,video}/service.py` 只保留生成引擎，`generative/model_resolve.py` 已删除；worker 编排 `run_generative_{image,video}_job_async` 由 L3 `jobs/runner.py` 上移 L1 `tenant/generative/services/job_execution.py`；画布生图/生视频节点经 `RunContext.resolve_generative_image/video` 注入（见 plan [`2026-09-09-engine-di-generative-model-resolve`](../plans/2026-09-09-engine-di-generative-model-resolve.md)）。`integrations`/`rag`/`flow_runtime` 对 `tenant.models.services` 引用清零。
```

- §8 修订记录表（L350 B-2b 行后）追加一行：

```markdown
| 2026-09-09 | B-2c：generative 模型解析收敛 L1 `generative_model_resolve`，`integrations/generative` 三 service 只留生成引擎；job 执行编排上移 L1 `job_execution`；画布生图/生视频节点解析器经 `RunContext` 注入 |
```

- [ ] **Step 3: Commit**

```bash
git add docs/architecture/layering.md
git commit -m "docs(architecture): 记录 B-2c generative 模型解析与执行编排收敛"
```

---

## Self-Review

- **Spec coverage**：目标（三 service 去 `model_resolve` 反依赖）由 Task 2（L1 落位）+ Task 4（删除 L3 实现与导出）达成；连带约束逐项闭环——Task 1 job 执行编排 L1 化、Task 3 flow ctx 注入与编译器透传、Task 5 文档与终审。解析优先级、异步 job 取消/进度语义在各 Task 中明确「逐字迁移、不改函数体」。
- **Placeholder scan**：无 TBD/「适当处理」类占位；每个代码步骤含完整可粘贴代码或「文件整体迁移 + 三处 import 改法」的精确指令（Task 1 的 runner 属整文件移动，函数体零改动，由 rg + pytest 验证等价）。
- **Type consistency**：Task 2 定义的四个函数签名在 Task 3（`RunContext` 字段注释 + 装配点注入函数引用）与 Task 4（tools handler / job_execution 调用）中被一致引用；`resolve_*_gen_model(db, ctx, *, model_config_id, agent_model=None, agent_config=None)` 全程同一形态；字段名 `resolve_generative_image`/`resolve_generative_video` 在 types.py、build.py、run.py、subflow、flow.py、chat_rag.py、节点代码间一致。
