# G1-2 实施计划：生成面租户编排下沉 L1——`integrations/generative` 对 tenant 清零

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 消除 L3 `app/integrations/generative` 对 `app.tenant` 的全部运行期 import——把租户副作用编排（合规扫描 / 日配额 / 参考图 data URL / 生成物持久化 / 媒体资产登记）从 L3 下沉 L1 `tenant/generative/services/orchestration.py`；L3 `*/service.py` 只保留纯厂商派发（`generate_image_bytes` / `generate_video_bytes` / `generate_tts_bytes`）；画布生图/生视频同步分支改经 `RunContext.generate_image_sync` / `generate_video_sync`（L1 注入）执行。

**完成标准：**
- `rg "app\.tenant" app/integrations/generative` 零命中（含注释/docstring 文本）；守卫测试 `tests/test_l3_neutral_imports.py` 纳入 `integrations/generative`。
- L3 删除 `persist.py` / `compliance.py` / `reference.py`，删除 `generate_{image,video,speech}_for_model`；`integrations/generative/__init__.py` 只导出 `ImageGenerateResult` / `VideoGenerateResult`。
- L1 新增 `tenant/generative/services/{persist,orchestration}.py`；三个 `generate_*_for_model` 签名与行为逐字等价（`(db, ctx, model, *, ...)`）。
- `RunContext.generate_image_sync` / `generate_video_sync`（L1 注入；None 时同步分支报错）；镜像既有 `submit_generative_*` 的装配/透传路径。
- 全量测试 ≥ 511（基线）。

## 背景事实（已审计）

- L3 生成面 tenant 触点共 6 处：`persist.py`（`AttachmentRepository` + `kb.services.quota`）、`compliance.py`（`ComplianceService`，惰性）、`reference.py`（`AttachmentService`，惰性）、`image/service.py` 与 `video/service.py`（惰性 `register_media_asset`）、`tts/service.py`（仅经 `persist`）。
- `quota.py` / `policy.py` / `request_prefs.py` / `jobs/*` / `registry.py` / providers / `video/cover.py` / `image/prompt_guard.py` **均无** tenant import（只依赖 `core`/`infra`/`models`），本计划不动。
- 编排函数当前签名 `(db: AsyncSession, ctx: TenantContext, model: ModelConfig, *, ...) -> Result`；L1 调用方 3 处：`tenant/generative/services/job_execution.py`（L17 import）、`tenant/tools/builtins/generative.py`（L18 + L109 + L204 函数级 import）。
- 画布同步分支（`flow_runtime/nodes/{image,video}_generate.py`）当前 `from app.integrations.generative import generate_*_for_model`，在自开短会话内解析 model 后同步调用，随后 `await db.commit()`。
- `RunContext` 既有同族字段与透传：`resolve_generative_*`、`submit_generative_*`、`invoke_platform_tool`、`resolve_prompt_template`、`load_scan_words`、`load_subflow_graph`、`media_reader`；透传点：`compiler/run.py` initial state、`compiler/build.py` `_State` + `RunContext(...)` 重建、`subflow/resolve.py::build_child_context`。
- 双根装配点：`chat_rag.py::flow_run_context`、`flows/services/flow.py::FlowService.run`（debug-run）；两者均持 `self.ctx`，loaders 走函数级 import。
- 测试 patch 面（须迁移）：`tests/tenant/generative/test_generative_{image,video}.py`、`tests/media/test_volcengine_video.py::test_generate_video_for_model_doubao_route`、`tests/flow/test_generative_nodes.py`。
- 既有守卫：`tests/test_l3_neutral_imports.py::_CONVERGED`（按行子串 `"app.tenant"` 扫描）。
- **陷阱**：`integrations/generative/**` 内任何注释/docstring 都不得出现字面量 `app.tenant`（否则守卫测试误报）；提到 L1 路径时写 ``tenant.generative.services.orchestration``（省略 `app.` 前缀）。

**Architecture:**

- **L3 纯派发**：`image/service.py::generate_image_bytes`（由 `_generate_bytes` 改名公开）、`video/service.py::generate_video_bytes`（从 `generate_video_for_model` 抽出）、`tts/service.py::generate_tts_bytes`（从 `generate_speech_for_model` 抽出）。三者只做 `resolve_invoke_mode` → Provider 调用，无 tenant。
- **L1 编排**：`tenant/generative/services/persist.py`（原 L3 `persist.py` 逐字下沉）+ `tenant/generative/services/orchestration.py`（`check_generative_prompt` / `reference_image_data_url` / `_resolve_frame_data_urls` / 三个 `generate_*_for_model`），依赖 L3 派发 + L1 附件/KB 配额/合规/媒体资产。
- **画布回调**：`RunContext.generate_image_sync` / `generate_video_sync` 直接注入 L1 编排函数引用（签名含 `db, ctx, model`，与 `submit_generative_*` 同风格），节点不再 import L3 编排。

## Global Constraints

- 分层：L3 `integrations/generative` 改后对 `app.tenant` 清零；L1 `tenant/generative/services/orchestration.py` 可 import L3 派发（L1→L3 合法，见 `layering.md` §1.2）与同域 L1 服务；`persist.py`/`orchestration.py` 不得被 L3 反向引用。
- 行为等价：三个 `generate_*_for_model` 的入参默认值、合规/配额/参考图/持久化/登记顺序、返回结构（`ImageGenerateResult` / `VideoGenerateResult` / TTS dict）逐字保留；媒体资产登记的 `resource_type`/`source_ref_type`/`kind` 等口径不变。
- 画布同步分支语义：`resolve_generative_*`（模型解析）检查在前，`generate_*_sync`（编排）检查在后；节点仍在自开短会话内解析模型并 `await db.commit()`。
- 中文 docstring/注释；`integrations/generative/**` 内不出现字面量 `app.tenant`。
- 每任务定向 + 全量回归（基线 **511 passed**；`uv run` 改写 `backend/uv.lock` 须 `git checkout -- backend/uv.lock` 还原）。
- 提交：每任务独立 commit，简体中文 `<type>(<scope>): <简述>`（scope `engine`）。

---

### Task 1: L3 厂商派发纯化（抽出公开派发函数，旧编排暂留）

**Files:**
- Modify: `backend/app/integrations/generative/image/service.py`
- Modify: `backend/app/integrations/generative/video/service.py`
- Modify: `backend/app/integrations/generative/tts/service.py`
- Modify: `backend/tests/tenant/generative/test_generative_image.py`（`_generate_bytes` patch 目标改名）

**Interfaces:**
- Produces: `generate_image_bytes(model, *, prompt, size, n, reference_image_data_url=None, progress=None) -> list[bytes]`；`generate_video_bytes(model, *, prompt, duration=5, resolution=None, first_frame_data_url=None, last_frame_data_url=None, progress=None) -> bytes`；`generate_tts_bytes(model, *, text, voice="longxiaochun", speech_rate=1.0) -> bytes`（Task 2 消费）。

- [ ] **Step 1: `image/service.py` 改名公开**

`_generate_bytes` 定义与 `generate_image_for_model` 内调用同步改名：

```python
async def generate_image_bytes(
    model: ModelConfig,
    *,
    prompt: str,
    size: str,
    n: int,
    reference_image_data_url: str | None = None,
    progress: object | None = None,
) -> list[bytes]:
    """按 invoke_mode 分发到具体 Provider，返回原始图片字节列表。

    按 Provider 函数签名过滤 kwargs，避免各厂商参数名不一致导致 TypeError。
    仅厂商派发，不含租户副作用（合规/配额/持久化）。
    """
    import inspect

    mode = resolve_invoke_mode(model, capability=ModelCapabilityType.IMAGE_GEN.value)
    provider_key = IMAGE_PROVIDER_ALIASES.get(mode, mode)
    provider = IMAGE_PROVIDERS.get(provider_key)
    if not provider:
        raise BadRequestError(f"不支持的生图 invoke_mode: {mode}")

    candidates = {
        "prompt": prompt,
        "size": size,
        "n": n,
        "reference_image_data_url": reference_image_data_url,
        # 兼容旧 Provider 参数名
        "reference_image_url": reference_image_data_url,
        "progress": progress,
    }
    try:
        accepted = set(inspect.signature(provider).parameters)
    except (TypeError, ValueError):
        accepted = set(candidates)
    kwargs = {k: v for k, v in candidates.items() if k in accepted}
    # 同一参考图只传一个参数，避免重复
    if "reference_image_data_url" in kwargs and "reference_image_url" in kwargs:
        del kwargs["reference_image_url"]

    return await provider(model, **kwargs)
```

`generate_image_for_model` 内 `blobs = await _generate_bytes(...)` 改为 `blobs = await generate_image_bytes(...)`（其余不动）。

- [ ] **Step 2: `video/service.py` 抽出派发**

把现 `generate_video_for_model` 里 `mode = resolve_invoke_mode(...)` 至 `raise BadRequestError(f"不支持的生视频 invoke_mode: {mode}")` 的分支块抽为模块级函数（置于文件末尾），旧编排改调用它：

```python
async def generate_video_bytes(
    model: ModelConfig,
    *,
    prompt: str,
    duration: int = 5,
    resolution: str | None = None,
    first_frame_data_url: str | None = None,
    last_frame_data_url: str | None = None,
    progress: object | None = None,
) -> bytes:
    """按 invoke_mode 分发到具体厂商，返回 mp4 字节（节点内同步轮询至完成）。

    仅厂商派发，不含租户副作用（合规/配额/持久化）。
    """
    mode = resolve_invoke_mode(model, capability=ModelCapabilityType.VIDEO_GEN.value)
    if mode == INVOKE_DASHSCOPE_T2V:
        return await generate_dashscope_video(
            model,
            prompt=prompt,
            duration=duration,
            resolution=resolution,
            first_frame_data_url=first_frame_data_url,
            last_frame_data_url=last_frame_data_url,
            progress=progress,
        )
    if mode == INVOKE_VOLCENGINE_VIDEO:
        return await generate_volcengine_video(
            model,
            prompt=prompt,
            duration=duration,
            resolution=resolution,
            first_frame_data_url=first_frame_data_url,
            last_frame_data_url=last_frame_data_url,
            progress=progress,
        )
    raise BadRequestError(f"不支持的生视频 invoke_mode: {mode}")
```

旧 `generate_video_for_model` 中：

```python
    video_bytes = await generate_video_bytes(
        model,
        prompt=prompt,
        duration=duration,
        resolution=resolution,
        first_frame_data_url=first_frame,
        last_frame_data_url=last_frame,
        progress=progress,
    )
```

（新增函数放在 `generate_video_for_model` 之后即可，模块内相互引用。）

- [ ] **Step 3: `tts/service.py` 抽出派发**

```python
async def generate_tts_bytes(
    model: ModelConfig,
    *,
    text: str,
    voice: str = "longxiaochun",
    speech_rate: float = 1.0,
) -> bytes:
    """按 invoke_mode 分发到 TTS Provider，返回音频字节。仅厂商派发，无租户副作用。"""
    mode = resolve_invoke_mode(model, capability=ModelCapabilityType.TTS.value) or INVOKE_DASHSCOPE_TTS

    if mode == INVOKE_DASHSCOPE_TTS:
        return await generate_dashscope_tts(
            model,
            text=text,
            voice=voice,
            speech_rate=speech_rate,
        )
    raise BadRequestError(f"不支持的 TTS invoke_mode: {mode}")
```

旧 `generate_speech_for_model` 中 mode 分支块整体替换为：

```python
    audio_bytes = await generate_tts_bytes(
        model,
        text=text,
        voice=voice,
        speech_rate=speech_rate,
    )
```

- [ ] **Step 4: 测试 patch 目标改名**

`tests/tenant/generative/test_generative_image.py` 两处：

```
"app.integrations.generative.image.service._generate_bytes"
```
→
```
"app.integrations.generative.image.service.generate_image_bytes"
```

- [ ] **Step 5: 验证 + 提交**

Run（backend/ 下）：
```bash
uv run ruff check app/integrations/generative tests/tenant/generative tests/media
uv run python -m pytest tests/tenant/generative tests/media -q
uv run python -m pytest -q | tail -1
```
Expected：ruff 绿；定向全过；全量 ≥ 511 passed。

```bash
git add backend/app/integrations/generative/image/service.py backend/app/integrations/generative/video/service.py backend/app/integrations/generative/tts/service.py backend/tests/tenant/generative/test_generative_image.py
git commit -m "refactor(engine): 生图/生视频/TTS 抽出纯厂商派发函数

为生成面编排下沉 L1 做准备：L3 只在派发函数里做 invoke_mode 分发，
旧编排入口暂留并改为调用新函数，行为不变。"
```

---

### Task 2: L1 编排下沉（新增 `persist.py` + `orchestration.py`）+ L1 调用方切换 + 生成测试迁移

**Files:**
- Create: `backend/app/tenant/generative/services/persist.py`
- Create: `backend/app/tenant/generative/services/orchestration.py`
- Modify: `backend/app/tenant/generative/services/job_execution.py`（L17 import）
- Modify: `backend/app/tenant/tools/builtins/generative.py`（L18 + L109 + L204 import）
- Modify: `backend/tests/tenant/generative/test_generative_image.py`
- Modify: `backend/tests/tenant/generative/test_generative_video.py`
- Modify: `backend/tests/media/test_volcengine_video.py`

**Interfaces:**
- Consumes: Task 1 `generate_image_bytes` / `generate_video_bytes` / `generate_tts_bytes`。
- Produces: `persist_generated_bytes`；`check_generative_prompt`；`reference_image_data_url`；`generate_image_for_model` / `generate_video_for_model` / `generate_speech_for_model`（Task 3 装配消费；TTS 已由 `tenant/tools/builtins/generative.py` 于本任务消费）。

- [ ] **Step 1: L1 `persist.py`（逐字下沉）**

```python
"""生成物写入对象存储与 sys_attachments（L1）。"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.tenant import TenantContext
from app.infra.storage import build_attachment_object_key
from app.infra.storage.resolve import resolve_object_storage_async
from app.integrations.generative.constants import PURPOSE_CHAT_GENERATED
from app.tenant.attachments.repositories.attachment import AttachmentRepository
from app.tenant.kb.services.quota import apply_storage_delta, assert_can_upload_bytes

settings = get_settings()


async def persist_generated_bytes(
    db: AsyncSession,
    ctx: TenantContext,
    *,
    data: bytes,
    filename: str,
    mime_type: str,
    purpose: str = PURPOSE_CHAT_GENERATED,
    resource_type: str | None = None,
    resource_id: UUID | None = None,
) -> UUID:
    """上传字节并创建附件记录，返回 attachment_id。"""
    await assert_can_upload_bytes(db, ctx.tenant_id, len(data))
    repo = AttachmentRepository(db)
    storage = await resolve_object_storage_async(ctx.tenant_id, db)
    att = await repo.create(
        tenant_id=ctx.tenant_id,
        uploaded_by=ctx.user_id,
        filename=filename,
        mime_type=mime_type,
        file_size=len(data),
        object_bucket=storage.default_bucket,
        object_key="pending",
        purpose=purpose,
        resource_type=resource_type,
        resource_id=resource_id,
    )
    object_key = build_attachment_object_key(str(ctx.tenant_id), str(att.id), filename)
    att.object_key = object_key
    storage.storage.upload_bytes(data, object_key, mime_type)
    await apply_storage_delta(db, ctx.tenant_id, len(data))
    await db.flush()
    await db.refresh(att)
    return att.id
```

- [ ] **Step 2: L1 `orchestration.py`**

新建 `backend/app/tenant/generative/services/orchestration.py`：

```python
"""生成类租户编排（L1）：合规扫描 → 配额 → 参考图 → 厂商派发 → 持久化 → 媒体资产登记。

L3 ``integrations/generative`` 只保留纯厂商派发（``generate_{image,video,tts}_bytes``）；
租户副作用全部在本模块：``ComplianceService`` / 日配额 / ``AttachmentService`` /
附件仓储 / 媒体资产登记。画布同步分支经 ``RunContext.generate_{image,video}_sync``
（即本模块 ``generate_{image,video}_for_model``）注入执行。
"""

from __future__ import annotations

import base64
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import BadRequestError
from app.core.tenant import TenantContext
from app.integrations.generative.constants import (
    DEFAULT_IMAGE_SIZE,
    EXTRA_IMAGE_SIZE,
    MAX_IMAGES_PER_REQUEST,
    PURPOSE_CHAT_GENERATED,
)
from app.integrations.generative.image.prompt_guard import sanitize_image_prompt
from app.integrations.generative.image.service import generate_image_bytes
from app.integrations.generative.quota import assert_generative_quota
from app.integrations.generative.tts.service import generate_tts_bytes
from app.integrations.generative.types import ImageGenerateResult, VideoGenerateResult
from app.integrations.generative.video.cover import extract_video_cover_jpeg
from app.integrations.generative.video.service import generate_video_bytes
from app.models.compliance.constants import SCAN_MODULE_GENERATIVE
from app.models.model import ModelConfig
from app.tenant.attachments.services.attachment import AttachmentService
from app.tenant.compliance.services.compliance import ComplianceService
from app.tenant.generative.services.persist import persist_generated_bytes
from app.tenant.media_assets.services.media_asset import register_media_asset


async def check_generative_prompt(
    db: AsyncSession,
    ctx: TenantContext,
    prompt: str,
) -> str:
    """扫描生成 prompt；拦截时抛业务异常，返回脱敏后文本（通常与输入相同）。"""
    compliance = ComplianceService(db, ctx)
    return await compliance.check_input((prompt or "").strip(), module=SCAN_MODULE_GENERATIVE)


async def reference_image_data_url(
    db: AsyncSession,
    ctx: TenantContext,
    attachment_id: UUID,
) -> str:
    """读取租户图片附件并编码为 data URL，供万相/豆包图生图、图生视频使用。"""
    data, mime = await AttachmentService(db, ctx).read_image_bytes(attachment_id)
    encoded = base64.standard_b64encode(data).decode("ascii")
    return f"data:{mime};base64,{encoded}"


async def _resolve_frame_data_urls(
    db: AsyncSession,
    ctx: TenantContext,
    *,
    first_attachment_id: UUID | None,
    last_attachment_id: UUID | None,
) -> tuple[str | None, str | None]:
    if last_attachment_id and not first_attachment_id:
        raise BadRequestError("首尾帧生视频需同时提供首帧与尾帧 attachment")

    first_url: str | None = None
    last_url: str | None = None
    if first_attachment_id:
        first_url = await reference_image_data_url(db, ctx, first_attachment_id)
    if last_attachment_id:
        last_url = await reference_image_data_url(db, ctx, last_attachment_id)
    return first_url, last_url


async def generate_image_for_model(
    db: AsyncSession,
    ctx: TenantContext,
    model: ModelConfig,
    *,
    prompt: str,
    size: str | None = None,
    n: int = 1,
    reference_attachment_id: UUID | None = None,
    purpose: str = PURPOSE_CHAT_GENERATED,
    agent_id: UUID | None = None,
    generative_job_id: UUID | None = None,
    trace_id: str | None = None,
    allow_collage: bool = False,
) -> ImageGenerateResult:
    """调用厂商生图并持久化为附件；可选参考图 attachment 实现图生图。"""
    prompt = (prompt or "").strip()
    if not prompt:
        raise BadRequestError("生图 prompt 不能为空")

    prompt = await check_generative_prompt(db, ctx, prompt)
    prompt = sanitize_image_prompt(prompt, allow_collage=allow_collage)

    ref_url: str | None = None
    if reference_attachment_id:
        ref_url = await reference_image_data_url(db, ctx, reference_attachment_id)

    extra = model.extra or {}
    resolved_size = size or str(extra.get(EXTRA_IMAGE_SIZE) or DEFAULT_IMAGE_SIZE)
    count = min(max(int(n), 1), MAX_IMAGES_PER_REQUEST)
    await assert_generative_quota(db, ctx.tenant_id, units=count)

    job_progress = None
    if generative_job_id:
        from app.integrations.generative.jobs.progress import GenerativeJobProgress

        job_progress = GenerativeJobProgress(generative_job_id)
        await job_progress.update(10, "调用生图 API")

    blobs = await generate_image_bytes(
        model,
        prompt=prompt,
        size=resolved_size,
        n=count,
        reference_image_data_url=ref_url,
        progress=job_progress,
    )
    if job_progress:
        await job_progress.update(80, "保存生成物")

    attachment_ids: list[UUID] = []
    media_asset_ids: list[UUID] = []
    mime = "image/png"
    import logging

    _log = logging.getLogger(__name__)
    _log.info("生图 → blobs=%d, n=%d", len(blobs), count)
    for i, data in enumerate(blobs):
        ext = "png"
        if data[:3] == b"\xff\xd8\xff":
            mime = "image/jpeg"
            ext = "jpg"
        att_id = await persist_generated_bytes(
            db,
            ctx,
            data=data,
            filename=f"generated-{i + 1}.{ext}",
            mime_type=mime,
            purpose=purpose,
            resource_type="agent" if agent_id else None,
            resource_id=agent_id,
        )
        row = await register_media_asset(
            db,
            ctx,
            attachment_id=att_id,
            purpose=purpose,
            prompt=prompt,
            model_config_id=model.id,
            kind="image",
            source_ref_type="agent" if agent_id else None,
            source_ref_id=agent_id,
        )
        attachment_ids.append(att_id)
        media_asset_ids.append(row.id)

    return ImageGenerateResult(attachment_ids=attachment_ids, mime_type=mime, media_asset_ids=media_asset_ids)


async def generate_video_for_model(
    db: AsyncSession,
    ctx: TenantContext,
    model: ModelConfig,
    *,
    prompt: str,
    duration: int = 5,
    resolution: str | None = None,
    image_attachment_id: UUID | None = None,
    last_frame_attachment_id: UUID | None = None,
    purpose: str = PURPOSE_CHAT_GENERATED,
    agent_id: UUID | None = None,
    generative_job_id: UUID | None = None,
    trace_id: str | None = None,
) -> VideoGenerateResult:
    """调用厂商生视频并持久化为 mp4 附件（可能阻塞数分钟）。"""
    prompt = (prompt or "").strip()
    if not prompt:
        raise BadRequestError("生视频 prompt 不能为空")

    prompt = await check_generative_prompt(db, ctx, prompt)

    await assert_generative_quota(db, ctx.tenant_id, units=1)

    first_frame, last_frame = await _resolve_frame_data_urls(
        db,
        ctx,
        first_attachment_id=image_attachment_id,
        last_attachment_id=last_frame_attachment_id,
    )

    progress = None
    if generative_job_id:
        from app.integrations.generative.jobs.progress import GenerativeJobProgress

        progress = GenerativeJobProgress(generative_job_id)
        await progress.update(8, "已提交厂商任务")

    video_bytes = await generate_video_bytes(
        model,
        prompt=prompt,
        duration=duration,
        resolution=resolution,
        first_frame_data_url=first_frame,
        last_frame_data_url=last_frame,
        progress=progress,
    )

    if progress:
        await progress.update(96, "保存生成物…")

    att_id = await persist_generated_bytes(
        db,
        ctx,
        data=video_bytes,
        filename="generated.mp4",
        mime_type="video/mp4",
        purpose=purpose,
        resource_type="agent" if agent_id else None,
        resource_id=agent_id,
    )
    cover_att_id: UUID | None = None
    cover_bytes = extract_video_cover_jpeg(video_bytes)
    if cover_bytes:
        cover_att_id = await persist_generated_bytes(
            db,
            ctx,
            data=cover_bytes,
            filename="generated-cover.jpg",
            mime_type="image/jpeg",
            purpose=purpose,
            resource_type="agent" if agent_id else None,
            resource_id=agent_id,
        )

    row = await register_media_asset(
        db,
        ctx,
        attachment_id=att_id,
        purpose=purpose,
        prompt=prompt,
        model_config_id=model.id,
        kind="video",
        source_ref_type="agent" if agent_id else None,
        source_ref_id=agent_id,
        cover_attachment_id=cover_att_id,
    )
    return VideoGenerateResult(
        attachment_id=att_id,
        mime_type="video/mp4",
        duration_sec=duration,
        media_asset_id=row.id,
    )


async def generate_speech_for_model(
    db: AsyncSession,
    ctx: TenantContext,
    model: ModelConfig,
    *,
    text: str,
    voice: str = "longxiaochun",
    speech_rate: float = 1.0,
    purpose: str = PURPOSE_CHAT_GENERATED,
    agent_id: UUID | None = None,
    trace_id: str | None = None,
) -> dict:
    """调用 TTS 模型生成语音，持久化为附件并返回结果。"""
    audio_bytes = await generate_tts_bytes(
        model,
        text=text,
        voice=voice,
        speech_rate=speech_rate,
    )

    attachment_id = await persist_generated_bytes(
        db,
        ctx,
        data=audio_bytes,
        filename=f"speech-{UUID(int=hash(text) & ((1 << 128) - 1))}.wav",
        mime_type="audio/wav",
        purpose=purpose,
        resource_type="agent" if agent_id else None,
        resource_id=agent_id,
    )

    return {
        "attachment_id": str(attachment_id),
        "mime_type": "audio/wav",
        "text_length": len(text),
    }
```

- [ ] **Step 3: L1 调用方切换 import**

- `tenant/generative/services/job_execution.py`：`from app.integrations.generative import generate_image_for_model, generate_video_for_model` → `from app.tenant.generative.services.orchestration import generate_image_for_model, generate_video_for_model`（常量那行不动）。
- `tenant/tools/builtins/generative.py`：三处 `from app.integrations.generative import generate_*_for_model` → `from app.tenant.generative.services.orchestration import ...`（顶层 1 处 + 函数级 2 处）。

- [ ] **Step 4: 迁移生成测试 patch 面**

`tests/tenant/generative/test_generative_image.py`：import 改为 `from app.tenant.generative.services.orchestration import generate_image_for_model`（2 处）；patch 目标改为
- `app.integrations.generative.quota.assert_generative_quota` → `app.tenant.generative.services.orchestration.assert_generative_quota`
- `app.integrations.generative.image.service.reference_image_data_url` → `app.tenant.generative.services.orchestration.reference_image_data_url`
- `app.integrations.generative.image.service.persist_generated_bytes` → `app.tenant.generative.services.orchestration.persist_generated_bytes`
- `app.tenant.media_assets.services.media_asset.register_media_asset` → `app.tenant.generative.services.orchestration.register_media_asset`
- `app.integrations.generative.compliance.check_generative_prompt` → `app.tenant.generative.services.orchestration.check_generative_prompt`

`tests/tenant/generative/test_generative_video.py`：import 改为 orchestration（1 处）；patch 目标：
- `...quota.assert_generative_quota` → `app.tenant.generative.services.orchestration.assert_generative_quota`
- `...video.service.generate_dashscope_video` **保持不变**（L3 派发内部仍按模块全局调用）
- `...video.service.persist_generated_bytes` → `app.tenant.generative.services.orchestration.persist_generated_bytes`
- `...compliance.check_generative_prompt` → `app.tenant.generative.services.orchestration.check_generative_prompt`
- `app.tenant.media_assets.services.media_asset.register_media_asset` → `app.tenant.generative.services.orchestration.register_media_asset`

`tests/media/test_volcengine_video.py::test_generate_video_for_model_doubao_route`：import 改为 orchestration（1 处）；patch 目标同上（`video.service.generate_volcengine_video` **保持不变**；quota/compliance/persist/register_media_asset 改 orchestration）。

- [ ] **Step 5: 验证 + 提交**

Run（backend/ 下）：
```bash
uv run ruff check app/tenant/generative app/tenant/tools/builtins tests/tenant/generative tests/media
uv run python -m pytest tests/tenant/generative tests/media -q
uv run python -m pytest -q | tail -1
```
Expected：ruff 绿；定向全过；全量 ≥ 511 passed。

```bash
git add backend/app/tenant/generative/services/persist.py backend/app/tenant/generative/services/orchestration.py backend/app/tenant/generative/services/job_execution.py backend/app/tenant/tools/builtins/generative.py backend/tests/tenant/generative tests/media/test_volcengine_video.py
git commit -m "refactor(engine): 生成面租户编排下沉 L1 orchestration

persist/compliance/reference 与三个 generate_*_for_model 迁入 L1，L3 只留
厂商派发；job_execution 与内置工具改用 L1 编排，生成测试 patch 面随迁。"
```

---

### Task 3: 画布同步编排回调闭环（节点 + 装配 + 透传）

**Files:**
- Modify: `backend/app/flow_runtime/types.py`
- Modify: `backend/app/flow_runtime/nodes/image_generate.py`
- Modify: `backend/app/flow_runtime/nodes/video_generate.py`
- Modify: `backend/app/tenant/agents/services/agent/chat_rag.py`
- Modify: `backend/app/tenant/flows/services/flow.py`
- Modify: `backend/app/integrations/langgraph/compiler/run.py`
- Modify: `backend/app/integrations/langgraph/compiler/build.py`
- Modify: `backend/app/flow_runtime/subflow/resolve.py`
- Modify: `backend/tests/flow/test_generative_nodes.py`
- Modify: `backend/tests/tenant/agents/test_agent_chat_rag_flow_context.py`
- Modify: `backend/tests/flow/test_subflow.py`

**Interfaces:**
- Consumes: Task 2 `orchestration.generate_{image,video}_for_model`。
- Produces: `RunContext.generate_{image,video}_sync`（本任务 Step 5 装配）；`flow_runtime/nodes/{image,video}_generate.py` 对 L3 生成编排 import 清零。

- [ ] **Step 1: `RunContext` 字段**


`flow_runtime/types.py`：`media_reader` 之后追加：

```python
    # 画布同步生图/生视频编排回调（L1 注入，即 orchestration.generate_{image,video}_for_model；
    # 签名 (db, ctx, model, **kwargs) -> Result；None 表示未装配，
    # ImageGenerate/VideoGenerate 同步分支报错）。新建画布 RunContext 根装配点
    # 须随 resolve_generative_* 一并注入（见 chat_rag/flow debug-run）。
    generate_image_sync: Callable[..., Awaitable[Any]] | None = None
    generate_video_sync: Callable[..., Awaitable[Any]] | None = None
```

- [ ] **Step 2: `image_generate.py` 同步分支改造**

删除 `from app.integrations.generative import generate_image_for_model`（保留 `PURPOSE_FLOW_GENERATED` 常量 import）；同步分支改为：

```python
    resolver = ctx.resolve_generative_image
    if resolver is None:
        raise BadRequestError("生图模型解析器未装配（resolve_generative_image），无法同步生图")

    generate = ctx.generate_image_sync
    if generate is None:
        raise BadRequestError("生图编排未装配（generate_image_sync），无法同步生图")

    async with AsyncSessionLocal() as db:
        tenant_ctx = tenant_context_from_run(ctx)
        model = await resolver(
            db,
            tenant_ctx,
            model_config_id=UUID(str(model_id)),
            agent_config=ctx.agent_config,
        )
        result = await generate(
            db,
            tenant_ctx,
            model,
            prompt=prompt,
            size=size,
            n=n,
            reference_attachment_id=image_att,
            purpose=PURPOSE_FLOW_GENERATED,
            agent_id=_optional_uuid(ctx.agent_id),
            trace_id=get_trace_id(),
        )
        await db.commit()
        primary = result.attachment_ids[0]
        return {
            "kind": "image",
            "attachment_id": str(primary),
            "attachment_ids": [str(i) for i in result.attachment_ids],
            "mime_type": result.mime_type,
        }
```

（模块 docstring 末句补「同步分支经 ``RunContext.generate_image_sync``（L1 注入）。」）

- [ ] **Step 3: `video_generate.py` 同步分支改造**

删除 `from app.integrations.generative import generate_video_for_model`；同步分支改为：

```python
    resolver = ctx.resolve_generative_video
    if resolver is None:
        raise BadRequestError("生视频模型解析器未装配（resolve_generative_video），无法同步生视频")

    generate = ctx.generate_video_sync
    if generate is None:
        raise BadRequestError("生视频编排未装配（generate_video_sync），无法同步生视频")

    async with AsyncSessionLocal() as db:
        tenant_ctx = tenant_context_from_run(ctx)
        model = await resolver(
            db,
            tenant_ctx,
            model_config_id=model_id,
            agent_config=ctx.agent_config,
        )
        result = await generate(
            db,
            tenant_ctx,
            model,
            prompt=prompt,
            duration=duration,
            resolution=resolution,
            image_attachment_id=first_att,
            last_frame_attachment_id=last_att,
            purpose=PURPOSE_FLOW_GENERATED,
            agent_id=_optional_uuid(ctx.agent_id),
            trace_id=get_trace_id(),
        )
        await db.commit()
        return {
            "kind": "video",
            "attachment_id": str(result.attachment_id),
            "mime_type": result.mime_type,
            "duration_sec": result.duration_sec,
        }
```

- [ ] **Step 4: 节点测试改为回调注入**

`tests/flow/test_generative_nodes.py`：

- 删除 `monkeypatch.setattr(image_node, "generate_image_for_model", fake_generate)` / 对应 video 行；`fake_generate` 签名改为 `async def fake_generate(db, ctx, model, **kwargs)`。
- `test_image_generate_sync_with_injected_resolver`：`RunContext(...)` 增 `generate_image_sync=fake_generate,`。
- `test_video_generate_sync_with_injected_resolver`：增 `generate_video_sync=fake_generate,`。
- 新增两个用例（放在 sync-with-resolver 之后）：

```python
def test_image_generate_sync_without_orchestrator_raises(monkeypatch):
    """resolver 已装配但未注入 generate_image_sync ⇒ 报未装配。"""
    monkeypatch.setattr(image_node, "AsyncSessionLocal", _FakeSession)
    mid = uuid4()

    async def fake_resolve(db, ctx, *, model_config_id, agent_model=None, agent_config=None):
        return type("Model", (), {"id": mid})()

    ctx = RunContext(
        tenant_id=str(uuid4()),
        user_id=str(uuid4()),
        generative_image_async=False,
        agent_config={},
        resolve_generative_image=fake_resolve,
    )
    node = {"prompt": "画一只猫", "model_config_id": str(mid)}
    with pytest.raises(BadRequestError, match="编排未装配"):
        _run(image_node.image_generate(node, {}, ctx))


def test_video_generate_sync_without_orchestrator_raises(monkeypatch):
    monkeypatch.setattr(video_node, "AsyncSessionLocal", _FakeSession)
    mid = uuid4()

    async def fake_resolve(db, ctx, *, model_config_id, agent_config=None):
        return type("Model", (), {"id": mid})()

    ctx = RunContext(
        tenant_id=str(uuid4()),
        user_id=str(uuid4()),
        generative_video_async=False,
        resolve_generative_video=fake_resolve,
    )
    node = {"prompt": "一段小短片", "model_config_id": str(mid)}
    with pytest.raises(BadRequestError, match="编排未装配"):
        _run(video_node.video_generate(node, {}, ctx))
```

- [ ] **Step 5: 双根装配点注入**

- `chat_rag.py::flow_run_context`：在既有函数级 import 组内加
  `from app.tenant.generative.services.orchestration import generate_image_for_model, generate_video_for_model`；
  `RunContext(...)` 实参在 `media_reader=...,` 之后加：

```python
            generate_image_sync=generate_image_for_model,
            generate_video_sync=generate_video_for_model,
```

- `flows/services/flow.py::FlowService.run`（debug-run）：同样加函数级 import 与两行实参（位置同上）。

- [ ] **Step 6: state + subflow 透传**

- `compiler/run.py`：initial state 加 `"generate_image_sync": ctx.generate_image_sync,`、`"generate_video_sync": ctx.generate_video_sync,`。
- `compiler/build.py`：`_State` 加 `generate_image_sync: Any` / `generate_video_sync: Any`（注释「L1 注入的同步生成编排回调（随 ctx 透传）」）；`run_node` 的 `RunContext(...)` 重建加 `generate_image_sync=state.get("generate_image_sync"),`、`generate_video_sync=state.get("generate_video_sync"),`。
- `subflow/resolve.py::build_child_context`：加

```python
        generate_image_sync=parent_ctx.generate_image_sync,  # 同步生图编排回调透传到子流程
        generate_video_sync=parent_ctx.generate_video_sync,  # 同步生视频编排回调透传到子流程
```

- [ ] **Step 7: 装配/透传断言**

- `tests/tenant/agents/test_agent_chat_rag_flow_context.py::test_flow_run_context_injects_resolvers_and_bindings_always` 追加：

```python
    # 同步生成编排回调恒定注入（画布 ImageGenerate/VideoGenerate 同步分支装配）
    assert ctx.generate_image_sync is not None
    assert callable(ctx.generate_image_sync)
    assert ctx.generate_video_sync is not None
    assert callable(ctx.generate_video_sync)
```

- `tests/flow/test_subflow.py`：parent `RunContext(...)` 增 `generate_image_sync=fake_sync_generator,`（`fake_sync_generator = object()` 即可，与 `media_reader` 同法），并加 `assert child.generate_image_sync is fake_sync_generator`。

- [ ] **Step 8: 验证 + 全量回归**

Run（backend/ 下）：
```bash
uv run ruff check app/flow_runtime app/tenant/generative app/tenant/tools/builtins app/integrations/generative app/integrations/langgraph/compiler
uv run python -m pytest tests/flow tests/tenant/generative tests/tenant/agents tests/media -q
uv run python -m pytest -q | tail -1
```
Expected：ruff 绿；定向全过；全量 ≥ 511 passed。

- [ ] **Step 9: Commit**

```bash
git add backend/app/flow_runtime/types.py backend/app/flow_runtime/nodes/image_generate.py backend/app/flow_runtime/nodes/video_generate.py backend/app/tenant/agents/services/agent/chat_rag.py backend/app/tenant/flows/services/flow.py backend/app/integrations/langgraph/compiler/run.py backend/app/integrations/langgraph/compiler/build.py backend/app/flow_runtime/subflow/resolve.py backend/tests/flow/test_generative_nodes.py backend/tests/tenant/agents/test_agent_chat_rag_flow_context.py backend/tests/flow/test_subflow.py
git commit -m "refactor(engine): 画布同步生成改走 RunContext 编排回调并装配透传

节点不再 import L3 生成编排；同步分支经 L1 注入的 generate_{image,video}_sync
执行，未装配时报错；双根装配点注入并随 langgraph/subflow 透传。"
```

---

### Task 4: 删除 L3 旧编排 + 守卫测试 + 文档闭环

**Files:**
- Delete: `backend/app/integrations/generative/persist.py`
- Delete: `backend/app/integrations/generative/compliance.py`
- Delete: `backend/app/integrations/generative/reference.py`
- Modify: `backend/app/integrations/generative/image/service.py`
- Modify: `backend/app/integrations/generative/video/service.py`
- Modify: `backend/app/integrations/generative/tts/service.py`
- Modify: `backend/app/integrations/generative/__init__.py`
- Modify: `backend/app/integrations/generative/image/__init__.py`
- Modify: `backend/app/integrations/generative/video/__init__.py`
- Modify: `backend/app/integrations/generative/tts/__init__.py`
- Modify: `backend/scripts/backfill_media_assets.py`
- Modify: `backend/tests/test_l3_neutral_imports.py`
- Modify: `docs/architecture/layering.md`

**Interfaces:**
- Produces: `integrations/generative` 对 `app.tenant` 零引用（本任务 Step 3 守卫断言）。

- [ ] **Step 1: 删除旧编排函数与 tenant import**

- `image/service.py`：删除 `generate_image_for_model` 整个函数；删除 `AsyncSession`、`TenantContext`、`UUID`、`reference_image_data_url`、`persist_generated_bytes`、`PURPOSE_CHAT_GENERATED`、`DEFAULT_IMAGE_SIZE`/`EXTRA_IMAGE_SIZE`/`MAX_IMAGES_PER_REQUEST`（若仅编排使用）等 import；`sanitize_image_prompt` 若仅编排使用亦删。保留下方新 docstring：

```python
"""
生图厂商派发（``model_type=image_gen``）。

只做 invoke_mode → Provider 分发与参数过滤；租户副作用（合规/配额/持久化/媒体资产
登记）见 L1 ``tenant.generative.services.orchestration``。
"""
```

- `video/service.py`：删除 `generate_video_for_model` 与 `_resolve_frame_data_urls`；删除 `AsyncSession`/`TenantContext`/`UUID`/`PURPOSE_CHAT_GENERATED`/`persist_generated_bytes`/`reference_image_data_url` import。docstring 改为：

```python
"""
生视频厂商派发（``model_type=video_gen``）。

万相 / 豆包：节点内同步轮询至完成（``dashscope_t2v`` / ``volcengine_video``）。
只做 invoke_mode 分发；租户副作用见 L1 ``tenant.generative.services.orchestration``。
"""
```

- `tts/service.py`：删除 `generate_speech_for_model`；删除 `AsyncSession`/`TenantContext`/`UUID`/`PURPOSE_CHAT_GENERATED`/`persist_generated_bytes` import。docstring 改为：

```python
"""
TTS 语音合成厂商派发（``model_type=tts``）。

当前 Provider：DashScope CosyVoice（``INVOKE_DASHSCOPE_TTS``）。
租户副作用见 L1 ``tenant.generative.services.orchestration``。
"""
```

> 校验：`ruff` 报 F401 时按报错继续删未用 import，直到干净。

- [ ] **Step 1b: `scripts/backfill_media_assets.py` 改指中立常量**

`backend/scripts/backfill_media_assets.py:12` 现依赖 L3 `persist.py` 的 PURPOSE re-export（Task 2 评审发现的遗留）。删除 L3 `persist.py` 后该 import 会断：

```python
# 原
from app.integrations.generative.persist import PURPOSE_CHAT_GENERATED, PURPOSE_FLOW_GENERATED
# 改
from app.integrations.generative.constants import PURPOSE_CHAT_GENERATED, PURPOSE_FLOW_GENERATED
```

- [ ] **Step 2: 收敛 `__init__` 导出**

`integrations/generative/__init__.py` 整体替换为：

```python
"""
文生图 / 生视频 / TTS 厂商集成（不走 LiteLLM chat）。

本层只做厂商派发：``image.service.generate_image_bytes`` /
``video.service.generate_video_bytes`` / ``tts.service.generate_tts_bytes``；
不含租户副作用（合规/配额/持久化/媒体资产登记），编排在 L1
``tenant.generative.services.orchestration``，画布节点经
``RunContext.generate_{image,video}_sync`` 注入。
模型解析（``resolve_*_gen_model``）见 L1 ``tenant.models.services.generative_model_resolve``。
"""

from app.integrations.generative.types import ImageGenerateResult, VideoGenerateResult

__all__ = [
    "ImageGenerateResult",
    "VideoGenerateResult",
]
```

`image/__init__.py`（单行 docstring）：

```python
"""生图（``model_type=image_gen``）Provider 与厂商派发（``image.service.generate_image_bytes``）。"""
```

`video/__init__.py`：

```python
"""生视频（``model_type=video_gen``）Provider 与厂商派发（``video.service.generate_video_bytes``）。"""
```

`tts/__init__.py`：

```python
"""TTS 语音合成 Provider 与厂商派发（``tts.service.generate_tts_bytes``）。"""
```

- [ ] **Step 3: 守卫测试纳入**

`tests/test_l3_neutral_imports.py` 的 `_CONVERGED` 增加一项：

```python
    ("integrations/generative", "integrations/generative"),
```

- [ ] **Step 4: 验证 + 提交**

Run（backend/ 下）：
```bash
rg -n "app\.tenant" app/integrations/generative || echo "generative 对 app.tenant 清零"
rg -n "from app\.integrations\.generative import|integrations\.generative\.(persist|compliance|reference)" app tests scripts --glob "*.py" || echo "无 L3 旧编排消费方"
uv run ruff check app/integrations/generative scripts/backfill_media_assets.py tests/test_l3_neutral_imports.py
uv run python -m pytest tests/test_l3_neutral_imports.py tests/tenant/generative tests/media tests/flow -q
uv run python -m pytest -q | tail -1
```
Expected：`rg` 零命中（注意先删净 docstring/注释中的字面量 `app.tenant`）；ruff 绿；定向全过；全量 ≥ 511 passed。

```bash
git add -A backend/app/integrations/generative backend/scripts/backfill_media_assets.py backend/tests/test_l3_neutral_imports.py
git commit -m "refactor(engine): 删除 L3 生成面租户编排，integrations/generative 清零

persist/compliance/reference 与三个 generate_*_for_model 从 L3 移除，
__init__ 只导出结果类型；backfill 脚本改指中立常量；守卫测试纳入
integrations/generative。"
```

- [ ] **Step 5: 文档闭环 + 独立 commit**


`docs/architecture/layering.md`：G2-4a 收敛记录之后追加：

```markdown
> **收敛记录（2026-09-10，G1-2）**：生成面租户编排下沉——`integrations/generative` 前零 tenant 引用：合规扫描 / 日配额 / 参考图 data URL / 生成物持久化 / 媒体资产登记从 L3 迁入 L1 `tenant/generative/services/orchestration.py`（`persist.py` 同步下沉），L3 `*/service.py` 只保留纯厂商派发 `generate_{image,video,tts}_bytes`；画布 `ImageGenerate`/`VideoGenerate` 同步分支改经 `RunContext.generate_{image,video}_sync`（L1 注入），与 `submit_generative_*` 同族。守卫测试纳入 `integrations/generative`。见 plan [`2026-09-10-engine-di-generative-orchestration`](../superpowers/plans/2026-09-10-engine-di-generative-orchestration.md)。
```

§8 修订表 G2-4a 行之后追加：

```markdown
| 2026-09-10 | G1-2：生成面租户编排下沉 L1——`integrations/generative` 只留纯厂商派发，`RunContext.generate_{image,video}_sync` 注入画布同步分支，L3 生成面对 tenant 清零 |
```

```bash
git add docs/architecture/layering.md
git commit -m "docs(architecture): 记录 G1-2 生成面编排下沉 L1"
```

---



---

## Self-Review

- **Spec coverage**：完成标准四项分别由 Task 1（L3 派发纯化）+ Task 2（L1 编排 + 调用方/测试迁移）+ Task 3（画布回调 + 装配 + 透传）+ Task 4（L3 删除 + 守卫纳入 + 文档）达成。
- **行为等价**：Task 2 Step 2 三个 `generate_*_for_model` 为原逻辑逐字搬运（仅 `_generate_bytes`→`generate_image_bytes`、mode 分支→`generate_*_bytes`、惰性 import→模块级）；返回值与登记字段（`purpose`/`resource_type`/`source_ref_type`/`kind`/`cover_attachment_id`）不变；`persist.py` 逐字下沉。
- **依赖方向**：L3 派发只依赖 providers/registry/constants/models/core/common；L1 orchestration 依赖 L3 派发（合法下行）+ L1 同域；`integrations/generative` 无 `app.tenant` 字面量（Task 4 守卫）。
- **中间态可跑（删除置末）**：Task 1 旧编排仍在（改调新函数）；Task 2 L1 新增 + 调用方切换 + 测试迁移（L3 旧编排仍在，画布节点暂用）；Task 3 画布节点切回调 + 装配透传（L3 旧编排仍存在但已无消费方，保证不出现 import 断裂）；Task 4 原子删除 L3 旧编排 + 守卫 + 文档。**删除必须在 Task 3 之后**，否则画布节点 import 会断。
- **Type consistency**：`generate_image_bytes`/`generate_video_bytes`/`generate_tts_bytes` 名称在 Task 1 定义、Task 2 消费；`generate_{image,video}_sync` 在 Task 3 定义并同任务装配；`check_generative_prompt`/`reference_image_data_url`/`persist_generated_bytes`/`register_media_asset` 在 Task 2 定义并被 Task 2 测试 patch。
- **Placeholder scan**：无 TBD；新文件与改动片段均给出完整代码；删除类步骤给出确定的删除范围与替代 docstring。
