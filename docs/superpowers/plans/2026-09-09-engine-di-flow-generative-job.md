# B-2e 实施计划：画布生图/生视频节点异步 job 提交上移 L1（RunContext.submit_* 注入）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 消除 `flow_runtime/nodes/{image_generate,video_generate}.py` 对 `tenant.generative.{schemas.job, services.job}` 的运行期反依赖——把画布生图/生视频节点的**异步 job 提交流程**从 L3 节点上移 L1（`tenant/generative/services/job_execution.py`），节点经 `RunContext.submit_generative_image/video` 注入回调提交（与 B-2c 已收敛的同步 resolver 注入同构）。

**Architecture:**

- **回调注入**：`RunContext` 新增 `submit_generative_image` / `submit_generative_video` 两回调字段（L1 装配注入；None 表示 Celery 异步未启用/未装配）。
- **语义等价分支判断**：节点现状为
  `if ctx.generative_image_async and GenerativeJobService.image_async_enabled():` → 异步提交，否则走同步 resolver 兜底。
  而 `image_async_enabled()` 即 `get_settings().generative_image_async`（静态配置）。装配点（L1）按该配置注入回调或 None，节点改为
  `if ctx.generative_image_async and ctx.submit_generative_image is not None:` → 异步提交。
  配置为 False 时 submit=None → 节点落同步分支（旧逻辑同样如此），**行为零偏移**；节点不再 import `GenerativeJobService`。
- **L1 提交回调**：`job_execution.py`（B-2c 后承载 worker 执行编排的 L1 模块）新增 `submit_generative_image_job` / `submit_generative_video_job`，接收节点提取的**原子参数**，内部构造 `ImageGenerativeJobCreate`/`VideoGenerativeJobCreate` 并调 `GenerativeJobService.submit_*`（函数级 import 规避 `job.py` ↔ `job_execution.py` 的顶层循环），返回 job id（原节点即用 `str(out.id)` 且 `commit` 前可用，语义保持）。
- 透传链：`RunContext` → LangGraph `compiler/build.py` + `compiler/run.py` → `flow_runtime/subflow/resolve.py`，与既有 `resolve_generative_*` 完全同构。

**Tech Stack:** FastAPI / SQLAlchemy async / Celery / LangGraph（后端 `backend/`，pytest 验证）。

## Global Constraints

- 分层（[`layering.md`](../../architecture/layering.md) §2.2）：`flow_runtime`（L3）禁止 import `tenant`（L1）。本计划完成后 `flow_runtime/nodes/{image_generate,video_generate}.py` 内不得再出现 `from app.tenant.generative` import；`app/integrations/langgraph/compiler/*.py`、`app/flow_runtime/subflow/resolve.py` 仅透传回调引用（不 import `tenant`）。
- 语义保持（逐点核验）：
  - 异步分支仅在「`ctx.generative_{image,video}_async` 为真 **且** settings 异步启用」时进入——与现状 `ctx.generative_image_async and GenerativeJobService.image_async_enabled()` 等价（装配点用同一 settings 决定注入与否）；
  - 提交参数与 `submit_image`/`submit_video` 原接收完全一致：`prompt`、`size`(str|None, image)、`n`(int, image)、`duration`(int, video)、`resolution`(str|None, video)、`image_attachment_id`、`last_frame_attachment_id`(video)、`model_config_id`、`source="flow_node"`、`agent_id`、`agent_config`、`trace_id=get_trace_id()`；
  - 返回 pending dict 形状（`kind/status/generative_job_id/message`）不变；`AsyncSessionLocal` 会话与 `tenant_context_from_run(ctx)` 仍在节点开启（同同步分支），`await db.commit()` 后返回；
  - 同步分支（resolver 路径）**不改动**。
- 中文 docstring：新增/改动模块须写模块与公开函数 docstring。
- 体量：改动文件不得超过 500 行。
- 测试：每任务跑指定 pytest + 全量回归（`uv run python -m pytest`，基线 **447 passed**；`uv run` 若弄脏 `backend/uv.lock` 须 `git checkout -- backend/uv.lock` 还原）；收尾不得少于基线。
- 提交：每任务单独 commit，message 简体中文 `<type>(<scope>): <简述>`（scope `engine`）。

---

### Task 1: L1 提交回调 `submit_generative_{image,video}_job`（TDD）

**Files:**
- Modify: `backend/app/tenant/generative/services/job_execution.py`
- Test: `backend/tests/tenant/generative/test_job_execution_submitters.py`（新建）

**Interfaces:**
- Consumes: `ImageGenerativeJobCreate`/`VideoGenerativeJobCreate`（`tenant.generative.schemas.job`）、`GenerativeJobService`（`tenant.generative.services.job`，**函数级 import**）、`get_trace_id`（`app.common.trace`）。
- Produces（Task 2/4 使用，签名精确）:
  - `submit_generative_image_job(db, tenant_ctx, *, prompt: str, size: str | None, n: int, image_attachment_id: UUID | None, model_config_id: UUID, agent_id: UUID | None, agent_config: dict | None = None) -> UUID`
  - `submit_generative_video_job(db, tenant_ctx, *, prompt: str, duration: int, resolution: str | None, image_attachment_id: UUID | None, last_frame_attachment_id: UUID | None, model_config_id: UUID | None, agent_id: UUID | None, agent_config: dict | None = None) -> UUID`

- [ ] **Step 1: 先写失败测试**

新建 `backend/tests/tenant/generative/test_job_execution_submitters.py`：

```python
"""job_execution 画布 job 提交回调：构造 JobCreate 并委托 GenerativeJobService.submit_*。"""

import asyncio
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.core.tenant import TenantContext
from app.infra.db import AsyncSession
from app.tenant.generative.services import job_execution


def _run(coro):
    return asyncio.run(coro)


class _FakeJobService:
    """替身 GenerativeJobService：记录入参，返回假 job（id 可用）。"""

    def __init__(self, db, ctx, *, submit_image=None, submit_video=None):
        self._db = db
        self._ctx = ctx
        self._submit_image = submit_image
        self._submit_video = submit_video

    async def submit_image(self, body, **kwargs):
        return await self._submit_image(self, body, kwargs)

    async def submit_video(self, body, **kwargs):
        return await self._submit_video(self, body, kwargs)


def _make_fake(job_id, captures):
    async def _submit_image(svc, body, kwargs):
        captures.append(("image", body, kwargs))
        return SimpleNamespace(id=job_id)

    async def _submit_video(svc, body, kwargs):
        captures.append(("video", body, kwargs))
        return SimpleNamespace(id=job_id)

    return _FakeJobService(None, None, submit_image=_submit_image, submit_video=_submit_video)


@pytest.fixture()
def fake_job_service(monkeypatch):
    import app.tenant.generative.services.job as job_module

    job_id = uuid4()
    captures = []
    # 回调内函数级 `from ...services.job import GenerativeJobService` 每次调用时
    # 读取 job 模块属性，故须 patch job 模块而非 job_execution
    monkeypatch.setattr(
        job_module,
        "GenerativeJobService",
        lambda db, ctx: _make_fake(job_id, captures),
    )
    return SimpleNamespace(job_id=job_id, captures=captures)


def _tenant_ctx() -> TenantContext:
    return TenantContext(
        user_id=uuid4(),
        tenant_id=uuid4(),
        username="t",
        is_superuser=False,
        permissions=frozenset(),
    )


def test_submit_generative_image_job_delegates(fake_job_service, monkeypatch):
    monkeypatch.setattr(job_execution, "get_trace_id", lambda: "trace-1")
    pid, mid, aid = uuid4(), uuid4(), uuid4()
    out_id = _run(
        job_execution.submit_generative_image_job(
            None,
            _tenant_ctx(),
            prompt="画猫",
            size="1024x1024",
            n=2,
            image_attachment_id=aid,
            model_config_id=mid,
            agent_id=pid,
            agent_config={"_k": "v"},
        )
    )
    assert out_id == fake_job_service.job_id
    (kind, body, kwargs) = fake_job_service.captures[0]
    assert kind == "image"
    assert body.prompt == "画猫"
    assert body.size == "1024x1024"
    assert body.n == 2
    assert body.image_attachment_id == aid
    assert body.model_config_id == mid
    assert kwargs["source"] == "flow_node"
    assert kwargs["agent_id"] == pid
    assert kwargs["agent_config"] == {"_k": "v"}
    assert kwargs["trace_id"] == "trace-1"


def test_submit_generative_video_job_delegates(fake_job_service, monkeypatch):
    monkeypatch.setattr(job_execution, "get_trace_id", lambda: "trace-2")
    pid, mid, first, last = uuid4(), uuid4(), uuid4(), uuid4()
    out_id = _run(
        job_execution.submit_generative_video_job(
            None,
            _tenant_ctx(),
            prompt="一段短片",
            duration=5,
            resolution="720P",
            image_attachment_id=first,
            last_frame_attachment_id=last,
            model_config_id=mid,
            agent_id=pid,
            agent_config=None,
        )
    )
    assert out_id == fake_job_service.job_id
    (kind, body, kwargs) = fake_job_service.captures[0]
    assert kind == "video"
    assert body.prompt == "一段短片"
    assert body.duration == 5
    assert body.resolution == "720P"
    assert body.image_attachment_id == first
    assert body.last_frame_attachment_id == last
    assert body.model_config_id == mid
    assert kwargs["source"] == "flow_node"
    assert kwargs["agent_id"] == pid
    assert kwargs["agent_config"] == {}
```

- [ ] **Step 2: 运行确认失败**

Run（backend/ 下）：`uv run python -m pytest tests/tenant/generative/test_job_execution_submitters.py -q`
Expected：FAIL——`ImportError`（`job_execution` 尚无 `submit_generative_*`）。

- [ ] **Step 3: 实现回调**

`backend/app/tenant/generative/services/job_execution.py`：
- 顶部 import 区追加 `from app.common.trace import get_trace_id`（若无）；函数级 import 放回调内。
- 模块 docstring 末追加一句说明：画布异步提交回调亦在本模块装配（`RunContext.submit_generative_*`）。
- 在文件末尾（`get_generative_job_for_tenant` 之前或之后均可）追加：

```python
async def submit_generative_image_job(
    db,
    tenant_ctx: TenantContext,
    *,
    prompt: str,
    size: str | None,
    n: int,
    image_attachment_id: UUID | None,
    model_config_id: UUID,
    agent_id: UUID | None,
    agent_config: dict | None = None,
) -> UUID:
    """画布 ImageGenerate 异步分支提交回调（L1 装配注入 RunContext）。

    函数级 import ``GenerativeJobService`` 避免 ``services.job`` 顶层循环依赖；
    仅构造 JobCreate 并提交，会话提交（``db.commit``）由节点统一执行。
    """
    from app.tenant.generative.schemas.job import ImageGenerativeJobCreate
    from app.tenant.generative.services.job import GenerativeJobService

    body = ImageGenerativeJobCreate(
        prompt=prompt,
        size=size,
        n=n,
        image_attachment_id=image_attachment_id,
        model_config_id=model_config_id,
    )
    out = await GenerativeJobService(db, tenant_ctx).submit_image(
        body,
        source="flow_node",
        agent_id=agent_id,
        agent_config=agent_config or {},
        trace_id=get_trace_id(),
    )
    return out.id


async def submit_generative_video_job(
    db,
    tenant_ctx: TenantContext,
    *,
    prompt: str,
    duration: int,
    resolution: str | None,
    image_attachment_id: UUID | None,
    last_frame_attachment_id: UUID | None,
    model_config_id: UUID | None,
    agent_id: UUID | None,
    agent_config: dict | None = None,
) -> UUID:
    """画布 VideoGenerate 异步分支提交回调（L1 装配注入 RunContext）。"""
    from app.tenant.generative.schemas.job import VideoGenerativeJobCreate
    from app.tenant.generative.services.job import GenerativeJobService

    body = VideoGenerativeJobCreate(
        prompt=prompt,
        duration=duration,
        resolution=resolution,
        image_attachment_id=image_attachment_id,
        last_frame_attachment_id=last_frame_attachment_id,
        model_config_id=model_config_id,
    )
    out = await GenerativeJobService(db, tenant_ctx).submit_video(
        body,
        source="flow_node",
        agent_id=agent_id,
        agent_config=agent_config or {},
        trace_id=get_trace_id(),
    )
    return out.id
```

- [ ] **Step 4: 运行确认通过**

Run（backend/ 下）：
```bash
uv run python -m pytest tests/tenant/generative/test_job_execution_submitters.py -q
uv run ruff check app/tenant/generative/services/job_execution.py tests/tenant/generative/test_job_execution_submitters.py
```
Expected：2 passed；ruff 全绿。

- [ ] **Step 5: Commit**

```bash
git add backend/app/tenant/generative/services/job_execution.py backend/tests/tenant/generative/test_job_execution_submitters.py
git commit -m "refactor(engine): job_execution 增画布生图/生视频提交回调

submit_generative_{image,video}_job 供 RunContext 注入，节点提交参数
在 L1 构造 JobCreate 并委托 GenerativeJobService。"
```

---

### Task 2: `RunContext` 字段与 LangGraph/subflow 透传（机械）

**Files:**
- Modify: `backend/app/flow_runtime/types.py`
- Modify: `backend/app/integrations/langgraph/compiler/build.py`
- Modify: `backend/app/integrations/langgraph/compiler/run.py`
- Modify: `backend/app/flow_runtime/subflow/resolve.py`

**Interfaces:**
- Consumes: Task 1 两回调函数引用（本任务仅类型占位与透传，不 import `tenant`）。
- Produces: `RunContext.submit_generative_image` / `submit_generative_video`（None 默认，语义见约束）。

- [ ] **Step 1: `types.py` 追加字段**

`RunContext` 中 `resolve_generative_image`/`resolve_generative_video`（现 L70-71）之后追加：

```python
    # 生图/生视频异步 job 提交回调（L1 注入；None 表示 Celery 异步未启用/未装配，
    # ImageGenerate/VideoGenerate 节点落同步 resolver 分支）
    submit_generative_image: Callable[..., Awaitable[Any]] | None = None
    submit_generative_video: Callable[..., Awaitable[Any]] | None = None
```

（`Callable`/`Awaitable` 已在 `types.py` 顶部 import，无需新增。）

- [ ] **Step 2: `compiler/build.py` 透传**

- `run_node` 内构造 `RunContext` 的 `replace(...)`（现 L84-85 `resolve_generative_*` 行）之后追加：

```python
                submit_generative_image=state.get("submit_generative_image"),
                submit_generative_video=state.get("submit_generative_video"),
```

- `_State` TypedDict（现 L125-126 附近）追加：

```python
        # L1 注入的生图/生视频异步 job 提交回调（随 ctx 透传，ImageGenerate/VideoGenerate 异步分支）
        submit_generative_image: Any
        submit_generative_video: Any
```

- [ ] **Step 3: `compiler/run.py` initial dict 透传**

现 L41-42（`resolve_generative_*`）之后追加：

```python
        "submit_generative_image": ctx.submit_generative_image,
        "submit_generative_video": ctx.submit_generative_video,
```

- [ ] **Step 4: `subflow/resolve.py` 子 RunContext 透传**

现 L159-160（`resolve_generative_*`）之后追加：

```python
        submit_generative_image=parent_ctx.submit_generative_image,  # 生图异步提交回调透传到子流程
        submit_generative_video=parent_ctx.submit_generative_video,  # 生视频异步提交回调透传到子流程
```

- [ ] **Step 5: 验证 + Commit**

Run（backend/ 下）：
```bash
uv run ruff check app/flow_runtime/types.py app/integrations/langgraph/compiler/build.py app/integrations/langgraph/compiler/run.py app/flow_runtime/subflow/resolve.py
uv run python -m pytest tests/flow/test_generative_nodes.py tests/flow/test_subflow.py tests/flow/test_langgraph_compiler.py -q
```
Expected：ruff 全绿；定向测试通过（默认 None 不影响既有用例）。

```bash
git add backend/app/flow_runtime/types.py backend/app/integrations/langgraph/compiler/build.py backend/app/integrations/langgraph/compiler/run.py backend/app/flow_runtime/subflow/resolve.py
git commit -m "refactor(engine): RunContext 增生图/生视频异步提交回调并透传画布链路

submit_generative_{image,video} 沿 resolve_generative_* 既有通道经
LangGraph state/initial 与 subflow 子 RunContext 透传。"
```

---

### Task 3: 节点异步分支改经 `ctx.submit_generative_*`（TDD）

**Files:**
- Modify: `backend/app/flow_runtime/nodes/image_generate.py`
- Modify: `backend/app/flow_runtime/nodes/video_generate.py`
- Test: `backend/tests/flow/test_generative_nodes.py`（追加用例）

**Interfaces:**
- Consumes: Task 2 `RunContext.submit_generative_*`。
- Produces: 收敛终态——两节点不再 import `tenant.generative.{schemas.job, services.job}`；异步分支条件 `ctx.generative_*_async and ctx.submit_* is not None`。

- [ ] **Step 1: 先写失败测试（追加到 `tests/flow/test_generative_nodes.py`）**

在文件末追加（复用 `_run`/`_FakeSession`）：

```python
def test_image_generate_async_submits_via_callback(monkeypatch):
    monkeypatch.setattr(image_node, "AsyncSessionLocal", _FakeSession)

    mid, att, job = uuid4(), uuid4(), uuid4()

    async def fake_submit(db, tenant_ctx, *, prompt, size, n, image_attachment_id,
                          model_config_id, agent_id=None, agent_config=None):
        assert model_config_id == mid
        return job

    ctx = RunContext(
        tenant_id=str(uuid4()),
        user_id=str(uuid4()),
        agent_id=str(uuid4()),
        generative_image_async=True,
        agent_config={},
        submit_generative_image=fake_submit,
    )
    node = {"prompt": "画一只猫", "model_config_id": str(mid)}
    out = _run(image_node.image_generate(node, {}, ctx))
    assert out == {
        "kind": "image",
        "status": "pending",
        "generative_job_id": str(job),
        "message": "生图任务已提交，请通过 generative_job_id 查询进度",
    }


def test_video_generate_async_submits_via_callback(monkeypatch):
    monkeypatch.setattr(video_node, "AsyncSessionLocal", _FakeSession)

    mid, att, job = uuid4(), uuid4(), uuid4()

    async def fake_submit(db, tenant_ctx, *, prompt, duration, resolution,
                          image_attachment_id, last_frame_attachment_id,
                          model_config_id, agent_id=None, agent_config=None):
        assert duration == 5
        assert model_config_id == mid
        return job

    ctx = RunContext(
        tenant_id=str(uuid4()),
        user_id=str(uuid4()),
        agent_id=str(uuid4()),
        generative_video_async=True,
        submit_generative_video=fake_submit,
    )
    node = {"prompt": "一段小短片", "model_config_id": str(mid)}
    out = _run(video_node.video_generate(node, {}, ctx))
    assert out == {
        "kind": "video",
        "status": "pending",
        "generative_job_id": str(job),
        "message": "生视频任务已提交，请通过 generative_job_id 查询进度",
    }


def test_image_generate_async_without_submitter_falls_back_to_sync():
    """async 打开但未注入 submit（Celery 未启用）→ 落同步分支；无 resolver 时报未装配。"""
    ctx = RunContext(
        tenant_id=str(uuid4()),
        user_id=str(uuid4()),
        generative_image_async=True,
        agent_config={},
    )
    node = {"prompt": "画一只猫", "model_config_id": str(uuid4())}
    with pytest.raises(BadRequestError, match="未装配"):
        _run(image_node.image_generate(node, {}, ctx))
```

- [ ] **Step 2: 运行确认失败**

Run（backend/ 下）：`uv run python -m pytest tests/flow/test_generative_nodes.py -q`
Expected：3 个新用例 FAIL——节点仍直接走 `GenerativeJobService` 同步判定路径（`image_async_enabled` 读取 settings 为真则尝试真实提交），且不读 `ctx.submit_generative_image`。

- [ ] **Step 3: 改造 `image_generate.py`**

- 删除顶部 import（现 L19-20）：
  ```python
  from app.tenant.generative.schemas.job import ImageGenerativeJobCreate
  from app.tenant.generative.services.job import GenerativeJobService
  ```
- async 分支（现 L54-74）改写为：

```python
    submit = ctx.submit_generative_image
    if ctx.generative_image_async and submit is not None:
        async with AsyncSessionLocal() as db:
            tenant_ctx = tenant_context_from_run(ctx)
            job_id = await submit(
                db,
                tenant_ctx,
                prompt=prompt,
                size=str(size) if size else None,
                n=n,
                image_attachment_id=image_att,
                model_config_id=UUID(str(model_id)),
                agent_id=_optional_uuid(ctx.agent_id),
                agent_config=ctx.agent_config,
            )
            await db.commit()
        return {
            "kind": "image",
            "status": "pending",
            "generative_job_id": str(job_id),
            "message": "生图任务已提交，请通过 generative_job_id 查询进度",
        }
```

- 模块 docstring 同步更新：默认异步分支「提交 generative_jobs + Celery」→「经 ``RunContext.submit_generative_image``（L1 注入）提交」。

- [ ] **Step 4: 改造 `video_generate.py`**

- 删除顶部 import（现 L19-20）：
  ```python
  from app.tenant.generative.schemas.job import VideoGenerativeJobCreate
  from app.tenant.generative.services.job import GenerativeJobService
  ```
- async 分支（现 L55-78）改写为：

```python
    submit = ctx.submit_generative_video
    if ctx.generative_video_async and submit is not None:
        async with AsyncSessionLocal() as db:
            tenant_ctx = tenant_context_from_run(ctx)
            job_id = await submit(
                db,
                tenant_ctx,
                prompt=prompt,
                duration=duration,
                resolution=str(resolution) if resolution else None,
                image_attachment_id=first_att,
                last_frame_attachment_id=last_att,
                model_config_id=model_id,
                agent_id=_optional_uuid(ctx.agent_id),
                agent_config=ctx.agent_config,
            )
            await db.commit()
        return {
            "kind": "video",
            "status": "pending",
            "generative_job_id": str(job_id),
            "message": "生视频任务已提交，请通过 generative_job_id 查询进度",
        }
```

- 模块 docstring 同步更新。

- [ ] **Step 5: 验证 + Commit**

Run（backend/ 下）：
```bash
uv run python -m pytest tests/flow/test_generative_nodes.py -q
rg -n "from app\.tenant\.generative|import app\.tenant\.generative" app/flow_runtime/nodes/image_generate.py app/flow_runtime/nodes/video_generate.py || echo "flow 生图/生视频节点对 tenant.generative 引用清零"
uv run ruff check app/flow_runtime/nodes/image_generate.py app/flow_runtime/nodes/video_generate.py tests/flow/test_generative_nodes.py
uv run python -m pytest -q | tail -1
```
Expected：新 3 + 既有 4 = 7 passed；rg 无命中；ruff 全绿；全量 ≥ 447。

```bash
git add backend/app/flow_runtime/nodes/image_generate.py backend/app/flow_runtime/nodes/video_generate.py backend/tests/flow/test_generative_nodes.py
git commit -m "refactor(engine): 生图/生视频节点异步提交改经 RunContext 注入回调

async 分支按 submit_generative_* 存在性判定（等同既有 settings 门控），
提交参数在 L1 回调内构造 JobCreate，节点不再 import tenant.generative。"
```

---

### Task 4: L1 装配注入（chat_rag + flow debug-run）

**Files:**
- Modify: `backend/app/tenant/agents/services/agent/chat_rag.py`
- Modify: `backend/app/tenant/flows/services/flow.py`

**Interfaces:**
- Consumes: Task 1 `submit_generative_{image,video}_job`、`GenerativeJobService.image_async_enabled()/video_async_enabled()`。
- Produces: 两条生产装配路径的 `RunContext.submit_generative_*` 按 settings 注入回调或 None。

- [ ] **Step 1: 核对装配 import 面**

Run（backend/ 下）：
```bash
sed -n '1,45p' app/tenant/agents/services/agent/chat_rag.py
sed -n '1,45p' app/tenant/flows/services/flow.py
```
先读顶部 import 区：`resolve_image_gen_model`/`resolve_video_gen_model` 的现有 import 语句（自 `generative_model_resolve`）作为锚点；确认两文件是否已 import `app.tenant.generative.services.job`（若无则追加，若顶层已 import `GenerativeJobService` 或 `job_execution` 则复用）。

- [ ] **Step 2: 追加 import**

在既有 `generative_model_resolve` import 附近追加：

```python
from app.tenant.generative.services.job import GenerativeJobService
from app.tenant.generative.services.job_execution import (
    submit_generative_image_job,
    submit_generative_video_job,
)
```

（若文件已顶层 import `GenerativeJobService`/`job_execution` 符号则复用既有 import，勿重复。若顶层 import 造成循环导入证据（启动即报 ImportError），改为在装配函数内函数级 import。）

- [ ] **Step 3: 装配点注入**

- `chat_rag.py` `flow_run_context` 的 `RunContext(...)` 构造（现 L98-99 `resolve_generative_*`）之后追加：

```python
            submit_generative_image=submit_generative_image_job
            if GenerativeJobService.image_async_enabled()
            else None,
            submit_generative_video=submit_generative_video_job
            if GenerativeJobService.video_async_enabled()
            else None,
```

- `flows/service.py` flow debug-run 的 `RunContext(...)`（现 L265-266）同理追加。

- [ ] **Step 4: 验证 + Commit**

Run（backend/ 下）：
```bash
uv run ruff check app/tenant/agents/services/agent/chat_rag.py app/tenant/flows/services/flow.py
uv run python -m pytest tests/flow/test_generative_nodes.py tests/tenant/agents/test_agent_flow_chat.py -q 2>/dev/null || uv run python -m pytest tests/flow/test_generative_nodes.py tests/tenant/agents/test_agent_chat_ws.py -q
uv run python -m pytest -q | tail -1
```
（`tests/tenant/agents/` 下若存在 flow-chat 相关定向用例文件则以实际为准；不存在则跑 `test_generative_nodes.py` + 全量。）
Expected：ruff 全绿；全量 ≥ 447 passed。

```bash
git add backend/app/tenant/agents/services/agent/chat_rag.py backend/app/tenant/flows/services/flow.py
git commit -m "refactor(engine): chat/flow 装配点按 settings 注入生图生视频提交回调

image/video_async_enabled 为静态配置，装配期转 RunContext.submit_* 存在性。"
```

---

### Task 5: 回归审计与 `layering.md` 收敛记录

**Files:**
- Modify: `docs/architecture/layering.md`

- [ ] **Step 1: 全量回归 + 定向 rg 终审**

Run（backend/ 下）：
```bash
uv run ruff check app/flow_runtime app/integrations/langgraph/compiler app/tenant/generative/services/job_execution.py
rg -n "from app\.tenant\.generative" app/flow_runtime || echo "flow_runtime 对 tenant.generative 运行期引用清零"
rg -n "from app\.tenant\.generative\.(schemas\.job|services\.job)" app/integrations app/flow_runtime || echo "L3 对 generative job schema/service 引用清零"
uv run python -m pytest -q | tail -1
```
Expected：ruff 全绿；两条 rg 无命中；pytest ≥ 447 passed。

- [ ] **Step 2: 更新收敛记录**

`docs/architecture/layering.md`：
- 在 L105（B-2d 收敛记录）之后追加：

```markdown
> **收敛记录（2026-09-09，B-2e）**：画布生图/生视频节点异步 job 提交上移 L1——`submit_generative_{image,video}_job` 落 `tenant/generative/services/job_execution.py`（构造 JobCreate 委托 `GenerativeJobService`，函数级 import 防循环），`ImageGenerate`/`VideoGenerate` 节点经 `RunContext.submit_generative_image/video`（L1 装配点按 settings `generative_*_async` 注入回调或 None）提交，节点不再 import `tenant.generative.{schemas.job, services.job}`（见 plan [`2026-09-09-engine-di-flow-generative-job`](../superpowers/plans/2026-09-09-engine-di-flow-generative-job.md)）。`flow_runtime` 对 `tenant` 引用继续收窄至 media/compliance/tools/rag 节点与 subflow 仓库面。
```

- §8 修订记录表追加一行：

```markdown
| 2026-09-09 | B-2e：画布生图/生视频节点异步提交收敛——job 提交流程落 L1 `job_execution` submit 回调，`RunContext.submit_generative_*` 注入，节点对 `tenant.generative.{schemas.job,services.job}` 运行期引用清零 |
```

- [ ] **Step 3: Commit**

```bash
git add docs/architecture/layering.md
git commit -m "docs(architecture): 记录 B-2e 画布生图/生视频提交收敛"
```

---

## Self-Review

- **Spec coverage**：目标（`image_generate`/`video_generate` 对 `tenant.generative.{schemas.job, services.job}` 反依赖清零）由 Task 1（L1 submit 回调）、Task 2（RunContext 字段 + 透传）、Task 3（节点切回调 + TDD）、Task 4（两装配点注入）达成；Task 5 文档终审闭环。同步 resolver 分支与 B-2c 结果零改动。
- **语义等价**：异步分支门控从「`async and GenerativeJobService.image_async_enabled()`」平移为「`async and ctx.submit_* is not None`」——装配点用同一 settings 判注入，False 时 submit=None、节点落同步兜底，与旧行为一致（旧 async+disabled 亦走同步 resolver）。pending dict、提交参数（含 `source="flow_node"`、`trace_id=get_trace_id()`、`agent_config`）、`db.commit` 时点均保持。
- **循环依赖**：`job.py` 顶层已 import `job_execution`（`get_generative_job_for_tenant`），故 `job_execution` 内对 `GenerativeJobService` 一律函数级 import（Task 1 明确）。
- **Placeholder scan**：各 Task 均含完整代码/命令；Task 4 两处「以实际文件 import 面为准」为读取指令而非 TBD；装配代码块为两文件共用模板（镜像复制）。
