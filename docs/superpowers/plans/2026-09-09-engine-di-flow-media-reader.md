# G2-4a 实施计划：flow 画布媒体读取收敛——MediaReader 契约 + RunContext 注入（G2 收官）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 消除 `flow_runtime/nodes/media_nodes.py`（L3）对 `tenant.attachments.services.attachment.AttachmentService` 的运行期 import——媒体读取改经 L3 中性契约 `MediaReader`（`app/models/media/reader.py`）+ L1 实现 `tenant/attachments/services/media_reader.py`，经 `RunContext.media_reader` 注入。完成后 `flow_runtime/nodes/` 对 `tenant.*` 直接 import 清零，**G2 画布节点面收官**。

**完成标准：**
- `flow_runtime/nodes/*.py` 对 `from app.tenant.*` 清零。
- 中立契约 `MediaReader`（`read_image_bytes` / `read_attachment_bytes`）+ `AttachmentBytes`；L1 `build_flow_media_reader(tenant_id, user_id)` 短会话实现。
- `RunContext.media_reader`（L1 注入；None 且节点执行时报错）。
- 行为等价：OCR 路径与返回结构（`output`/`attachment_id`/`mime_type`）不变；`_resolve_attachment_id` 解析顺序不变。
- **缺陷修复（显式）**：`AudioTranscribe` 原实现误用 `AttachmentService.read_image_bytes`（图片类型校验），对真实音频必然抛「附件不是支持的图片格式」。改走 `read_attachment_bytes` 后按 mime/filename 正常读取；返回结构（`output`/`attachment_id`/`filename`）不变。
- 全量测试 ≥ 497。

## 背景事实（已审计）

- `media_nodes.py`（110 行）反依赖 1 处：L24 `from app.tenant.attachments.services.attachment import AttachmentService`；另用 `AsyncSessionLocal`、`TenantContext`、`select`/`Attachment`（仅 `audio_transcribe` 取 `filename`）。
- `ocr_extract`：`AttachmentService(db, tctx).read_image_bytes(UUID(id))` → `(data, mime)`；`mime` 实际恒为 `"image/png"`（`read_image_bytes` 末尾固定返回）；`parse_image(data, f"ocr-{id}")`。
- `audio_transcribe`：先 `select(Attachment)` 取 `att.filename`，再调用 `read_image_bytes`（**图片校验 → 音频必失败**）；`parse_audio(data, filename)`。
- `_make_ctx`：`TenantContext(user_id=可选, tenant_id, username="flow_media", is_superuser=False, permissions=frozenset(["attachment:read"]))`；每节点调用自开短会话 `AsyncSessionLocal()`（短会话语义须保留）。
- `AttachmentService` 现有公开读取仅 `read_image_bytes(attachment_id) -> (bytes, str)`（含图片校验；对象存储异常时回退 1x1 透明 PNG）；私有 `_get_or_raise` 做租户校验（`NotFoundError("附件不存在")` + `assert_tenant_access`）。
- `RunContext` 现有注入先例：`kb_retrieval: Any = None`、`usage_sink: Any = None`（对象）+ 若干 `Callable | None` 回调；`build_child_context`/`compiler/run.py`/`compiler/build.py` 已透传同族字段。
- 双根装配点均持有 `self.ctx`（`chat_rag.py::flow_run_context` L93 起、`flows/services/flow.py::run` L260 起）。
- 既有测试：**无** media_nodes/OCR/AudioTranscribe 直接测试（`rg` 零命中），需新建。
- 守卫测试 `tests/test_l3_neutral_imports.py::_CONVERGED` 可扩入 `models/media`。
- 其余媒体反依赖（`integrations/chat/multimodal.py`、`generative/reference.py` 等）属 **G2-4b/G1**，本计划不动。

**Architecture:**

- **中立契约**（新建 `app/models/media/reader.py`）：
  ```python
  """媒体/附件读取中立契约（L3 与 L1 实现共用）。

  ``AttachmentBytes``：读取结果的 L3 最小视图；``MediaReader`` 由 L1
  ``tenant.attachments.services.media_reader`` 实现（租户鉴权 + 对象存储短会话）。
  """

  from __future__ import annotations

  from dataclasses import dataclass
  from typing import Protocol
  from uuid import UUID

  __all__ = ["AttachmentBytes", "MediaReader"]


  @dataclass(frozen=True)
  class AttachmentBytes:
      """附件字节读取结果：data / mime / filename（filename 供解析器推断格式）。"""

      data: bytes
      mime: str
      filename: str | None = None


  class MediaReader(Protocol):
      """画布媒体节点所需的最小附件读取面（L1 注入）。"""

      async def read_image_bytes(self, attachment_id: UUID) -> AttachmentBytes:
          """按租户鉴权读取图片字节（非图片/未就绪抛业务异常）。"""
          ...

      async def read_attachment_bytes(self, attachment_id: UUID) -> AttachmentBytes:
          """按租户鉴权读取任意附件字节（不存在/未就绪抛业务异常）。"""
          ...
  ```
- **L1 `AttachmentService` 新增方法**（`tenant/attachments/services/attachment.py`）：
  ```python
  async def read_attachment_bytes(self, attachment_id: UUID) -> tuple[bytes, str, str | None]:
      """按租户鉴权读取任意附件字节（不做图片类型校验）。

      返回 ``(data, mime_type, filename)``；不存在/已删抛 ``NotFoundError``，
      文件未就绪抛 ``BadRequestError``。读取失败不吞异常（与 ``read_image_bytes``
      的图片占位兜底不同，音频等需真实字节）。
      """
      att = await self._get_or_raise(attachment_id)
      if not att.object_key or att.object_key == "pending":
          raise BadRequestError("附件文件未就绪")
      storage = await resolve_object_storage_async(att.tenant_id, self.db)
      data = storage.storage.download_bytes(att.object_key, att.object_bucket)
      return data, att.mime_type or "application/octet-stream", att.filename
  ```
- **L1 reader**（新建 `tenant/attachments/services/media_reader.py`）：`FlowMediaReader` 持有 `tenant_id/user_id`（str|UUID → UUID），每次读取开 `AsyncSessionLocal()` 短会话 + 构造 `TenantContext(username="flow_media", permissions=frozenset(["attachment:read"]))` 委托 `AttachmentService`；`build_flow_media_reader(*, tenant_id, user_id=None) -> FlowMediaReader` 工厂。
- **RunContext 字段**（`flow_runtime/types.py`，随 `load_subflow_graph` 之后）：
  ```python
  # 画布媒体节点附件读取器（L1 注入，实现 models.media.reader.MediaReader；
  # None 表示未装配，OcrExtract/AudioTranscribe 节点报错）。新建画布 RunContext
  # 根装配点须随 resolve_generative_* 一并注入（见 chat_rag/flow debug-run）。
  media_reader: Any = None
  ```
- **节点改造**（`media_nodes.py`）：删 `AsyncSessionLocal`/`TenantContext`/`select`/`Attachment`/`AttachmentService` import 与 `_make_ctx`；`_require_media_reader(ctx)`（None → `BadRequestError("运行上下文未提供媒体读取器")`）；
  - `ocr_extract`：`att = await reader.read_image_bytes(UUID(attachment_id))` → `parse_image(att.data, f"ocr-{attachment_id}")` → 返回 `{"output": text, "attachment_id": str(attachment_id), "mime_type": att.mime}`。
  - `audio_transcribe`：`att = await reader.read_attachment_bytes(UUID(attachment_id))` → `filename = att.filename or f"audio-{attachment_id}"` → `parse_audio(att.data, filename)` → 返回 `{"output": text, "attachment_id": str(attachment_id), "filename": filename}`。
  - `_resolve_attachment_id` 逐字保留。

## Global Constraints

- 分层：改后 `flow_runtime/nodes/` 对 `tenant.*` 直接 import 清零（允许 `models.media.reader`/`rag.parse`/`infra`/`core`）；`media_reader.py` 为 L1（import 同域 `AttachmentService` + `infra.db` + `models.media.reader`）；`models/media/reader.py` 为中立域（禁止 import tenant/integrations）。
- 短会话语义保留：每次读取新开 `AsyncSessionLocal()`（不把请求级 session 塞进 RunContext）。
- 行为等价（OCR）+ 显式缺陷修复（AudioTranscribe，见完成标准）；`_make_ctx` 的权限/用户名字段在新 reader 中等价复刻。
- 中文 docstring；改动 ≤ 400 行。
- 每任务定向 + 全量回归（基线 **497 passed**；`uv run` 改写 `backend/uv.lock` 须还原）。
- 提交：每任务独立 commit，简体中文 `<type>(<scope>): <简述>`（scope `engine`）。

---

### Task 1: 中立契约 + `AttachmentService.read_attachment_bytes` + L1 reader + 单测

**Files:**
- Create: `backend/app/models/media/reader.py`
- Modify: `backend/app/tenant/attachments/services/attachment.py`
- Create: `backend/app/tenant/attachments/services/media_reader.py`
- Create: `backend/tests/tenant/attachments/test_flow_media_reader.py`
- Create: `backend/tests/tenant/attachments/test_attachment_read_bytes.py`
- Modify: `backend/tests/test_l3_neutral_imports.py`（`_CONVERGED` 加 `models/media`）

**Interfaces:**
- Produces: `AttachmentBytes`、`MediaReader`、`AttachmentService.read_attachment_bytes`、`build_flow_media_reader`（Task 2/3 消费）。

- [ ] **Step 1: 中立契约**

按 Architecture 建 `app/models/media/reader.py`（verbatim）。

- [ ] **Step 2: `AttachmentService.read_attachment_bytes`**

按 Architecture 加入 `attachment.py`（放在 `read_image_bytes` 之后、`delete` 之前）；复用已 import 的 `BadRequestError`/`resolve_object_storage_async`。

- [ ] **Step 3: L1 reader**

`tenant/attachments/services/media_reader.py`：
```python
"""画布媒体节点附件读取器（L1，实现 L3 中性 MediaReader 契约）。

``FlowMediaReader`` 持有 tenant_id/user_id，每次读取开短会话并构造带
``attachment:read`` 权限的 TenantContext，委托 ``AttachmentService`` 完成租户
鉴权 + 对象存储读取；装配点为 chat_rag.flow_run_context 与 flows flow debug-run。
"""

from __future__ import annotations

from uuid import UUID

from app.core.tenant import TenantContext
from app.infra.db import AsyncSessionLocal
from app.models.media.reader import AttachmentBytes
from app.tenant.attachments.services.attachment import AttachmentService


class FlowMediaReader:
    """短会话媒体读取器（每调用新开 AsyncSessionLocal）。"""

    def __init__(self, *, tenant_id: UUID, user_id: UUID | None) -> None:
        self._tenant_id = tenant_id
        self._user_id = user_id

    def _ctx(self) -> TenantContext:
        return TenantContext(
            user_id=self._user_id,
            tenant_id=self._tenant_id,
            username="flow_media",
            is_superuser=False,
            permissions=frozenset(["attachment:read"]),
        )

    async def read_image_bytes(self, attachment_id: UUID) -> AttachmentBytes:
        async with AsyncSessionLocal() as db:
            data, mime = await AttachmentService(db, self._ctx()).read_image_bytes(attachment_id)
        return AttachmentBytes(data=data, mime=mime)

    async def read_attachment_bytes(self, attachment_id: UUID) -> AttachmentBytes:
        async with AsyncSessionLocal() as db:
            data, mime, filename = await AttachmentService(db, self._ctx()).read_attachment_bytes(attachment_id)
        return AttachmentBytes(data=data, mime=mime, filename=filename)


def build_flow_media_reader(
    *,
    tenant_id: str | UUID,
    user_id: str | UUID | None = None,
) -> FlowMediaReader:
    """构造 RunContext.media_reader（str/UUID 均可；None user_id 表示匿名运行）。"""
    return FlowMediaReader(
        tenant_id=UUID(str(tenant_id)),
        user_id=UUID(str(user_id)) if user_id else None,
    )
```

- [ ] **Step 4: 单测**

1. `tests/tenant/attachments/test_flow_media_reader.py`（新建；`asyncio.run` 同步风格）：
   - monkeypatch `media_reader.AsyncSessionLocal`（假 async 上下文，`__aenter__` 返回假 db）、`media_reader.AttachmentService`（假类，记录 `(db, ctx)` 并按方法返回 `(b"img", "image/png")` / `(b"aud", "audio/mpeg", "a.mp3")`）。
   - `read_image_bytes` → `AttachmentBytes(data=b"img", mime="image/png", filename=None)`；断言假 service 收到的 `ctx.tenant_id/user_id/username/permissions` 正确。
   - `read_attachment_bytes` → `filename == "a.mp3"`。
   - `build_flow_media_reader(tenant_id="<uuid>", user_id="<uuid>")` 解析为 UUID；`user_id=None` → 内部 None。
2. `tests/tenant/attachments/test_attachment_read_bytes.py`（新建）：
   - 构造 `AttachmentService(db=FakeDb(), ctx=TenantContext(...))`，monkeypatch `attachment.resolve_object_storage_async`（returns SimpleNamespace(storage=SimpleNamespace(download_bytes=lambda key, bucket: b"raw"))）与 `_get_or_raise`（返回 `SimpleNamespace(tenant_id=..., object_key="k", object_bucket=None, mime_type="audio/mpeg", filename="a.mp3")`）。
   - 断言返回 `(b"raw", "audio/mpeg", "a.mp3")`。
   - `object_key="pending"` → `pytest.raises(BadRequestError)` match "未就绪"。

Run（backend/ 下）：
```bash
uv run ruff check app/models/media app/tenant/attachments/services tests/tenant/attachments tests/test_l3_neutral_imports.py
uv run python -m pytest tests/tenant/attachments tests/test_l3_neutral_imports.py -q
```
Expected：ruff 绿；用例全过。

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/media/reader.py backend/app/tenant/attachments/services/attachment.py backend/app/tenant/attachments/services/media_reader.py backend/tests/tenant/attachments backend/tests/test_l3_neutral_imports.py
git commit -m "refactor(engine): 新增媒体读取中立契约与 L1 短会话读取器

MediaReader/AttachmentBytes 下沉 models/media，AttachmentService 增
read_attachment_bytes，供画布媒体节点去租户化引用。"
```

---

### Task 2: `RunContext.media_reader` + `media_nodes.py` 契约化 + 节点测试

**Files:**
- Modify: `backend/app/flow_runtime/types.py`
- Modify: `backend/app/flow_runtime/nodes/media_nodes.py`
- Create: `backend/tests/flow/test_media_nodes.py`

**Interfaces:**
- Consumes: Task 1 `MediaReader`/`AttachmentBytes`。
- Produces: `RunContext.media_reader`；`media_nodes.py` 对 tenant import 清零。

- [ ] **Step 1: RunContext 字段**

`flow_runtime/types.py`：`load_subflow_graph` 之后追加 Architecture 段 `media_reader` 字段。

- [ ] **Step 2: 节点改造**

按 Architecture 改 `media_nodes.py`：
- 删 `from uuid import UUID`? **保留**（`UUID(attachment_id)` 仍需）；删 `from sqlalchemy import select`、`from app.core.tenant import TenantContext`、`from app.infra.db import AsyncSessionLocal`、`from app.models.media.attachment import Attachment`、`from app.tenant.attachments.services.attachment import AttachmentService`。
- 加 `from app.models.media.reader import MediaReader`（`_require_media_reader` 返回类型标注）。
- 删 `_make_ctx`；新增：
  ```python
  def _require_media_reader(ctx: RunContext) -> MediaReader:
      """取运行上下文注入的媒体读取器；未装配时报错。"""
      if ctx.media_reader is None:
          raise BadRequestError("运行上下文未提供媒体读取器")
      return ctx.media_reader
  ```
- `ocr_extract`/`audio_transcribe` 按 Architecture 改（`attachment_id` 空值检查/早返回**保留原样**）。
- 模块 docstring 改述：媒体字节经 ``RunContext.media_reader``（L1 注入，见 ``tenant.attachments.services.media_reader``）读取。

- [ ] **Step 3: 节点测试**

新建 `tests/flow/test_media_nodes.py`（`pytest.mark.asyncio`）：
- 用例 A（OCR）：假 reader（`read_image_bytes` → `AttachmentBytes(b"IMG", "image/png")`）；monkeypatch `app.flow_runtime.nodes.media_nodes.parse_image`（记录 `(data, name)` 返回 `"OCR-TEXT"`）→ `ocr_extract({"attachment_id": str(uuid4())}, {}, ctx)`：`output == "OCR-TEXT"`、`attachment_id` 回显、`mime_type == "image/png"`、`parse_image` 收到 `(b"IMG", f"ocr-{id}")`。
- 用例 B（音频 filename）：假 reader（`read_attachment_bytes` → `AttachmentBytes(b"AUD", "audio/mpeg", "a.mp3")`）；monkeypatch `parse_audio`（记录 filename 返回 `"ASR"`）→ `output == "ASR"`、`filename == "a.mp3"`。
- 用例 C（音频 filename 兜底）：reader 返回 `filename=None` → `filename == f"audio-{attachment_id}"`。
- 用例 D（缺 attachment_id）：`ocr_extract({}, {}, ctx)` 与 `audio_transcribe({}, {}, ctx)` → `BadRequestError`（无需 reader）。
- 用例 E（未装配 reader）：合法 attachment_id + `ctx.media_reader=None` → `BadRequestError` match "媒体读取器"。
- 用例 F（`_resolve_attachment_id` 变体）：`inputs={"media": [{"attachment_id": str(id)}]}` 命中；`node_data={"input_key":"file"}`+`inputs={"file": str(id)}` 命中（读音节点断言 attachment 回显即可）。

Run（backend/ 下）：
```bash
rg -n "from app\.tenant\.|import app\.tenant\." app/flow_runtime/nodes/ || echo "flow_nodes 对 tenant import 清零"
uv run ruff check app/flow_runtime/nodes app/flow_runtime/types.py tests/flow/test_media_nodes.py
uv run python -m pytest tests/flow/test_media_nodes.py -q
uv run python -m pytest -q | tail -1
```
Expected：rg 零命中；ruff 绿；用例全过；全量 ≥ 497 passed。

- [ ] **Step 4: Commit**

```bash
git add backend/app/flow_runtime/types.py backend/app/flow_runtime/nodes/media_nodes.py backend/tests/flow/test_media_nodes.py
git commit -m "refactor(engine): 画布媒体节点改走 RunContext 媒体读取器

OCR/AudioTranscribe 经 ctx.media_reader 读取附件，flow_runtime/nodes 对
tenant import 清零；AudioTranscribe 改用任意附件读取（修复音频必败缺陷）。"
```

---

### Task 3: 装配注入 + 透传 + 文档闭环

**Files:**
- Modify: `backend/app/tenant/agents/services/agent/chat_rag.py`
- Modify: `backend/app/tenant/flows/services/flow.py`
- Modify: `backend/app/integrations/langgraph/compiler/run.py`
- Modify: `backend/app/integrations/langgraph/compiler/build.py`
- Modify: `backend/app/flow_runtime/subflow/resolve.py`
- Modify: `backend/tests/flow/test_subflow.py`
- Modify: `backend/tests/tenant/agents/test_agent_chat_rag_flow_context.py`
- Modify: `docs/architecture/layering.md`

- [ ] **Step 1: 双根装配点注入**

- `chat_rag.py::flow_run_context`：函数级 import `from app.tenant.attachments.services.media_reader import build_flow_media_reader`；`RunContext(...)` 实参在 `load_subflow_graph=...,` 之后加 `media_reader=build_flow_media_reader(tenant_id=str(self.ctx.tenant_id), user_id=self.ctx.user_id),`。
- `flows/services/flow.py::run`（debug-run）：同上。

- [ ] **Step 2: state + subflow 透传**

- `compiler/run.py`：initial state 加 `"media_reader": ctx.media_reader,`。
- `compiler/build.py`：`_State` 加 `media_reader: Any`（附「L1 注入的附件读取器（随 ctx 透传，OcrExtract/AudioTranscribe 装配）」注释）；`run_node` 的 `RunContext(...)` 重建加 `media_reader=state.get("media_reader"),`。
- `subflow/resolve.py::build_child_context`：加 `media_reader=parent_ctx.media_reader,  # 媒体读取器透传到子流程`。

- [ ] **Step 3: 测试断言**

- `tests/flow/test_subflow.py`：parent 构造加 `media_reader=fake_media_reader,`（任意对象），断言 `assert child.media_reader is fake_media_reader`。
- `tests/tenant/agents/test_agent_chat_rag_flow_context.py`：按既有断言模式追加 `ctx.media_reader is not None`（不删既有）。

- [ ] **Step 4: 验证 + 全量回归**

Run（backend/ 下）：
```bash
rg -n "from app\.tenant\.|import app\.tenant\." app/flow_runtime/nodes/ || echo "flow_nodes 对 tenant import 清零"
uv run ruff check app/flow_runtime app/tenant/attachments app/tenant/agents/services/agent/chat_rag.py app/tenant/flows/services/flow.py app/integrations/langgraph/compiler app/models/media
uv run python -m pytest tests/flow tests/tenant/attachments tests/tenant/agents -q
uv run python -m pytest -q | tail -1
```
Expected：rg 零命中；ruff 绿；定向全过；全量 ≥ 497 passed。

- [ ] **Step 5: 文档 + 两次 commit**

`docs/architecture/layering.md`：G2-1 收敛记录之后追加：

```markdown
> **收敛记录（2026-09-09，G2-4a）**：画布媒体读取收敛——L3 中性契约 `app/models/media/reader.py`（`MediaReader`/`AttachmentBytes`）+ L1 短会话实现 `tenant/attachments/services/media_reader.py::build_flow_media_reader`（`AttachmentService` 增 `read_attachment_bytes`），经 `RunContext.media_reader` 注入；`flow_runtime/nodes/` 对 `tenant.*` import 清零，G2 画布节点面收官（AudioTranscribe 顺带修复误用图片读取的缺陷）。见 plan [`2026-09-09-engine-di-flow-media-reader`](../superpowers/plans/2026-09-09-engine-di-flow-media-reader.md)。
```

§8 修订表加固行之后追加：

```markdown
| 2026-09-09 | G2-4a：画布媒体读取收敛——MediaReader 中立契约 + RunContext.media_reader + L1 短会话读取器，flow_runtime/nodes 对 tenant 清零（G2 画布节点面收官） |
```

```bash
git add backend/app/tenant/agents/services/agent/chat_rag.py backend/app/tenant/flows/services/flow.py backend/app/integrations/langgraph/compiler/run.py backend/app/integrations/langgraph/compiler/build.py backend/app/flow_runtime/subflow/resolve.py backend/tests/flow/test_subflow.py backend/tests/tenant/agents/test_agent_chat_rag_flow_context.py
git commit -m "refactor(engine): 装配注入与透传 media_reader"

git add docs/architecture/layering.md
git commit -m "docs(architecture): 记录 G2-4a 画布媒体读取收敛"
```

---

## Self-Review

- **Spec coverage**：目标（media_nodes 去 tenant + G2 收官）由 Task 1（契约 + L1 实现）+ Task 2（节点切换 + 测试）+ Task 3（装配/透传/文档）达成。
- **行为等价与显式修复**：OCR 路径/返回字段/mime 语义不变；`_resolve_attachment_id` 逐字保留；AudioTranscribe 由「图片校验必败」改为任意附件读取（已在完成标准中显式声明并加用例 B/C 固化）；短会话语义保留（reader 内部 `AsyncSessionLocal`）。
- **依赖方向**：`models/media/reader.py` 中立（Task 1 审）；`media_reader.py` 为 L1（同域 + infra + 中立契约）；节点只引中立契约/`rag.parse`/`infra`/`core`；装配点 L1。守卫测试 `_CONVERGED` 增 `models/media`。
- **中间态**：Task 1 纯新增（可独立跑）；Task 2 节点切换同 commit 加测试；Task 3 装配闭环（同 G2-1/G2-2/G2-3 先例，langgraph 透传在末任务）。
- **测试罩**：L1 reader 用例 + `AttachmentService.read_attachment_bytes` 用例 + media 节点 6 用例 + 透传/装配断言；全量 ≥ 497。
- **Placeholder scan**：无 TBD；新代码（contracts/reader/节点片段）verbatim。
