# 拆出 `miles-integrations`（第 11 包）设计

> 状态：**已实施**
> 关联：[layering.md](../../architecture/layering.md)、[2026-09-22-miles-ai-internal-layering-design.md](./2026-09-22-miles-ai-internal-layering-design.md)（**已实施**，本设计的严格前置）、[2026-09-11-backend-uv-workspace-multipackage-design.md](./2026-09-11-backend-uv-workspace-multipackage-design.md) §11
> 目标形态：新建 workspace 包 `miles-integrations`，承接原 `miles_ai.integrations`；包级 layers 变为 `portal → miles_ai → miles_integrations → miles_core`；硬切换、不留兼容层。

---

## 1. 背景与动机

`2026-09-11` 的 uv workspace 重构把 `rag/`（L2）与 `integrations/`（L3）合并进 `miles_ai`，并把「拆出 `miles_integration` 第 11 包」列为最高优先级后续项。`2026-09-22` 已完成**前置子集**：把混在 `integrations/` 里的 L2 代码归位到 `rag/` / `flow_runtime/`，并以包内 `ai-internal-layers` 冻结 `flow_runtime → rag → integrations`。

前置完成后的硬事实（2026-09-22，`main`）：

- `integrations → rag / flow_runtime` 反向边 = **0**
- `integrations/` 已是纯 L3（langchain / langgraph(checkpointer) / litellm / deepagents / embeddings / generative / rerank / chat）
- 上层（portal / server / worker）仍大量直连 `miles_ai.integrations`（约 278 条 `from/import`）

此时拆第 11 包不再有环依赖障碍，可以落地依赖隔离与包级边界。

### 为什么现在做

1. **依赖隔离**：litellm / deepagents / sentence-transformers / langgraph-checkpoint-redis 等仅 L3 使用的重依赖可离开 `miles-ai`。
2. **包边界清晰**：L2 与 L3 在 uv workspace 里成为两个 distribution，layers 升到包级，不再只靠包内契约。
3. 内部分层归位已清干净混装，拆包是纯物理迁移动，风险可控。

---

## 2. 目标与非目标

### 目标

1. 新建 `packages/miles-integrations`，Python 包名 `miles_integrations`。
2. 原 `miles_ai/integrations/**` 整树迁入；import 根由 `miles_ai.integrations` 硬改为 `miles_integrations`。
3. 包级 layers 插入 `miles_integrations`（位于 `miles_ai` 与 `miles_core` 之间）。
4. 上层（portal / server / worker）**继续允许**直连 `miles_integrations`（与今日直连 L3 一致）。
5. 行为不变：全量 pytest 用例集合与 OpenAPI 快照零漂移。

### 非目标

- 不留 `miles_ai.integrations` 兼容 re-export / 转发壳。
- 不把 `rag` / `flow_runtime` 再挪包。
- 不重构 tool_agent / deepagents / generative 内部实现。
- 不追求「`miles-ai` 零 langchain」——L2 图引擎与 parse/chunk 仍直接依赖 LC/LG 核心（见 §4）。
- 不收紧「上层禁止直连 L3」策略（若将来要做，单独立项）。

---

## 3. 架构与包边界

### 终态包图

```text
miles_server | miles_worker | miles_runner
miles_openapi | miles_admin
miles_portal
miles_ai                 # 仅 L2：rag/ + flow_runtime/
miles_integrations       # 仅 L3：原 integrations/ 整树
miles_core
miles_exec
miles_common
```

### 物理落点

| 现在 | 之后 |
|------|------|
| `packages/miles-ai/src/miles_ai/integrations/` | `packages/miles-integrations/src/miles_integrations/` |
| `from miles_ai.integrations.X` | `from miles_integrations.X` |
| `tests/miles_ai/integrations/` | `tests/miles_integrations/` |

子目录结构**原样保留**：`chat/`、`deepagents/`、`embeddings/`、`generative/`、`langchain/`、`langgraph/`、`litellm/`、`rerank/`、`http_constants.py`。

### 允许的依赖方向

- `miles_ai` → `miles_integrations` → `miles_core` / `miles_common`
- `miles_portal` / `miles_server` / `miles_worker` 可直连 `miles_integrations`
- **禁止**：`miles_integrations` → `miles_ai` / `miles_portal`

---

## 4. 依赖归属

### 跟 `miles-integrations` 走（仅 L3 用）

| 依赖 | 理由 |
|------|------|
| `litellm` | 仅 adapter / tool_agent |
| `deepagents` | 仅 deepagents 子包 |
| `langgraph-checkpoint-redis` | 仅 checkpointer |
| `sentence-transformers` | 仅 local / CLIP embedding providers |
| `langchain-openai` | 若仅 L3 引用则搬走；实施时以实测为准 |

另：以 integrations 为主要用户的 `httpx` 等 HTTP 客户端依赖归新包（实施时按 import 面核对）。

### 两边都要声明（共享运行时）

| 依赖 | 谁用 |
|------|------|
| `langchain-core` | L2 图/文档 + L3 chat/toolkit |
| `langgraph` | L2 `rag.graph` / `flow_runtime.compiler` + L3 checkpointer / deepagents |

### 留在 `miles-ai`（属 rag/parse）

`langchain-community`、`langchain-text-splitters`、`pypdf`、`docling`、`pytesseract`、`openai-whisper`，以及 L2 解析管线所需的 `Pillow`。

### 上层 pyproject

- `miles-ai`：增加 `miles-integrations` workspace 依赖。
- `miles-portal` / `miles-server` / `miles-worker`：因直连新包，**显式**声明 `miles-integrations`（不只靠传递依赖）。

### 预期效果（诚实版）

- **能瘦**：litellm / deepagents / sentence-transformers / redis-checkpointer 离开 `miles-ai`。
- **不能全瘦**：LC/LG 核心仍挂在 `miles-ai`（L2 需要）。
- 收益在「可选/重型适配隔离」与包边界，而非零-langchain 的 `miles-ai`。

---

## 5. import-linter 契约

### 包级 `layers`

```ini
layers =
    miles_server | miles_worker | miles_runner
    miles_openapi | miles_admin
    miles_portal
    miles_ai
    miles_integrations
    miles_core
    miles_exec
    miles_common
```

`root_packages` 增加 `miles_integrations`。

### 包内 `ai-internal-layers`（收窄）

integrations 已不在 `miles_ai` 内，改为两层：

```ini
layers =
    miles_ai.flow_runtime
    miles_ai.rag
```

仍冻结 `rag ✗→ flow_runtime`。契约名保留 `ai-internal-layers`，注释改为「编排在上、RAG 在下」。

### forbidden 同步

| 契约 | 改动 |
|------|------|
| `no-ai-to-portal` | `source_modules` 增加 `miles_integrations` |
| `core-no-ai` | `forbidden_modules` 增加 `miles_integrations` |
| `runner-minimal` | `forbidden_modules` 增加 `miles_integrations` |

### 红/绿验收

1. **红**：临时在 `miles_integrations` 内 `import miles_ai.rag` → layers BROKEN。
2. **绿**：撤销后全部 KEPT。

---

## 6. 迁移步骤

1. **建包骨架**：`packages/miles-integrations/`（`pyproject.toml` + `src/miles_integrations`），加入 workspace。
2. **`git mv` 整树**：源码与 `tests/miles_ai/integrations/**` → `tests/miles_integrations/**`。
3. **全仓硬改 import**：`miles_ai.integrations` → `miles_integrations`（含 monkeypatch 路径字符串）。
4. **依赖归属**：按 §4 调整各 `pyproject.toml`；`uv sync`。
5. **契约**：改 `.importlinter`；红/绿双向证明。
6. **文档**：同步 `layering.md` 等；本 spec 补「已实施」。
7. **门禁**：`make check`。

### 约束

- 纯搬迁：禁止改逻辑、断言、fixture、函数签名。
- 不留兼容壳。
- 每个 Task 一个简体中文 Conventional Commit。
- 单文件 ≤ 500 行；新增模块须有中文 docstring。

---

## 7. 验收标准

| 项 | 期望 |
|----|------|
| `miles_ai` 目录 | 仅有 `rag/`、`flow_runtime/`（无 `integrations/`） |
| `^\s*(from\|import)\s+miles_ai\.integrations`（packages + tests） | **0** |
| `lint-imports` | 全 KEPT（新层 + 收窄后的 ai-internal-layers + forbidden） |
| `make check` | 全绿；pytest collect-only 用例名快照与搬迁前一致 |
| OpenAPI | 零漂移 |

---

## 8. 风险与回滚

| 风险 | 缓解 |
|------|------|
| 漏改 patch 字符串导致测试静默打错模块 | 实施计划列出全部 monkeypatch 目标；全量 pytest |
| 依赖漏搬 / 错搬导致 import 失败 | §4 以实测 import 面为准；`uv sync` + 冒烟 |
| LC/LG 双边声明被误认为「拆包失败」 | §4 已写明预期；文档同步说明 |

回滚：整支线 revert；无数据迁移、无 schema 变更。

---

## 9. 与前置设计的关系

[2026-09-22-miles-ai-internal-layering-design.md](./2026-09-22-miles-ai-internal-layering-design.md) §9 曾将「拆第 11 包」列为后续项。本设计即该项的完整方案；前置归位是其硬门禁，现已满足。

---

## 10. 修订记录

### 2026-09-22：初稿

协作确认：目标 = 依赖隔离 + 包边界；硬切换；包名 `miles-integrations` / `miles_integrations`；上层可继续直连 L3；方案 = 整包抽出并插入 layers。

### 2026-09-22：已实施

Task 1–3 落地。与本文无偏差。验收：全仓无 `miles_ai.integrations` 生产 import；
`lint-imports` 全绿；pytest collect-only 与基线一致。
