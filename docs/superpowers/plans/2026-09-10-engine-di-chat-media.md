# G1-3 实施计划：`integrations/chat` 媒体读取收敛——L3 对 tenant 全域清零收官

> **归档：** 已实施并合并（engine DI 收敛，2026-09-10 校核）。**收敛记录：** [layering.md](../../architecture/layering.md) §8；执行明细见 `.superpowers/sdd/progress.md`。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 消除 `app/integrations/chat/multimodal.py`（L3）对 `tenant.attachments.services.attachment.AttachmentService` 的运行期 import——图片字节读取改经已存在的 L3 中性契约 `models.media.reader.MediaReader`（G2-4a 引入），由 L1 会话绑定实现 `SessionMediaReader` 注入；完成后 `app/integrations/**` 与 `app/flow_runtime/**` 对 `app.tenant` **全域清零**（engine DI 收官）。

**完成标准：**
- `rg "from app\.tenant|import app\.tenant" backend/app/integrations` 零命中；`tests/test_l3_neutral_imports.py::_CONVERGED` 纳入 `integrations/chat`。
- `integrations/chat/multimodal.py` 无 `AsyncSession`/`TenantContext`/`AttachmentService` import；`resolve_media_refs` / `build_invoke_messages_with_media` 接收 `reader: MediaReader`。
- L1 新增 `SessionMediaReader`（复用调用方 `db`/`ctx`，不开短会话）+ `build_session_media_reader`。
- 行为等价：`MAX_MEDIA_PER_TURN`/`MAX_IMAGE_BYTES`/`_IMAGE_DETAIL_VALUES` 校验、data URL 编码（`data:{mime};base64,...`）、media 为空时回退纯文本、RAG 仍以文本 query 检索——全部逐字保留。
- 全量测试 ≥ 513（基线）。

## 背景事实（已审计）

- `multimodal.py` 反依赖仅 1 处：`_resolve_attachment_data_url` 内惰性 `from app.tenant.attachments.services.attachment import AttachmentService`；纯函数 `build_user_message`/`messages_contain_image`/`media_refs_from_items` 无依赖。
- I/O 函数调用点（全部需切 reader）：
  - `app/integrations/langchain/tool_agent/loop.py:125`（L3，`run_tool_calling_chat`）
  - `app/integrations/langgraph/graphs/rag_qa.py:191,243`（L3，`generate`/`fallback` 节点，经 `configurable` 取装配件）
  - `app/rag/generate/answer.py:109`（L2，`rag_answer`）
  - `app/flow_runtime/nodes/llm_nodes.py:57`（L3，`RunContext` 可用）
  - `app/tenant/agents/services/agent/chat_rag.py:141`（L1，合法）
- `rag_qa.py` 的 `AsyncSessionLocal` 与 `_tenant_from_state` **仅**服务于 media 解析（grep 仅 185/237 两处）→ 可一并删除。
- `run_rag_workflow`（`langgraph/runner.py`）已有 `bindings`/`usage_sink`/`media` 写 `configurable` 的先例，`media_reader` 同法透传。
- `rag_answer` 的 `ctx: TenantContext | None` **仅**用于 media（answer.py:108）→ 可改为 `media_reader`；调用点只有 `chat_rag.py:363`，无测试传 `ctx`。
- `RunContext.media_reader` 已存在（G2-4a）并已在双根装配点注入 → `llm_nodes` 零新字段。
- `flow_runtime/context_utils.tenant_context_from_run` 仍被 `image/video_generate.py` 使用 → **保留**。
- 既有测试 patch 面：`tests/tenant/agents/test_multimodal_chat.py`、`tests/rag/test_rag_multimodal.py`、`tests/flow/test_flow_multimodal.py`。

**Architecture:**

- **L1 会话读取器**（`tenant/attachments/services/media_reader.py` 追加）：`SessionMediaReader(db, ctx)` 实现 `models.media.reader.MediaReader`，委托 `AttachmentService(self._db, self._ctx)`；与既有 `FlowMediaReader`（短会话）并存。
- **L3 契约化**（`integrations/chat/multimodal.py`）：两个 I/O 函数首参由 `(db, ctx)` 改为 `reader: MediaReader`；`_resolve_attachment_data_url(reader, attachment_id)` 用 `reader.read_image_bytes` 取 `AttachmentBytes`。
- **装配**：L1 `chat_rag` 每次请求构造 `build_session_media_reader(self.db, self.ctx)` 并注入 `run_tool_calling_chat` / `run_rag_workflow` / `rag_answer`；`flow_runtime/nodes/llm_nodes` 直接用 `ctx.media_reader`；`rag_qa` 从 `configurable.media_reader` 取。

## Global Constraints

- 分层：L3 = `app/integrations/**` + `app/flow_runtime/**`（不含 `app/tenant`）；L1 = `app/tenant/**`。改后 L3 对 `app.tenant` 直接/template import 一律禁止（`rg` 零命中）。
- 行为等价：见完成标准第三/四条；不改 `MAX_*` 常量值与异常文案；`resolve_media_refs` 的 detail 校验与 max_count 校验顺序不变。
- `integrations/chat/**` 内注释/docstring 不得出现字面量 `app.tenant`（守卫测试按行子串扫描）；提 L1 路径写 ``tenant.attachments.services.media_reader``。
- 中文 docstring；每任务定向 + 全量回归（基线 **513 passed**；`uv run` 改写 `backend/uv.lock` 须 `git checkout -- backend/uv.lock` 还原）。
- 提交：每任务独立 commit，简体中文 `<type>(<scope>): <简述>`（scope `engine`）。

---

### Task 1: L1 `SessionMediaReader` + 单测

**Files:**
- Modify: `backend/app/tenant/attachments/services/media_reader.py`
- Create: `backend/tests/tenant/attachments/test_session_media_reader.py`

**Interfaces:**
- Produces: `SessionMediaReader`、`build_session_media_reader(db, ctx)`（Task 2/3 装配消费）。

- [ ] **Step 1: 追加会话读取器**

在 `media_reader.py` 的 `FlowMediaReader` 之后、`build_flow_media_reader` 之前或之后追加（保持文件内同类相邻）：

```python
class SessionMediaReader:
    """会话绑定的媒体读取器（复用调用方 ``db``/``ctx``，不再开短会话）。

    适用于请求/图节点已持有租户会话的场景（Agent 对话、RAG、工具循环），
    与 ``FlowMediaReader``（自开 ``AsyncSessionLocal``）互补。
    """

    def __init__(self, *, db: AsyncSession, ctx: TenantContext) -> None:
        self._db = db
        self._ctx = ctx

    async def read_image_bytes(self, attachment_id: UUID) -> AttachmentBytes:
        data, mime = await AttachmentService(self._db, self._ctx).read_image_bytes(attachment_id)
        return AttachmentBytes(data=data, mime=mime)

    async def read_attachment_bytes(self, attachment_id: UUID) -> AttachmentBytes:
        data, mime, filename = await AttachmentService(self._db, self._ctx).read_attachment_bytes(attachment_id)
        return AttachmentBytes(data=data, mime=mime, filename=filename)


def build_session_media_reader(db: AsyncSession, ctx: TenantContext) -> SessionMediaReader:
    """构造复用既有会话的 ``MediaReader``（装配点：chat_rag / RAG / 工具循环）。"""
    return SessionMediaReader(db=db, ctx=ctx)
```

若 `AsyncSession` 尚未 import，补 `from sqlalchemy.ext.asyncio import AsyncSession`。同步更新模块 docstring 提及两种读取器。

- [ ] **Step 2: 单测**

新建 `tests/tenant/attachments/test_session_media_reader.py`（`asyncio.run` 同步风格，与 `test_flow_media_reader.py` 一致）：

```python
"""SessionMediaReader：复用调用方会话的媒体读取器。"""

import asyncio
from uuid import uuid4

from app.core.tenant import TenantContext
from app.models.media.reader import AttachmentBytes
from app.tenant.attachments.services import media_reader as mod


def _run(coro):
    return asyncio.run(coro)


def _ctx() -> TenantContext:
    return TenantContext(
        user_id=uuid4(),
        tenant_id=uuid4(),
        username="session-media",
        is_superuser=False,
        permissions=frozenset(["attachment:read"]),
    )


def test_session_reader_reads_image_with_caller_session(monkeypatch):
    calls: list[object] = []

    class FakeService:
        def __init__(self, db, ctx):
            calls.append((db, ctx))

        async def read_image_bytes(self, attachment_id):
            return b"IMG", "image/png"

    monkeypatch.setattr(mod, "AttachmentService", FakeService)
    db, ctx = object(), _ctx()
    att = mod.build_session_media_reader(db, ctx).read_image_bytes(uuid4())
    out = _run(att)
    assert out == AttachmentBytes(data=b"IMG", mime="image/png", filename=None)
    # 复用调用方会话/上下文，未新开 session
    assert calls[0][0] is db and calls[0][1] is ctx


def test_session_reader_reads_attachment_with_filename(monkeypatch):
    class FakeService:
        def __init__(self, db, ctx):
            pass

        async def read_attachment_bytes(self, attachment_id):
            return b"AUD", "audio/mpeg", "a.mp3"

    monkeypatch.setattr(mod, "AttachmentService", FakeService)
    att = mod.build_session_media_reader(object(), _ctx()).read_attachment_bytes(uuid4())
    out = _run(att)
    assert out == AttachmentBytes(data=b"AUD", mime="audio/mpeg", filename="a.mp3")
```

- [ ] **Step 3: 验证 + 提交**

Run（backend/ 下）：
```bash
uv run ruff check app/tenant/attachments/services/media_reader.py tests/tenant/attachments
uv run python -m pytest tests/tenant/attachments -q
uv run python -m pytest -q | tail -1
```
Expected：ruff 绿；定向全过；全量 ≥ 513 passed。

```bash
git add backend/app/tenant/attachments/services/media_reader.py backend/tests/tenant/attachments/test_session_media_reader.py
git commit -m "refactor(engine): 新增会话绑定媒体读取器 SessionMediaReader

为 integrations/chat 媒体读取去租户化铺路：复用调用方 db/ctx 实现
MediaReader，与短会话 FlowMediaReader 互补。"
```

---

### Task 2: `integrations/chat` 契约化 + 全链装配切换 + 测试迁移 + 守卫纳入

**Files:**
- Modify: `backend/app/integrations/chat/multimodal.py`
- Modify: `backend/app/flow_runtime/nodes/llm_nodes.py`
- Modify: `backend/app/integrations/langchain/tool_agent/loop.py`
- Modify: `backend/app/integrations/langgraph/graphs/rag_qa.py`
- Modify: `backend/app/integrations/langgraph/runner.py`
- Modify: `backend/app/rag/generate/answer.py`
- Modify: `backend/app/tenant/agents/services/agent/chat_rag.py`
- Modify: `backend/tests/tenant/agents/test_multimodal_chat.py`
- Modify: `backend/tests/rag/test_rag_multimodal.py`
- Modify: `backend/tests/flow/test_flow_multimodal.py`
- Modify: `backend/tests/test_l3_neutral_imports.py`

**Interfaces:**
- Consumes: Task 1 `build_session_media_reader`；`models.media.reader.MediaReader`。
- Produces: `resolve_media_refs(reader, refs, *, max_count=...)`；`build_invoke_messages_with_media(reader, *, prompt_text, media, max_count=...)`；`run_tool_calling_chat(..., media_reader=...)`；`run_rag_workflow(..., media_reader=...)`；`rag_answer(..., media_reader=...)`。

- [ ] **Step 1: `multimodal.py` 契约化（整文件替换）**

```python
"""
多模态 user 消息：附件 → OpenAI content parts（base64 data URL）。

v1 不向厂商/浏览器提供对象存储签名 URL。
附件字节读取经注入的 ``MediaReader``（L3 中性契约 ``models.media.reader``；
L1 实现见 ``tenant.attachments.services.media_reader``），本模块不接触租户域。
"""

from __future__ import annotations

import base64
from typing import Any
from uuid import UUID

from app.common.exceptions import BadRequestError
from app.common.schemas.media import MediaRefIn
from app.models.media.reader import MediaReader

MAX_MEDIA_PER_TURN = 10
MAX_IMAGE_BYTES = 10 * 1024 * 1024
_IMAGE_DETAIL_VALUES = frozenset({"auto", "low", "high"})


def build_user_message(*, query: str, media_parts: list[dict[str, Any]]) -> dict[str, Any]:
    """组装 OpenAI 形状 user message（content 为 str 或 part 数组）。"""
    text = (query or "").strip()
    if not media_parts:
        return {"role": "user", "content": text}
    content: list[dict[str, Any]] = []
    content.append({"type": "text", "text": text or "请根据附图回答。"})
    content.extend(media_parts)
    return {"role": "user", "content": content}


def messages_contain_image(messages: list[dict[str, Any]]) -> bool:
    """任一 message 的 content 含 image_url part。"""
    for msg in messages:
        raw = msg.get("content")
        if not isinstance(raw, list):
            continue
        for part in raw:
            if isinstance(part, dict) and part.get("type") == "image_url":
                return True
    return False


async def resolve_media_refs(
    reader: MediaReader,
    refs: list[MediaRefIn],
    *,
    max_count: int = MAX_MEDIA_PER_TURN,
) -> list[dict[str, Any]]:
    """批量解析为 LiteLLM/OpenAI image_url content parts（字节经 ``reader`` 读取）。"""
    if len(refs) > max_count:
        raise BadRequestError(f"每轮最多 {max_count} 张图片")
    parts: list[dict[str, Any]] = []
    for ref in refs:
        detail = (ref.detail or "auto").strip().lower()
        if detail not in _IMAGE_DETAIL_VALUES:
            raise BadRequestError(f"不支持的 image detail: {ref.detail}")
        url = await _resolve_attachment_data_url(reader, ref.attachment_id)
        image_url: dict[str, Any] = {"url": url}
        if detail != "auto":
            image_url["detail"] = detail
        parts.append({"type": "image_url", "image_url": image_url})
    return parts


async def build_invoke_messages_with_media(
    reader: MediaReader,
    *,
    prompt_text: str,
    media: list[MediaRefIn] | None,
    max_count: int = MAX_MEDIA_PER_TURN,
) -> list[dict[str, Any]]:
    """RAG / 兜底生成：单条 user message，可选附图（检索仍仅用文本 query）。"""
    if not media:
        return [{"role": "user", "content": prompt_text}]
    parts = await resolve_media_refs(reader, media, max_count=max_count)
    return [build_user_message(query=prompt_text, media_parts=parts)]


def media_refs_from_items(items: list[Any] | None) -> list[MediaRefIn]:
    """ChatRequest.media / state.media → MediaRefIn 列表。"""
    refs: list[MediaRefIn] = []
    for item in items or []:
        if isinstance(item, MediaRefIn):
            refs.append(item)
        elif isinstance(item, dict) and item.get("attachment_id"):
            refs.append(MediaRefIn.model_validate(item))
    return refs


async def _resolve_attachment_data_url(reader: MediaReader, attachment_id: UUID) -> str:
    """``reader`` 鉴权读图 → OpenAI/LiteLLM 所需的 data URL（不向厂商暴露 object_key）。"""
    att = await reader.read_image_bytes(attachment_id)
    if len(att.data) > MAX_IMAGE_BYTES:
        raise BadRequestError(f"单张图片不能超过 {MAX_IMAGE_BYTES // (1024 * 1024)}MB")
    encoded = base64.standard_b64encode(att.data).decode("ascii")
    return f"data:{att.mime};base64,{encoded}"
```

（`integrations/chat/__init__.py` 的 re-export 名单不变，无需改。）

- [ ] **Step 2: `flow_runtime/nodes/llm_nodes.py` 用 `ctx.media_reader`**

- 删 `from app.infra.db import AsyncSessionLocal`、`tenant_context_from_run`（保留 `media_refs_from_run`）。
- media 段改为：

```python
    max_media = int((ctx.agent_config or {}).get("max_media_per_turn", 10))
    media_parts: list[dict[str, Any]] = []
    if media_refs:
        if ctx.media_reader is None:
            raise BadRequestError("运行上下文未提供媒体读取器")
        media_parts = await resolve_media_refs(ctx.media_reader, media_refs, max_count=max_media)
```

- 模块 docstring 补一句：附图字节经 ``RunContext.media_reader``（L1 注入）读取。

- [ ] **Step 3: `tool_agent/loop.py` 接收 `media_reader`**

- import：`from app.models.media.reader import MediaReader`。
- 签名在 `platform_tools: list,` 之后加 `media_reader: MediaReader,`。
- `run_tool_calling_chat` 内第 125 行改为：

```python
    media_parts = await resolve_media_refs(media_reader, body.media, max_count=max_media) if body.media else []
```

- docstring 补：``media_reader`` 由 L1 注入（``tenant.attachments.services.media_reader``）。

- [ ] **Step 4: `langgraph/graphs/rag_qa.py` 经 configurable 取 reader**

- 删 `_tenant_from_state` 函数、`TenantContext` import、`AsyncSessionLocal` import（确认无其他使用）。
- `generate` 与 `fallback` 中 media 段统一改为：

```python
    media_refs = media_refs_from_items(state.get("media"))
    media_reader = config.get("configurable", {}).get("media_reader") if config else None
    if media_refs and media_reader:
        messages = await build_invoke_messages_with_media(
            media_reader,
            prompt_text=prompt,
            media=media_refs,
        )
    else:
        messages = [{"role": "user", "content": prompt}]
```

（删去各自 `async with AsyncSessionLocal() as db:` 及其内部 try/except；`on_delta`/`usage_sink`/`ainvoke_chat` 原样保留。）

- [ ] **Step 5: `langgraph/runner.py` 透传**

- import `from app.models.media.reader import MediaReader`（与既有 import 组同域）。
- 签名在 `bindings: KbRetrievalBindings | None = None,` 之后加 `media_reader: MediaReader | None = None,`。
- docstring 补 ``media_reader`` 写入 configurable（由 generate/fallback 节点读取）。
- `run_config["configurable"]` 加 `"media_reader": media_reader,`。

- [ ] **Step 6: `rag/generate/answer.py` 用 reader 替换 `ctx`**

- import：`from app.models.media.reader import MediaReader`；若 `TenantContext` 不再使用则删该 import。
- 签名：删 `ctx: TenantContext | None = None,`，在 `media` 附近加 `media_reader: MediaReader | None = None,`。
- media 段改为：

```python
    messages: list[dict[str, Any]]
    if media and media_reader:
        messages = await build_invoke_messages_with_media(
            media_reader,
            prompt_text=prompt,
            media=media,
        )
    else:
        messages = [{"role": "user", "content": prompt}]
```

- docstring 补 ``media_reader`` 由 L1 注入。

- [ ] **Step 7: L1 `chat_rag.py` 装配注入**

- 顶部 import 加 `from app.tenant.attachments.services.media_reader import build_session_media_reader`。
- `resolve_chat_media_parts`（L141）：

```python
            parts = await resolve_media_refs(
                build_session_media_reader(self.db, self.ctx),
                body.media,
                max_count=max_media,
            )
```

- 两处 `run_tool_calling_chat(...)` 调用（L259 起与其后 skill 分支）均在 `tool_executor=...,` 后加 `media_reader=build_session_media_reader(self.db, self.ctx),`。
- `run_rag_workflow(...)`：`bindings=kb_bindings,` 后加 `media_reader=build_session_media_reader(self.db, self.ctx),`。
- `rag_answer(...)`：把 `ctx=self.ctx,` 换成 `media_reader=build_session_media_reader(self.db, self.ctx),`。

- [ ] **Step 8: 既有测试迁移**

`tests/tenant/agents/test_multimodal_chat.py`：
- `test_resolve_media_refs_too_many`：改为 `await resolve_media_refs(MagicMock(), refs, max_count=10)`（删 `ctx` 构造）。
- `test_resolve_media_refs_builds_data_url`：删 `AttachmentService` patch，改用假 reader：

```python
    from app.models.media.reader import AttachmentBytes

    class FakeReader:
        async def read_image_bytes(self, attachment_id):
            return AttachmentBytes(data=png, mime="image/png")

    parts = await resolve_media_refs(FakeReader(), [MediaRefIn(attachment_id=att_id)])
```

- 新增超限用例：

```python
@pytest.mark.asyncio
async def test_resolve_media_refs_rejects_oversize_image():
    from app.models.media.reader import AttachmentBytes
    from app.integrations.chat.multimodal import MAX_IMAGE_BYTES

    class FakeReader:
        async def read_image_bytes(self, attachment_id):
            return AttachmentBytes(data=b"x" * (MAX_IMAGE_BYTES + 1), mime="image/png")

    with pytest.raises(BadRequestError, match="不能超过"):
        await resolve_media_refs(FakeReader(), [MediaRefIn(attachment_id=uuid4())])
```

`tests/rag/test_rag_multimodal.py`：
- `test_build_invoke_messages_with_media`：用假 reader 替换 `(db, ctx)` 与 `resolve_media_refs` patch：

```python
    class FakeReader:
        async def read_image_bytes(self, attachment_id):
            from app.models.media.reader import AttachmentBytes

            return AttachmentBytes(data=b"\x89PNG\r\n\x1a\n", mime="image/png")

    msgs = await build_invoke_messages_with_media(
        FakeReader(),
        prompt_text="参考：...\n\n用户问题：看图",
        media=[MediaRefIn(attachment_id=att_id)],
    )
```

（删 `TenantContext` import 与 ctx 构造。）
- `test_generate_node_with_media`：`config = {"configurable": {"model": model, "media_reader": MagicMock()}}`；删 `AsyncSessionLocal` patch 与其 db mock；保留 `mock_build.assert_awaited_once()`。
- `test_run_rag_workflow_passes_media_in_initial`：调用加 `media_reader=reader`（`reader = object()`），并断言 `mock_graph.ainvoke.await_args.kwargs["configurable"]["media_reader"] is reader`（若 `ainvoke` 以关键字传 config；否则用 `await_args.args[1]` —— 以实际调用形态为准）。

`tests/flow/test_flow_multimodal.py::test_llm_call_with_media_builds_multimodal_message`：
- `ctx` 增 `media_reader=object(),`（追加到 `usage_sink=usage_sink,` 后）。
- 删 `patch("app.flow_runtime.nodes.llm_nodes.AsyncSessionLocal")` 及其 session mock（llm_nodes 已无该属性，保留会 AttributeError）。

- [ ] **Step 9: 守卫测试纳入**

`tests/test_l3_neutral_imports.py` 的 `_CONVERGED` 增加：

```python
    ("integrations/chat", "integrations/chat"),
```

- [ ] **Step 10: 验证 + 提交**

Run（backend/ 下）：
```bash
rg -n "from app\.tenant|import app\.tenant" app/integrations || echo "integrations 对 app.tenant 清零"
uv run ruff check app/integrations app/flow_runtime app/rag app/tenant/agents tests/test_l3_neutral_imports.py
uv run python -m pytest tests/rag tests/flow tests/tenant/agents tests/test_l3_neutral_imports.py -q
uv run python -m pytest -q | tail -1
```
Expected：`rg` 零命中；ruff 绿；定向全过；全量 ≥ 513 passed。

```bash
git add backend/app/integrations/chat/multimodal.py backend/app/flow_runtime/nodes/llm_nodes.py backend/app/integrations/langchain/tool_agent/loop.py backend/app/integrations/langgraph/graphs/rag_qa.py backend/app/integrations/langgraph/runner.py backend/app/rag/generate/answer.py backend/app/tenant/agents/services/agent/chat_rag.py backend/tests/tenant/agents/test_multimodal_chat.py backend/tests/rag/test_rag_multimodal.py backend/tests/flow/test_flow_multimodal.py backend/tests/test_l3_neutral_imports.py
git commit -m "refactor(engine): chat 多模态读取改走 MediaReader，L3 对 tenant 清零

resolve_media_refs/build_invoke_messages_with_media 接收 L1 注入的
MediaReader；Agent 对话/RAG/工具循环/画布 LLMCall 全部切换，rag_qa 顺带
移除仅供读图的会话与 _tenant_from_state；守卫测试纳入 integrations/chat。"
```

---

### Task 3: 测试卫生清理 + 文档闭环 + engine DI 全域终检

**Files:**
- Modify: `backend/tests/rag/test_rag_answer_stream.py`
- Modify: `docs/architecture/layering.md`

- [ ] **Step 0: 清理死 mock（Task 2 评审 Minor）**

`tests/rag/test_rag_answer_stream.py` 的 `test_generate_node_forwards_on_delta` 与 `test_fallback_node_forwards_on_delta` 仍 patch `app.integrations.langgraph.graphs.rag_qa.AsyncSessionLocal`，但 `generate`/`fallback` 已不再开会话（仅 `retrieve` 用）。删除两处 `patch("...rag_qa.AsyncSessionLocal")` 及其 `session_cls`/`db` 设置，保留其余 patch 与断言。

- [ ] **Step 1: 全域终检**

Run（backend/ 下）：
```bash
rg -n "from app\.tenant|import app\.tenant" app/integrations app/flow_runtime || echo "L3（integrations + flow_runtime）对 app.tenant 全域清零"
rg -n "app\.tenant" app/integrations/chat app/integrations/generative app/flow_runtime/nodes || echo "已收敛区注释级也零命中"
uv run python -m pytest -q | tail -1
```
Expected：全部零命中；全量 ≥ 513 passed。

- [ ] **Step 2: 文档 + 提交**

`docs/architecture/layering.md`：G1-2 收敛记录之后追加：

```markdown
> **收敛记录（2026-09-10，G1-3）**：`integrations/chat` 媒体读取收敛——多模态 I/O（`resolve_media_refs` / `build_invoke_messages_with_media`）首参由 `(db, ctx)` 改为 L3 中性 `MediaReader`，L1 新增 `SessionMediaReader`（复用调用方会话，`tenant.attachments.services.media_reader`）并注入 Agent 对话 / RAG / 工具循环 / 画布 LLMCall；`rag_qa` 顺带移除仅供读图的会话与 `_tenant_from_state`。至此 **`integrations/**` 与 `flow_runtime/**` 对 `tenant` 全域清零**，engine DI 反依赖收敛收官。见 plan [`2026-09-10-engine-di-chat-media`](../superpowers/plans/2026-09-10-engine-di-chat-media.md)。
```

§8 修订表 G1-2 行之后追加：

```markdown
| 2026-09-10 | G1-3：`integrations/chat` 媒体读取收敛——MediaReader 注入多模态 I/O + L1 SessionMediaReader，**L3（integrations + flow_runtime）对 tenant 全域清零，engine DI 收官** |
```

```bash
git add backend/tests/rag/test_rag_answer_stream.py
git commit -m "test(engine): 清理 rag_qa 生成节点已失效的会话 mock"

git add docs/architecture/layering.md
git commit -m "docs(architecture): 记录 G1-3 chat 媒体读取收敛与 L3 全域清零"
```

---

## Self-Review

- **Spec coverage**：完成标准四条分别由 Task 1（L1 reader）+ Task 2（契约化 + 全链装配 + 测试迁移 + 守卫纳入）+ Task 3（文档 + 全域终检）达成。
- **行为等价**：Task 2 Step 1 的 `multimodal.py` 为除首参与读图实现外逐字保留（常量值、校验顺序、异常文案、data URL 格式、`build_user_message` 默认文案）；`rag_answer` 仅把 `ctx` 换为 `media_reader`（原 `ctx` 只用于 media，无其它语义）。
- **依赖方向**：`multimodal.py` 只依赖 `common`/`models.media.reader`；`llm_nodes` 用 `RunContext.media_reader`；`loop.py`/`rag_qa.py`/`runner.py`/`answer.py` 接收注入；装配全部在 L1 `chat_rag`。
- **中间态**：Task 1 纯新增（绿）；Task 2 为一个原子切换（L3 签名与全部 L3/L2/L1 调用方同 commit；定向 + 全量回归兜底）；Task 3 文档。
- **类型一致性**：`MediaReader`/`AttachmentBytes` 沿用 G2-4a 契约；`SessionMediaReader` 与 `FlowMediaReader` 同接口；`build_session_media_reader` 名称在 Task 1 定义、Task 2 消费。
- **Placeholder scan**：无 TBD；新文件与改动片段完整给出；测试迁移给出具体替换代码。
