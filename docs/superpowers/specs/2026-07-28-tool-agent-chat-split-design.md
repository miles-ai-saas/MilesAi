# 设计：拆分超标 `tool_agent` / `agent.chat`

**日期：** 2026-07-28  
**状态：** 已批准（对话确认；待实现）  
**约束：** [backend/README.md](../../../backend/README.md) 单文件体量；[layering.md](../../architecture/layering.md) §5.4  
**动机：** `tool_agent.py`（808）与 `agent/chat.py`（571）违反 ≥500 行禁止合入；按职责拆到约 300–400 行/文件。

---

## 1. 目标与非目标

### 目标

1. 将上述两文件拆为子包/多模块，拆后 **无单文件 ≥500 行**。
2. Import 策略选 **B**：允许改路径；测试中对私有符号的深引用改为公开导出。
3. **行为不变**：对话路由、tool calling 循环、artifacts、合规/Hook 包裹逻辑不改语义。
4. 对外主入口稳定：`run_tool_calling_chat`、`AgentService` 仍可从聚合包导入。

### 非目标

- 不实现 LLM 真 token 流式。
- 不改前端、不改 API 契约。
- 不重构 `FlowInspectorNodeForms.tsx` 等前端超标文件（另立项）。
- 不扩大测试覆盖（仅保证现有 agents / generative 相关测通过；必要时改 import）。

---

## 2. 方案选择

| 方案 | 结论 |
|------|------|
| 1. 职责子包（对齐 `tools/invoke/`） | **采用** |
| 2. 同目录平铺 `*_helpers.py` | 拒绝：命名易乱、再胀难管 |
| 3. 按路由切碎大量 Mixin | 拒绝：组合顺序脆弱、回归面大 |

---

## 3. `integrations/langchain/tool_agent/`

### 3.1 目录

```text
backend/app/integrations/langchain/tool_agent/
  __init__.py       # 对外出口
  parse.py          # 伪 tool_call 文本检测与参数解析、UUID 清洗、schema 校验
  artifacts.py      # generate_* 输出 → ChatArtifact
  litellm_tools.py  # StructuredTool → OpenAI tools schema；acompletion 封装
  loop.py           # run_tool_calling_chat 主循环
```

删除同级旧文件 `tool_agent.py`（不可与目录共存）。

### 3.2 模块职责边界

| 模块 | 放入 | 不放入 |
|------|------|--------|
| `parse.py` | `_GENERATIVE_*` 常量、JSON/伪调用解析、`_clean_uuid_params`、`_validate_and_clean` 等 | LiteLLM 调用、invoke |
| `artifacts.py` | `artifacts_from_tool_output`（公开名，原 `_artifacts_from_tool_output`） | 主循环 |
| `litellm_tools.py` | `_tools_to_openai_schema`、`_litellm_with_tools` | 工具 invoke |
| `loop.py` | `run_tool_calling_chat` 及循环内编排 | 解析算法细节（调用 parse） |

模块内私有函数可继续 `_` 前缀；**跨包/测试需要的**经 `__init__.py` 显式导出。

### 3.3 公开 API（`__init__.py`）

```python
# 对外稳定
from app.integrations.langchain.tool_agent.loop import run_tool_calling_chat
from app.integrations.langchain.tool_agent.artifacts import artifacts_from_tool_output

__all__ = ["run_tool_calling_chat", "artifacts_from_tool_output"]
```

调用方：

- 生产：`from app.integrations.langchain.tool_agent import run_tool_calling_chat`（路径字符串不变，由包取代模块）。
- 测试：改为导入 `artifacts_from_tool_output`（去掉对 `_artifacts_from_tool_output` 的依赖）。

### 3.4 体量预估

| 文件 | 约行数 |
|------|--------|
| parse.py | ~220 |
| artifacts.py | ~80 |
| litellm_tools.py | ~40 |
| loop.py | ~350–400 |
| `__init__.py` | &lt;30 |

若 `loop.py` 仍 ≥500，再拆「工具执行一轮 / 确认 pending」为 `loop_invoke.py`，本 spec 允许二次切分。

---

## 4. `tenant/agents/services/agent/` 对话拆分

### 4.1 目录（增量）

```text
backend/app/tenant/agents/services/agent/
  chat.py           # AgentChatMixin = 组合类；_generative_tools_system_hint 可留此或迁 hints
  chat_turn.py      # AgentChatTurnMixin：收尾、route 判定、_complete_chat_turn
  chat_entry.py     # AgentChatEntryMixin：chat / chat_as_child
  chat_rag.py       # AgentChatRagMixin：flow_run_context、maybe_augment_a2a、
                    #   resolve_chat_media_parts、direct_chat、rag_chat
  service.py        # 仍组合 AgentChatMixin（对外不变）
  __init__.py       # 文档更新目录职责；导出不变
```

删除原「单文件承载全部 Mixin 方法」形态；逻辑迁入上列 Mixin 文件。

### 4.2 Mixin 组合顺序

`service.py` / `chat.py` 中组合顺序建议（后者覆盖前者同名方法；当前无冲突）：

```text
AgentChatMixin(AgentChatEntryMixin, AgentChatRagMixin, AgentChatTurnMixin)
```

或与现有 `AgentService(AgentChatMixin, AgentCrudMixin, …)` 保持一致：仅让 `AgentChatMixin` 继承上述三个 Mixin。

**约束：** 不改变 `AgentService` 对外方法集合与签名。

### 4.3 Import

- 生产代码继续：`from app.tenant.agents.services.agent import AgentService`。
- 若测试直接 `from …agent.chat import AgentChatMixin`，保持 `chat.py` 仍导出该名。
- **不**要求调用方改深层路径到 `chat_entry` / `chat_rag`。

### 4.4 体量预估

| 文件 | 约行数 |
|------|--------|
| chat_turn.py | ~100 |
| chat_entry.py | ~220 |
| chat_rag.py | ~220 |
| chat.py | &lt;80（组合 + hint） |

---

## 5. 迁移与兼容

1. 先落地 `tool_agent/` 包并删旧文件，改 generative 测试 import，跑相关 pytest。
2. 再拆 `chat_*` Mixin，更新 `agent/__init__.py` 模块说明，跑 `tests/tenant/agents`。
3. 自检：`cd backend && find app -name '*.py' -exec wc -l {} + | awk '$1 >= 500'` — 不得再出现原两路径。
4. 可选：在 `chat_models.py` / 注释中「tool_agent」表述仍指本包，无需改文案语义。

**禁止：** 在 `integrations` 再套一层仅转发的空壳包；禁止 `tenant` 反向依赖循环。

---

## 6. 验收标准

- [ ] 无 `app/integrations/langchain/tool_agent.py` 单文件；存在 `tool_agent/` 包。
- [ ] `agent/chat.py` &lt;500；新增 `chat_*.py` 均 &lt;500。
- [ ] `pytest`：`tests/tenant/agents`、`tests/tenant/generative`（至少触及 artifacts / chat 的用例）通过。
- [ ] `ruff check` / `ruff format` 通过。
- [ ] Commit message 简体中文 Conventional Commits，例如：`refactor(agents): 拆分 tool_agent 与 chat 超标模块`。

---

## 7. 风险与回滚

| 风险 | 缓解 |
|------|------|
| Mixin MRO 顺序导致属性解析变化 | 保持单一组合类 `AgentChatMixin`；方法名不跨 Mixin 重复 |
| `loop.py` 仍超标 | 允许再拆 invoke 步 |
| 漏改私有 import | rg `_artifacts_from_tool_output` / 旧路径后合入 |

回滚：单 commit 内完成拆分，必要时 `git revert` 该 commit。

---

## 8. 决策记录

- Import 策略：**B**（可改路径，整理测试私有引用）。
- 采用职责子包，对齐 `tenant/tools/invoke/`。
- 公开 `artifacts_from_tool_output`（去下划线）作为测试与潜在复用入口。
