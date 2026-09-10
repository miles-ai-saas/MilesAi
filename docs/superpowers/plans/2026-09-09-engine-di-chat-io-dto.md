# F2a 实施计划：agent 对话 IO DTO 下沉中立域 `models/agent/chat_io`

> **归档：** 已实施并合并（engine DI 收敛，2026-09-10 校核）。**收敛记录：** [layering.md](../../architecture/layering.md) §8；执行明细见 `.superpowers/sdd/progress.md`。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 消除 `integrations/langchain/tool_agent/{loop,artifacts}.py` 对 `tenant.agents.schemas.agent` 的运行期 import——把智能体对话 IO 契约（`ChatMediaIn`/`ChatRequest`/`ChatResponse`/`ChatArtifact`/`PendingToolCall`）下沉中立域 `app/models/agent/chat_io.py`，原 `tenant.agents.schemas.agent` 变 re-export shim（L1 既有 import 路径稳定）。完成标准：`tool_agent/artifacts.py` 对 `tenant` 依赖**清零**，`tool_agent/loop.py` 仅剩 F2c 执行/确认行为面（`tenant.tools.{confirmation,invoke}`）待后续计划。

**Architecture:**

- **下沉目标** `models/agent/chat_io.py`：纯 pydantic DTO 集合，仅依赖 `pydantic`/`uuid`/`app.common.schemas.media.MediaRefIn`；与 `models/agent/constants.py`（B-2d 下沉的枚举）同域同风格。L3 指向本模块（中立域）；L1 经 `tenant.agents.schemas.agent` re-export shim 保持既有 import（与 `tenant.agents.constants` 对 `models.agent.constants` 的 shim 先例一致）。
- **抽取区块**：`backend/app/tenant/agents/schemas/agent.py` L137-242 为连续自包含区块（`class ChatMediaIn` 至 `class ChatResponse` 结束），5 个类互相引用但**不引用**文件内其它类、不引用 `tenant` 其它模块。整段复制。
- **L3 消费点改造**：`tool_agent/loop.py`（`ChatArtifact`/`ChatRequest`/`ChatResponse`/`PendingToolCall`）与 `tool_agent/artifacts.py`（`ChatArtifact`）改从 `app.models.agent.chat_io` import。
- **L1 消费点**：`schemas.agent` 的 shim 让所有 `from app.tenant.agents.schemas.agent import Chat*` 继续工作（含 `chat_entry`、各类 views/ws、`tenant/tools` 对 agent 侧 `PendingToolCall` 的引用等）。**零调用点改动**。

**Tech Stack:** FastAPI / pydantic v2（后端 `backend/`，pytest 回归验证）。

## Global Constraints

- 分层（[`layering.md`](../../architecture/layering.md) §2.2）：完成标准为 `integrations/langchain/tool_agent/{loop,artifacts}.py` 中 `from app.tenant.agents.schemas.agent import ...` 消失（`models.agent` import 合法）；`schemas/agent.py` 保留全部非 Chat 类（`SubAgent*`/`A2a*`/`Agent*`/`AgentPackage`）与既有 import 面。
- **语义零偏移**：5 个类的字段定义、默认值、`description`、validator（`ChatRequest.validate_query_or_media`）、docstring **逐字复制**；不增删字段、不改类型注解。
- shim 保持导出：`schemas/agent.py` 顶部 `from app.models.agent.chat_io import (ChatMediaIn, ChatRequest, ChatResponse, ChatArtifact, PendingToolCall)`；若 `MediaRefIn` 在移除 Chat 区块后无其它用途则删除其 import（防 ruff F401），否则保留。
- 中文 docstring：新模块须有模块 docstring 说明中立域定位与 L1 shim 关系。
- 体量：改动文件 ≤ 500 行。
- 测试：每任务跑定向 pytest + 全量回归（基线 **455 passed**；`uv run` 若弄脏 `backend/uv.lock` 须 `git checkout -- backend/uv.lock`）；收尾不得少于基线。
- 提交：每任务独立 commit，message 简体中文 `<type>(<scope>): <简述>`（scope `engine`）。

---

### Task 1: 建立 `models/agent/chat_io.py` + `schemas/agent.py` re-export shim（机械移动）

**Files:**
- Create: `backend/app/models/agent/chat_io.py`
- Modify: `backend/app/tenant/agents/schemas/agent.py`

**Interfaces:**
- Produces: `app.models.agent.chat_io` 导出 `ChatMediaIn`/`ChatRequest`/`ChatResponse`/`ChatArtifact`/`PendingToolCall`（字段/validator 与下沉前逐字一致）；`schemas/agent.py` 对 5 名 re-export。
- Consumes: `MediaRefIn`（`app.common.schemas.media`，L137 区块 `ChatMediaIn` 的基类）。

- [ ] **Step 1: 先做机械复制验证（确认源块边界）**

Run（backend/ 下）：`sed -n '137,242p' app/tenant/agents/schemas/agent.py`
Expected：`class ChatMediaIn(MediaRefIn):` 起至 `class ChatResponse` 的 `generative_jobs` 字段结束（L242 为类尾）。此即**逐字复制源**。若行号漂移，以「`class ChatMediaIn` 至 `class ChatResponse` 的收尾行」为边界定位。

- [ ] **Step 2: 创建 `models/agent/chat_io.py`**

内容 = 模块 docstring + 复制源区块（逐字，含类 docstring、字段注释、validator、`from __future__ import annotations`）：

```python
"""智能体对话 IO 契约（中立域，L3/tenant 共用）。

``ChatRequest``/``ChatResponse`` 与 ``ChatArtifact``/``PendingToolCall``/``ChatMediaIn``
为对话入口/响应与工具产出物的纯 pydantic 契约，供 L1（``tenant.agents.schemas.agent``
re-export）与 L3 ``integrations/langchain/tool_agent`` 共用。定义自
``tenant/agents/schemas/agent.py`` 下沉（路径稳定，L1 引用不变）；
新代码 L3 应指向本模块，禁止反向依赖 ``tenant``。
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.common.schemas.media import MediaRefIn


class ChatMediaIn(MediaRefIn):
    """智能体对话附图（与 ``MediaRefIn`` 同形）。"""


class ChatRequest(BaseModel):
    """对话入参；``inputs`` 合并进流程画布运行时变量。"""

    ...  # 自源块 L141-191 逐字复制（含 validator）

class PendingToolCall(BaseModel):
    ...  # 自源块 L194-198 逐字复制

class ChatArtifact(BaseModel):
    ...  # 自源块 L201-219 逐字复制

class ChatResponse(BaseModel):
    ...  # 自源块 L222-242 逐字复制
```

实现要求：
- 上述 `...` 处为省略记号，实际实现须以 Step 1 复制的源块**完整字段逐字落地**（不得精简字段/注释/默认值/validator 的语义）。
- `model_validator` 返回注解 `-> "ChatRequest"` 原文保留（`from __future__ import annotations` 下合法）。

- [ ] **Step 3: `schemas/agent.py` 转 shim**

- 删除 L137-242 Chat 区块（`ChatMediaIn`/`ChatRequest`/`PendingToolCall`/`ChatArtifact`/`ChatResponse` 定义）。
- 文件顶部（既有 import 区之后、`AgentStatus`/`AgentType` import 附近）追加：

```python
from app.models.agent.chat_io import (
    ChatArtifact,
    ChatMediaIn,
    ChatRequest,
    ChatResponse,
    PendingToolCall,
)
```

- 若此时 `from app.common.schemas.media import MediaRefIn` 不再被文件内任何定义引用（原唯一使用者为 `ChatMediaIn`），删除该 import；否则保留。
- 模块 docstring 追加一句：对话 IO 契约（Chat* 五类）定义已下沉 ``app.models.agent.chat_io``，本处 re-export 保持 L1 import 路径。

- [ ] **Step 4: 指向核对 + 回归**

Run（backend/ 下）：
```bash
rg -n "class (ChatMediaIn|ChatRequest|ChatResponse|ChatArtifact|PendingToolCall)\b" app/tenant/agents/schemas/agent.py || echo "schemas/agent.py 不再定义 Chat*（仅 re-export）"
rg -n "from app\.models\.agent\.chat_io import" app/tenant/agents/schemas/agent.py
uv run ruff check app/models/agent/chat_io.py app/tenant/agents/schemas/agent.py
uv run python -m pytest -q | tail -1
```
Expected：定义区已删、shim import 在、ruff 全绿、pytest ≥ 455（无行为变化，纯移动）。

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/agent/chat_io.py backend/app/tenant/agents/schemas/agent.py
git commit -m "refactor(engine): 对话 IO DTO 下沉 models/agent/chat_io 中立域

ChatRequest/ChatResponse/ChatArtifact/PendingToolCall/ChatMediaIn 纯契约
移至 models 域，schemas.agent 转 re-export shim（L1 路径稳定）。"
```

---

### Task 2: L3 `tool_agent` 消费点改指 `models.agent.chat_io`

**Files:**
- Modify: `backend/app/integrations/langchain/tool_agent/loop.py`
- Modify: `backend/app/integrations/langchain/tool_agent/artifacts.py`

**Interfaces:**
- Consumes: Task 1 `app.models.agent.chat_io` 五导出。
- Produces: 收敛终态——两文件对 `app.tenant.agents.schemas.agent` import 清零。

- [ ] **Step 1: 修改两文件 import**

- `loop.py` 现 L29-32 区块：
  ```python
  from app.tenant.agents.schemas.agent import (
      ChatArtifact,
      ChatRequest,
      ChatResponse,
      PendingToolCall,
  )
  ```
  改为：
  ```python
  from app.models.agent.chat_io import (
      ChatArtifact,
      ChatRequest,
      ChatResponse,
      PendingToolCall,
  )
  ```
- `artifacts.py` 现 L7：`from app.tenant.agents.schemas.agent import ChatArtifact`
  改为 `from app.models.agent.chat_io import ChatArtifact`。
- 模块 docstring 如提及 import 源（若无则不），保持简洁即可。

- [ ] **Step 2: 验证 + 回归**

Run（backend/ 下）：
```bash
rg -n "from app\.tenant\.agents\.schemas\.agent|import app\.tenant\.agents\.schemas\.agent" app/integrations/langchain/tool_agent || echo "tool_agent 对 tenant.agents.schemas.agent 引用清零"
rg -n "from app\.tenant\.agents" app/integrations/langchain/tool_agent/artifacts.py || echo "artifacts.py 对 tenant 引用清零"
uv run ruff check app/integrations/langchain/tool_agent/loop.py app/integrations/langchain/tool_agent/artifacts.py
uv run python -m pytest tests/tenant/agents tests/integrations tests/flow -q 2>/dev/null | tail -1 || uv run python -m pytest -q | tail -1
```
Expected：两条 rg 无命中；ruff 全绿；定向/全量 ≥ 455 passed。

- [ ] **Step 3: Commit**

```bash
git add backend/app/integrations/langchain/tool_agent/loop.py backend/app/integrations/langchain/tool_agent/artifacts.py
git commit -m "refactor(engine): tool_agent loop/artifacts 对话 DTO 改指中立 chat_io

L3 不再 import tenant.agents.schemas.agent；artifacts.py 对 tenant 依赖清零。"
```

---

### Task 3: 回归审计与 `layering.md` 收敛记录

**Files:**
- Modify: `docs/architecture/layering.md`

- [ ] **Step 1: 全量回归 + 定向 rg 终审**

Run（backend/ 下）：
```bash
rg -n "from app\.tenant\.agents\.schemas\.agent" app/integrations || echo "integrations 对 tenant.agents.schemas.agent 引用清零"
uv run ruff check app/integrations/langchain/tool_agent app/models/agent/chat_io.py app/tenant/agents/schemas/agent.py
uv run python -m pytest -q | tail -1
```
Expected：ruff 全绿；rg 无命中；pytest ≥ 455 passed。

- [ ] **Step 2: 更新收敛记录**

`docs/architecture/layering.md`：
- 在 L109（B-2e 收敛记录）之后追加：

```markdown
> **收敛记录（2026-09-09，F2a）**：agent 对话 IO DTO 下沉中立域——`ChatMediaIn`/`ChatRequest`/`ChatResponse`/`ChatArtifact`/`PendingToolCall` 落 `models/agent/chat_io.py`（纯 pydantic，依赖仅 pydantic/uuid/`common.schemas.media`），`tenant/agents/schemas/agent.py` 转 re-export shim（L1 路径稳定）；`integrations/langchain/tool_agent/{loop,artifacts}` 改指 `models.agent.chat_io`，`artifacts.py` 对 `tenant` 依赖清零（见 plan [`2026-09-09-engine-di-chat-io-dto`](../plans/2026-09-09-engine-di-chat-io-dto.md)）。`tool_agent/loop.py` 剩余 `tenant.tools.{confirmation,invoke}` 执行/确认行为面待 tools 契约计划（F2c）。
```

- §8 修订记录表追加一行：

```markdown
| 2026-09-09 | F2a：agent 对话 IO DTO 下沉 `models/agent/chat_io`，schemas 转 shim；tool_agent loop/artifacts 改指中立模块，artifacts 对 tenant 引用清零 |
```

- [ ] **Step 3: Commit**

```bash
git add docs/architecture/layering.md
git commit -m "docs(architecture): 记录 F2a 对话 IO DTO 下沉"
```

---

## Self-Review

- **Spec coverage**：目标（`tool_agent/{loop,artifacts}.py` 对 `schemas.agent` import 清零）由 Task 1（中立模块 + shim）+ Task 2（L3 改指）达成；Task 3 文档闭环。`schemas.agent` 非 Chat 类与 `AgentPackage` 不受影响；L1 全部 import 点经 shim 零改动。
- **语义零偏移**：Task 1 明确「逐字复制」且 Step 4 回归 ≥455 证明无行为变化；校验器/字段/默认值保留。
- **抽取边界**：`ChatMediaIn` 一并下沉是 `ChatRequest.media` 类型依赖所需；该区块（L137-242）文件内自包含，不引用 `SubAgent*`/`Agent*`/`A2a*`。
- **shim 先例一致**：与 B-2d `tenant.agents.constants` → `models.agent.constants` 完全同构。
- **Placeholder scan**：`chat_io.py` 内 `...` 为对实现者的「整段复制」记号，Task 1 Step 1-2 给出精确复制源（sed 行 + 类名边界）；无 TBD。schemas/agent.py 的 MediaRefIn import 保留与否以实际用途为准（显式指令）。
