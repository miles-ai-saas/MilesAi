# tool_agent / agent.chat 超标拆分 Implementation Plan

> **归档：** 实施 checklist（2026-07-28，纯内部拆分，无 features 文档）。**现网代码：** `backend/app/integrations/langchain/tool_agent/`、`backend/app/tenant/agents/services/agent/`

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将超标的 `tool_agent.py`（808）与 `agent/chat.py`（571）按职责拆到子模块，行为不变，单文件 &lt;500 行。

**Architecture:** `integrations/langchain/tool_agent/` 子包（parse / artifacts / litellm_tools / loop）；`tenant/agents/services/agent/` 内将 `AgentChatMixin` 拆为 Turn / Entry / Rag 三个 Mixin，由薄 `chat.py` 组合。公开 `artifacts_from_tool_output`；删除旧单文件。

**Tech Stack:** FastAPI / SQLAlchemy async / LiteLLM；pytest；Ruff。

**Spec:** [docs/superpowers/specs/2026-07-28-tool-agent-chat-split-design.md](../specs/2026-07-28-tool-agent-chat-split-design.md)

## Global Constraints

- 单文件 `wc -l` **&lt;500**（宜 300–400）；`loop.py` 若仍 ≥500 允许再拆。
- Import 策略 **B**：可改路径；测试改用公开 `artifacts_from_tool_output`。
- 对外：`from app.integrations.langchain.tool_agent import run_tool_calling_chat`；`from app.tenant.agents.services.agent import AgentService`。
- **行为不变**：禁止改对话路由语义、tool 循环逻辑、确认/artifacts 规则。
- Commit message **简体中文** Conventional Commits。
- 先拆 tool_agent，再拆 chat；每任务末跑对应 pytest。

---

## File Structure

### Create

| 路径 | 职责 |
|------|------|
| `backend/app/integrations/langchain/tool_agent/__init__.py` | 导出 `run_tool_calling_chat`、`artifacts_from_tool_output` |
| `backend/app/integrations/langchain/tool_agent/parse.py` | 伪 tool_call 检测与参数提取（原 L45–284） |
| `backend/app/integrations/langchain/tool_agent/artifacts.py` | `artifacts_from_tool_output`（原 `_artifacts_from_tool_output`） |
| `backend/app/integrations/langchain/tool_agent/litellm_tools.py` | schema 转换 + `_litellm_with_tools` |
| `backend/app/integrations/langchain/tool_agent/loop.py` | `run_tool_calling_chat` |
| `backend/app/tenant/agents/services/agent/chat_turn.py` | Turn Mixin |
| `backend/app/tenant/agents/services/agent/chat_entry.py` | Entry Mixin |
| `backend/app/tenant/agents/services/agent/chat_rag.py` | Rag Mixin |

### Modify

| 路径 | 变更 |
|------|------|
| 删除 `backend/app/integrations/langchain/tool_agent.py` | 与目录不可共存 |
| `backend/app/tenant/agents/services/agent/chat.py` | 薄组合 + `_generative_tools_system_hint` |
| `backend/app/tenant/agents/services/agent/__init__.py` | 更新目录职责说明 |
| `backend/tests/tenant/generative/test_generative_image.py` | 改 import / 调用名 |
| `backend/tests/tenant/generative/test_generative_video.py` | 同上 |

### Unchanged callers（包取代模块后仍有效）

- `agent/chat.py`（拆后 `chat_rag.py`）内 `from app.integrations.langchain.tool_agent import run_tool_calling_chat`
- `service.py`：`from …agent.chat import AgentChatMixin`

---

### Task 1: tool_agent 子包 — parse / artifacts / litellm_tools

**Files:**
- Create: `backend/app/integrations/langchain/tool_agent/parse.py`
- Create: `backend/app/integrations/langchain/tool_agent/artifacts.py`
- Create: `backend/app/integrations/langchain/tool_agent/litellm_tools.py`
- Test: `backend/tests/tenant/generative/test_generative_image.py`（本任务末先不改旧模块，仅新增文件；旧 `tool_agent.py` 暂留）

**Interfaces:**
- Produces:
  - `parse.py`: `_GENERATIVE_INTENT_PHRASES`, `_looks_like_tool_call_simulation`, `_extract_tool_params_from_text`（及内部 helpers）
  - `artifacts.py`: `artifacts_from_tool_output(output: dict) -> list[ChatArtifact]`
  - `litellm_tools.py`: `_tools_to_openai_schema`, `_litellm_with_tools`

- [ ] **Step 1: 创建 `parse.py`**

从现有 `tool_agent.py` **原样搬迁** L45–284（常量 + `_clean_uuid_params` … `_extract_tool_params_from_text`）。文件头：

```python
"""伪 tool_call 文本检测与参数提取（供 tool_agent 循环兜底）。"""
from __future__ import annotations

import ast
import json
import re
from typing import Any
# … 仅保留本文件用到的 import
```

保留函数名与逻辑；不在此任务改行为。

- [ ] **Step 2: 创建 `artifacts.py`**

将原 `_artifacts_from_tool_output` **改名为** `artifacts_from_tool_output`，正文逻辑不变：

```python
"""generate_* 工具输出 → ChatArtifact。"""
from __future__ import annotations

from uuid import UUID

from app.tenant.agents.schemas.agent import ChatArtifact


def artifacts_from_tool_output(output: dict) -> list[ChatArtifact]:
    """将 invoke 返回的 generate_* 字典转为 ChatArtifact（供前端预览）。"""
    # 正文 = 原 _artifacts_from_tool_output，一字不改逻辑
    ...
```

- [ ] **Step 3: 创建 `litellm_tools.py`**

搬迁原 `_tools_to_openai_schema`、`_litellm_with_tools`（约 L359–393）及所需 import（`litellm`、`adapter` 私有 helpers、`resolve_litellm_model`）。

- [ ] **Step 4: 行数自检**

Run:

```bash
cd backend && wc -l app/integrations/langchain/tool_agent/parse.py \
  app/integrations/langchain/tool_agent/artifacts.py \
  app/integrations/langchain/tool_agent/litellm_tools.py
```

Expected: 各文件 &lt;500；此时旧 `tool_agent.py` 仍存在（下一任务删除）。

- [ ] **Step 5: Commit**

```bash
git add backend/app/integrations/langchain/tool_agent/
git commit -m "$(cat <<'EOF'
refactor(integrations): 抽出 tool_agent 的 parse/artifacts/litellm 子模块

为超标单文件拆包做准备，本提交尚未切换入口。
EOF
)"
```

---

### Task 2: tool_agent loop + 包入口 + 删旧文件 + 测例

**Files:**
- Create: `backend/app/integrations/langchain/tool_agent/loop.py`
- Create: `backend/app/integrations/langchain/tool_agent/__init__.py`
- Delete: `backend/app/integrations/langchain/tool_agent.py`
- Modify: `backend/tests/tenant/generative/test_generative_image.py`
- Modify: `backend/tests/tenant/generative/test_generative_video.py`

**Interfaces:**
- Consumes: Task 1 的 parse / artifacts / litellm_tools
- Produces: `run_tool_calling_chat(...)`；包级 `__all__`

- [ ] **Step 1: 先改测试 import（指向新公开名）**

在 `test_generative_image.py` / `test_generative_video.py`：

```python
from app.integrations.langchain.tool_agent import artifacts_from_tool_output
```

并将所有 `_artifacts_from_tool_output(...)` 调用改为 `artifacts_from_tool_output(...)`。  
（旧单文件仍导出同名时可临时双轨；本任务在删旧文件前必须保证包可导入。）

- [ ] **Step 2: 创建 `loop.py`**

搬迁原 `run_tool_calling_chat`（约 L396–808）。顶部 import 改为：

```python
"""LiteLLM 多轮 function calling 主循环。"""
from __future__ import annotations
# … 原有第三方/业务 import（去掉已迁走的 parse helpers 定义）

from app.integrations.langchain.tool_agent.artifacts import artifacts_from_tool_output
from app.integrations.langchain.tool_agent.litellm_tools import (
    _litellm_with_tools,
    _tools_to_openai_schema,
)
from app.integrations.langchain.tool_agent.parse import (
    _GENERATIVE_INTENT_PHRASES,
    _extract_tool_params_from_text,
    _looks_like_tool_call_simulation,
)
```

函数体内所有 `_artifacts_from_tool_output` → `artifacts_from_tool_output`。  
**禁止**改循环分支逻辑。

- [ ] **Step 3: 创建 `__init__.py` 并删除旧 `tool_agent.py`**

```python
"""
智能体工具调用循环（无知识库绑定时可选）。

有 KB 时：若 enable_generative_tools 和/或绑定技能包且 enable_tool_calling，
走本包（knowledge_search + 可选 generate_*）；否则走 LangGraph/线性 RAG。
"""
from app.integrations.langchain.tool_agent.artifacts import artifacts_from_tool_output
from app.integrations.langchain.tool_agent.loop import run_tool_calling_chat

__all__ = [
    "artifacts_from_tool_output",
    "run_tool_calling_chat",
]
```

删除 `backend/app/integrations/langchain/tool_agent.py`。

- [ ] **Step 4: 验证无冲突 / 行数**

```bash
cd backend
test ! -f app/integrations/langchain/tool_agent.py
find app/integrations/langchain/tool_agent -name '*.py' -exec wc -l {} +
# 若 loop.py >= 500：再拆确认分支到 loop_confirm.py（允许，须同 commit 或紧随 commit）
```

- [ ] **Step 5: 跑测**

```bash
cd backend && python -m pytest tests/tenant/generative/test_generative_image.py tests/tenant/generative/test_generative_video.py -q
```

Expected: PASS（或仅环境相关 skip，无 ImportError / AttributeError）。

- [ ] **Step 6: Commit**

```bash
git add backend/app/integrations/langchain/tool_agent \
  backend/app/integrations/langchain/tool_agent.py \
  backend/tests/tenant/generative/test_generative_image.py \
  backend/tests/tenant/generative/test_generative_video.py
git commit -m "$(cat <<'EOF'
refactor(integrations): tool_agent 改为子包并公开 artifacts API

删除超标单文件；测试改用 artifacts_from_tool_output。
EOF
)"
```

---

### Task 3: 拆 `chat_turn` / `chat_rag` / `chat_entry`

**Files:**
- Create: `backend/app/tenant/agents/services/agent/chat_turn.py`
- Create: `backend/app/tenant/agents/services/agent/chat_rag.py`
- Create: `backend/app/tenant/agents/services/agent/chat_entry.py`
- Modify: `backend/app/tenant/agents/services/agent/chat.py`
- Modify: `backend/app/tenant/agents/services/agent/__init__.py`

**Interfaces:**
- Produces:
  - `AgentChatTurnMixin`: `_finish_chat_turn`, `_resolve_rag_route`, `_complete_chat_turn`
  - `AgentChatRagMixin`: `flow_run_context`, `maybe_augment_a2a`, `resolve_chat_media_parts`, `direct_chat`, `rag_chat`
  - `AgentChatEntryMixin`: `chat`, `chat_as_child`
  - `AgentChatMixin(AgentChatEntryMixin, AgentChatRagMixin, AgentChatTurnMixin)`
- Consumes: 现有 `AgentCrudMixin` 的 `get_agent_or_raise` / `resolve_system_prompt`；`self.db` / `self.ctx` / `self.flow_repo`

- [ ] **Step 1: 创建 `chat_turn.py`**

搬迁原 `AgentChatMixin` 中 `_finish_chat_turn`、`_resolve_rag_route`、`_complete_chat_turn`（约 L112–168）及所需 import。类名：`AgentChatTurnMixin`。

- [ ] **Step 2: 创建 `chat_rag.py`**

搬迁：`flow_run_context`、`maybe_augment_a2a`、`resolve_chat_media_parts`、`direct_chat`、`rag_chat`，以及模块级 `_generative_tools_system_hint`（或从 `chat.py` 导入 hint——**推荐 hint 留在 `chat.py`，`chat_rag` 从 `chat` 导入会循环**）。

**循环规避：** 将 `_generative_tools_system_hint` 放到独立小文件，或放进 `chat_rag.py`（推荐放进 `chat_rag.py`）。

`rag_chat` 内继续：

```python
from app.integrations.langchain.tool_agent import run_tool_calling_chat
```

类名：`AgentChatRagMixin`。

- [ ] **Step 3: 创建 `chat_entry.py`**

搬迁 `chat`、`chat_as_child`（约 L170–357）及所需 import。类名：`AgentChatEntryMixin`。

- [ ] **Step 4: 改写 `chat.py` 为组合门面**

```python
"""智能体对话编排：组合 Turn / Entry / Rag Mixin。"""
from __future__ import annotations

from app.tenant.agents.services.agent.chat_entry import AgentChatEntryMixin
from app.tenant.agents.services.agent.chat_rag import AgentChatRagMixin
from app.tenant.agents.services.agent.chat_turn import AgentChatTurnMixin


class AgentChatMixin(AgentChatEntryMixin, AgentChatRagMixin, AgentChatTurnMixin):
    """对话路由与 RAG；依赖 AgentCrudMixin 的加载与 prompt 解析。"""

    pass
```

若 `_generative_tools_system_hint` 在 `chat_rag.py`，则 `chat.py` 仅组合类。更新模块 docstring；删除已迁走的方法体。

- [ ] **Step 5: 更新 `agent/__init__.py` 目录说明**

在 docstring 中列出 `chat_turn` / `chat_entry` / `chat_rag`；**保持** `__all__` 与现有导出不变。

- [ ] **Step 6: 行数 + pytest**

```bash
cd backend
wc -l app/tenant/agents/services/agent/chat*.py
find app -path '*/tool_agent*' -name '*.py' -o -path '*/services/agent/chat*' -name '*.py' | while read f; do wc -l "$f"; done
python -m pytest tests/tenant/agents tests/tenant/generative/test_generative_image.py tests/tenant/generative/test_generative_video.py -q
```

Expected: 相关 `chat*.py` / `tool_agent/**` 均 &lt;500；测试 PASS。

全量红线自检：

```bash
find app -name '*.py' -exec wc -l {} + | awk '$1 >= 500'
```

Expected: 输出中 **无** `tool_agent.py`（单文件）且 **无** 超标的 `chat.py`；若仍有其它历史超标文件，本任务不强制清零，但 **本 spec 涉及的文件必须清零**。

- [ ] **Step 7: Commit**

```bash
git add backend/app/tenant/agents/services/agent/
git commit -m "$(cat <<'EOF'
refactor(agents): 将 AgentChatMixin 拆为 turn/entry/rag

消除 chat.py 超标，对外仍导出 AgentChatMixin / AgentService。
EOF
)"
```

---

### Task 4: Ruff 与收尾核对

**Files:**
- Modify: 仅当 ruff 要求（import 排序等）

- [ ] **Step 1: Ruff**

```bash
cd backend && ruff format app/integrations/langchain/tool_agent app/tenant/agents/services/agent && ruff check app/integrations/langchain/tool_agent app/tenant/agents/services/agent
```

Expected: 无 error（或仅 auto-fix 后干净）。

- [ ] **Step 2: rg 残留**

```bash
cd backend
rg '_artifacts_from_tool_output|integrations/langchain/tool_agent\.py' app tests || true
```

Expected: 无业务引用旧私有名 / 旧单文件路径。

- [ ] **Step 3: 若有格式改动则 commit**

```bash
git add -u backend/app/integrations/langchain/tool_agent backend/app/tenant/agents/services/agent
git commit -m "$(cat <<'EOF'
chore(agents): 整理 tool_agent/chat 拆分后的 ruff 格式
EOF
)"
```

若无改动则跳过 commit。

---

## Spec coverage（自检）

| Spec 项 | Task |
|---------|------|
| tool_agent/ 子包四模块 + `__init__` | 1–2 |
| 删除旧 tool_agent.py | 2 |
| 公开 artifacts_from_tool_output | 1–2 |
| chat_turn / entry / rag + 薄 chat.py | 3 |
| AgentService 对外不变 | 3（service.py 不改 import） |
| pytest agents + generative | 2–3 |
| 行数 &lt;500 | 2–3 |
| 中文 Conventional Commits | 各 Task commit 步 |

## Placeholder scan

无 TBD /「类似 Task N」占位；搬迁以「原样移动 + 改 import/函数名」为准，禁止重写业务分支。
