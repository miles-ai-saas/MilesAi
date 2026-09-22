# miles_ai 内部分层归位 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `miles_ai` 包内错放在 `integrations/`（L3）的编排代码归位到 `rag/`（L2）与 `flow_runtime/`（L2），并用一条 `import-linter` 的 `layers` 契约把 `flow_runtime → rag → integrations` 方向永久冻结。

**Architecture:** 纯搬迁 + 引用改写，不改任何逻辑。`integrations/` 收敛为不含任何 `rag` / `flow_runtime` 引用的纯适配层；Agent RAG 图引擎进 `rag/graph/`，画布流程引擎进 `flow_runtime/`。测试目录按既有镜像规则跟随源码归位。

**Tech Stack:** Python 3.11、uv workspace（10 包）、import-linter、pytest（`asyncio_mode = "auto"`）、ruff。

**设计依据：** [docs/superpowers/specs/2026-09-22-miles-ai-internal-layering-design.md](../specs/2026-09-22-miles-ai-internal-layering-design.md)

---

## Global Constraints

- 所有命令在 `/Users/xiezhigang/Projects/miles/MilesAI/backend` 下执行。
- 测试一律用 `.venv/bin/python -m pytest`：`tests.paths` / `tests.conftest` 依赖 `backend/` 在 `sys.path`。
- 基线（2026-09-22，main `3de8a44d`）：`1517 tests collected`；`lint-imports` = **7 kept, 0 broken**。
- **纯搬迁：禁止改逻辑、断言、fixture、函数签名。** 唯一的代码改写是 import 语句、模块 docstring 里的路径提及，以及本计划明确列举的例外：Task 4 与 Task 5 的两处「文件内手术」（拆分 `checkpointer.py`、拆除 `visual_embeddings.py`）和四处新增模块（`rag/graph/__init__.py`、`rag/graph/compiled.py`、`rag/pipeline/visual_policy.py`、`integrations/embeddings/policy.py`）。除此外不得增删任何函数或分支。
- `git mv` 保留 rename 历史；每个 Task 一个提交，message 用简体中文 Conventional Commits（`refactor(ai): …`）。
- **import 顺序**：`ruff` 已启用 `I`（isort），`select = ["E", "F", "I", "B", "UP", "RUF"]`。每个 Task 改完 import 后先跑 `.venv/bin/ruff check --select I --fix .` 自动排序，再跑 `.venv/bin/ruff format .`；不要手工猜顺序。本计划给出的 import 块已按 isort 排好，若与 `--fix` 结果冲突以 `--fix` 为准。
- 每个 Task 结束必须全绿：`.venv/bin/ruff check .`、`.venv/bin/ruff format --check .`、`.venv/bin/lint-imports`、`.venv/bin/python -m pytest -q`、`.venv/bin/python -m miles_server.scripts.export_openapi --check`。
- 单文件 ≤ 500 行（`backend/packages/*/src/`）；新增模块须有中文 docstring（模块 / 类 / 函数）。
- 搬迁后 `miles_ai.integrations.{generative,embeddings,rerank,deepagents,litellm,chat}` 与 `integrations/langchain/{chat_models,tool_agent,toolkit}` 的路径**不得变化**。
- 新增文件/目录的路径名严格按本计划给出的字面量，不得自创。

### 本计划对 spec 的两处收紧修正

1. **`integrations/langchain/__init__.py` 不删除，改为剥离跨层 re-export。** spec §4.5 写「删除」；实测 `tests/test_no_unreferenced_modules.py:182` 对包 `__init__` 不参与零引用判定，但删除 `__init__.py` 会让该目录退化为 namespace package，且与 `integrations/{chat,litellm,embeddings,rerank,deepagents}/__init__.py` 都做 re-export 的既有约定不一致。改为只 re-export 本子包的 `chat_models`。
2. **`should_use_visual_image_embedding` 落在 `rag/pipeline/visual_policy.py`，不是 spec 写的 `rag/parse/upload_policy.py`。** 该函数是「入库时是否走 CLIP 视觉向量化」的决策（唯一消费者是 `rag/pipeline/ingest.py`，且依赖 `miles_core.models.kb` ORM），放 `parse/upload_policy.py`（上传白名单，与 `parse.loaders` 解析能力对齐）语义不符。

### 实施前必读的现状事实（已实测，勿再重复调研）

- 反向边 **13 文件 / 21 条 import**，全在 `integrations/langchain/`（4 文件）与 `integrations/langgraph/`（9 文件）。
- `integrations/langchain/__init__.py` 惰性门面**全仓零消费者**；`integrations/langchain/vectorstores.py` 的同步版 `search_kb` **零调用**。
- `tests/miles_ai/flow_runtime/test_flow_runtime_constants.py:9` 用了裸门面写法 `from miles_ai.integrations.langgraph import constants as lg_constants`；`integrations/langgraph/__init__.py` 的 `__getattr__` 会被这条触发。
- `compile_rag_graph_for_tests()`（`integrations/langgraph/runner.py:141`）是既有死函数（零调用）。**本次保持原样搬迁，不清理**（清理属独立立项）。
- `integrations/langgraph/checkpointer.py` 被 `integrations/deepagents/runner.py`、`miles_server/apps/application.py`、`rag/graph/runner.py` 三处消费。

---

### Task 0: 记录实施基线

**Files:**
- 无改动（只产出 `/tmp` 下的快照）

**Interfaces:**
- Produces: `/tmp/ai-names-before.txt`（用例名集合，Task 7 收尾时比对）、`/tmp/ai-graph-before.txt`（反向边基线）

- [ ] **Step 1: 记录用例名集合（只留 `::` 之后的部分，与文件位置无关）**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
.venv/bin/python -m pytest -q --collect-only 2>/dev/null | grep '::' | sed -E 's/^[^:]+:://' | sort > /tmp/ai-names-before.txt
wc -l /tmp/ai-names-before.txt
```

Expected: `1517 /tmp/ai-names-before.txt`

- [ ] **Step 2: 记录反向边基线与工作区状态**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
rg -n "^\s*(from|import)\s+miles_ai\.(rag|flow_runtime)" \
  packages/miles-ai/src/miles_ai/integrations > /tmp/ai-graph-before.txt
wc -l /tmp/ai-graph-before.txt
git status --porcelain
```

Expected: `21 /tmp/ai-graph-before.txt`；`git status --porcelain` 输出为空。

---

### Task 1: ② 画布流程引擎迁入 `flow_runtime`

把 `compiler/`（6 文件）、`flow_runner.py`、`graph_analysis.py` 搬到 `flow_runtime/`，并改写全部引用。搬完后 `compiler/*` 内的 `flow_runtime.*` 引用变成包内引用，`integrations → flow_runtime` 的 **13 条边全部消失**（剩余 8 条反向边全部指向 `rag`，属 Task 2/3/5）。

**Files:**
- Move: `packages/miles-ai/src/miles_ai/integrations/langgraph/compiler/` → `packages/miles-ai/src/miles_ai/flow_runtime/compiler/`（`__init__.py`, `report.py`, `validate.py`, `state.py`, `build.py`, `run.py`）
- Move: `packages/miles-ai/src/miles_ai/integrations/langgraph/flow_runner.py` → `packages/miles-ai/src/miles_ai/flow_runtime/graph_runner.py`
- Move: `packages/miles-ai/src/miles_ai/integrations/langgraph/graph_analysis.py` → `packages/miles-ai/src/miles_ai/flow_runtime/graph_analysis.py`
- Modify: `packages/miles-ai/src/miles_ai/flow_runtime/runtime_factory.py`
- Modify: `packages/miles-portal/src/miles_portal/tenant/flows/services/flow.py:21,339`
- Modify: `packages/miles-ai/src/miles_ai/integrations/langgraph/__init__.py`（docstring 里的子模块清单）
- Test: 12 个文件仅改 import（Task 6 再搬目录）

**Interfaces:**
- Produces: `miles_ai.flow_runtime.compiler`（barrel 导出 `build_canvas_graph` / `can_compile_flow_graph` / `run_compiled_canvas` / `validate_graph_for_compile` / `FlowCompileReport` / `SUPPORTED_CANVAS_NODE_TYPES` / `resolve_node_type` / `_error_to_str`）、`miles_ai.flow_runtime.graph_runner.run_flow_graph(graph_json: dict, ctx: RunContext) -> RunResult`、`miles_ai.flow_runtime.graph_analysis`（含 `GRADE_BRANCH_HANDLES`、`compute_execution_layers`、`build_incoming`、`build_outgoing`、`find_start_nodes`、`find_end_nodes`、`normalize_grade_handle`、`normalize_branch_handle`、`has_cycle`、`topo_order`、`dangling_edge_endpoints`）

- [ ] **Step 1: 用 `git mv` 搬迁三个路径**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
git mv packages/miles-ai/src/miles_ai/integrations/langgraph/compiler \
       packages/miles-ai/src/miles_ai/flow_runtime/compiler
git mv packages/miles-ai/src/miles_ai/integrations/langgraph/flow_runner.py \
       packages/miles-ai/src/miles_ai/flow_runtime/graph_runner.py
git mv packages/miles-ai/src/miles_ai/integrations/langgraph/graph_analysis.py \
       packages/miles-ai/src/miles_ai/flow_runtime/graph_analysis.py
git status --porcelain
```

Expected: 输出均为 `R  ` 前缀的重命名行，无 `A`/`D`。

- [ ] **Step 2: 改写 `flow_runtime/compiler/__init__.py` 的 4 条自引用 import**

`packages/miles-ai/src/miles_ai/flow_runtime/compiler/__init__.py`，把导入块整体替换为：

```python
from miles_ai.flow_runtime.compiler.build import build_canvas_graph
from miles_ai.flow_runtime.compiler.report import (
    SUPPORTED_CANVAS_NODE_TYPES,
    FlowCompileReport,
    _error_to_str,
    resolve_node_type,
)
from miles_ai.flow_runtime.compiler.run import run_compiled_canvas
from miles_ai.flow_runtime.compiler.validate import can_compile_flow_graph, validate_graph_for_compile
```

同时把模块 docstring 里的 `from miles_ai.integrations.langgraph.compiler import build_canvas_graph, validate_graph_for_compile` 改为：

```
    from miles_ai.flow_runtime.compiler import build_canvas_graph, validate_graph_for_compile
```

`__all__` 列表保持逐字不变。

- [ ] **Step 3: 改写 `flow_runtime/compiler/state.py` 的 import 块**

`packages/miles-ai/src/miles_ai/flow_runtime/compiler/state.py`，把第 2-10 行的 import 块整体替换为（isort 序：`compiler.*` < `constants` < `graph_analysis` < `types` < `integrations.*`）：

```python
import operator
from typing import Annotated, Any, TypedDict

from miles_ai.flow_runtime.compiler.report import resolve_node_type
from miles_ai.flow_runtime.constants import TEXT_OUTPUT_NODE_TYPES
from miles_ai.flow_runtime.graph_analysis import GRADE_BRANCH_HANDLES
from miles_ai.flow_runtime.types import FlowGraph
from miles_ai.integrations.langgraph.constants import RELEVANCE_NONE
```

> `miles_ai.integrations.langgraph.constants` 本次**不动**（属 ③ 桶，Task 2 才迁）。

- [ ] **Step 4: 改写 `flow_runtime/compiler/build.py` 的 import 块**

`packages/miles-ai/src/miles_ai/flow_runtime/compiler/build.py`，把第 6-23 行的 import 块整体替换为：

```python
from dataclasses import replace
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from miles_ai.flow_runtime.compiler.report import resolve_node_type
from miles_ai.flow_runtime.compiler.state import (
    CanvasGraphState,
    gather_node_inputs,
    make_relevance_grade_router,
)
from miles_ai.flow_runtime.compiler.validate import validate_graph_for_compile
from miles_ai.flow_runtime.constants import CanvasNodeType
from miles_ai.flow_runtime.graph_analysis import (
    GRADE_BRANCH_HANDLES,
    build_incoming,
    build_outgoing,
    find_end_nodes,
    find_start_nodes,
    normalize_grade_handle,
)
from miles_ai.flow_runtime.nodes.registry import execute_node
from miles_ai.flow_runtime.step_record import build_flow_node_step
from miles_ai.flow_runtime.types import FlowGraph, RunContext
```

> 关键点：`compiler.*` 必须排在 `constants` 之前（`"compiler."` < `"constants"`），`graph_analysis` 排在 `nodes.registry` 之前。`from __future__ import annotations` 行仍留在原位置（docstring 之后、`from dataclasses` 之前）。

- [ ] **Step 5: 改写 `flow_runtime/compiler/validate.py` 的 import 块**

`packages/miles-ai/src/miles_ai/flow_runtime/compiler/validate.py`，把第 3-22 行的 import 块整体替换为：

```python
from typing import Any

from miles_ai.flow_runtime.compiler.report import (
    SUPPORTED_CANVAS_NODE_TYPES,
    FlowCompileReport,
    _compile_error,
    _error_to_str,
    resolve_node_type,
)
from miles_ai.flow_runtime.constants import CanvasNodeType
from miles_ai.flow_runtime.graph_analysis import (
    GRADE_BRANCH_HANDLES,
    build_outgoing,
    compute_execution_layers,
    dangling_edge_endpoints,
    find_start_nodes,
    has_cycle,
    normalize_branch_handle,
    normalize_grade_handle,
    topo_order,
)
from miles_ai.flow_runtime.types import FlowGraph
```

- [ ] **Step 6: 改写 `flow_runtime/compiler/run.py` 的 import 块**

`packages/miles-ai/src/miles_ai/flow_runtime/compiler/run.py`，把第 3-8 行的 import 块整体替换为：

```python
from typing import Any

from miles_ai.flow_runtime.compiler.build import build_canvas_graph
from miles_ai.flow_runtime.compiler.state import resolve_final_output
from miles_ai.flow_runtime.compiler.validate import validate_graph_for_compile
from miles_ai.flow_runtime.types import FlowGraph, RunContext
```

> `flow_runtime.types` 必须落在 3 条 `compiler.*` **之后**（`"compiler."` < `"types"`），不可原地只替换那 3 行。

`compiler/report.py` **无需改动**（它只 import `flow_runtime.nodes.registry`）。

- [ ] **Step 7: 改写 `flow_runtime/graph_runner.py` 与新 `graph_analysis.py`**

`packages/miles-ai/src/miles_ai/flow_runtime/graph_runner.py` 把第 15-17 行的 import 块整体替换为：

```python
from miles_ai.flow_runtime.compiler import run_compiled_canvas, validate_graph_for_compile
from miles_ai.flow_runtime.types import RunContext, RunResult
from miles_common.exceptions import BadRequestError
```

`packages/miles-ai/src/miles_ai/flow_runtime/graph_analysis.py` docstring 第 4 行：

```
供 ``flow_runtime.compiler`` 在编译前校验拓扑：
```

- [ ] **Step 8: 改写 `flow_runtime/runtime_factory.py`**

`packages/miles-ai/src/miles_ai/flow_runtime/runtime_factory.py` 全文替换为（逻辑逐字不变，只改 docstring 与 import 路径）：

```python
"""
流程执行门面（L2）。

``LangGraphFlowRuntime.run`` 委托 ``flow_runtime.graph_runner.run_flow_graph``，
编译与节点分发见 ``flow_runtime.compiler`` + ``flow_runtime.nodes.registry``。

典型调用方：智能体 ``published_flow_id`` 对话、流程调试 API。
"""

from functools import lru_cache

from miles_ai.flow_runtime.graph_runner import run_flow_graph
from miles_ai.flow_runtime.types import RunContext, RunResult


class LangGraphFlowRuntime:
    """流程运行时门面，委托 flow_runtime.graph_runner。"""

    async def run(self, graph: dict, ctx: RunContext) -> RunResult:
        """执行 React Flow 导出的 graph_json。"""
        return await run_flow_graph(graph, ctx)


@lru_cache
def get_flow_runtime() -> LangGraphFlowRuntime:
    """进程内单例 FlowRuntime（Agent 发布流程对话用）。"""
    return LangGraphFlowRuntime()
```

- [ ] **Step 9: 改写 `miles_portal` 的 2 处引用**

`packages/miles-portal/src/miles_portal/tenant/flows/services/flow.py`：

- 第 21 行 → `from miles_ai.flow_runtime.compiler import validate_graph_for_compile`
- 第 339 行 → `from miles_ai.flow_runtime.compiler import FlowCompileReport, _error_to_str`

- [ ] **Step 10: 更新 `integrations/langgraph/__init__.py` 的 docstring**

`packages/miles-ai/src/miles_ai/integrations/langgraph/__init__.py` 的 docstring 子模块清单中，删除 `compiler` / `flow_runner` 两行，改为：

```
子模块
------
- ``runner``：Agent RAG 图执行（``run_rag_workflow``）
- ``graphs.rag_qa``：检索→评分→生成/重试/兜底
- ``checkpointer``：Redis/内存多轮状态

画布 ``graph_json`` 编译与运行见 ``miles_ai.flow_runtime.{compiler,graph_runner,graph_analysis}``。
```

本文件其余内容（`__all__` 与 `__getattr__`）**不改**（`runner` 仍在 `integrations/langgraph/`，Task 2 才迁）。

- [ ] **Step 11: 改写 12 个测试文件的 import（目录留到 Task 6 再搬）**

按下表逐条替换。左列出现几次就替换几次（`test_langgraph_parallel.py` 有 2 条）：

| 文件:行 | 原文 | 改为 |
|---|---|---|
| `tests/integration/test_integration_pipeline.py:11` | `from miles_ai.integrations.langgraph.compiler import run_compiled_canvas, validate_graph_for_compile` | `from miles_ai.flow_runtime.compiler import run_compiled_canvas, validate_graph_for_compile` |
| `tests/integration/test_module_smoke.py:3` | `from miles_ai.integrations.langgraph.compiler import (` | `from miles_ai.flow_runtime.compiler import (` |
| `tests/miles_ai/flow_runtime/test_flow_multimodal.py:12` | `from miles_ai.integrations.langgraph.compiler import run_compiled_canvas` | `from miles_ai.flow_runtime.compiler import run_compiled_canvas` |
| `tests/miles_ai/flow_runtime/test_flow_template_graphs.py:6` | `from miles_ai.integrations.langgraph.compiler import validate_graph_for_compile` | `from miles_ai.flow_runtime.compiler import validate_graph_for_compile` |
| `tests/miles_ai/flow_runtime/test_flow_templates.py:12` | `from miles_ai.integrations.langgraph.compiler import validate_graph_for_compile` | `from miles_ai.flow_runtime.compiler import validate_graph_for_compile` |
| `tests/miles_ai/flow_runtime/test_relevance_grade_flow.py:10` | `from miles_ai.integrations.langgraph.compiler import validate_graph_for_compile` | `from miles_ai.flow_runtime.compiler import validate_graph_for_compile` |
| `tests/miles_ai/flow_runtime/test_subflow.py:8` | `from miles_ai.integrations.langgraph.compiler import validate_graph_for_compile` | `from miles_ai.flow_runtime.compiler import validate_graph_for_compile` |
| `tests/miles_ai/integrations/langgraph/test_canvas_state_contract.py:17` | `from miles_ai.integrations.langgraph.compiler.state import CanvasGraphState` | `from miles_ai.flow_runtime.compiler.state import CanvasGraphState` |
| `tests/miles_ai/integrations/langgraph/test_compile_error_details.py:3` | `from miles_ai.integrations.langgraph.compiler import validate_graph_for_compile` | `from miles_ai.flow_runtime.compiler import validate_graph_for_compile` |
| `tests/miles_ai/integrations/langgraph/test_langgraph_build.py:14` | `from miles_ai.integrations.langgraph.compiler.build import (` | `from miles_ai.flow_runtime.compiler.build import (` |
| `tests/miles_ai/integrations/langgraph/test_langgraph_compiler.py:7` | `from miles_ai.integrations.langgraph.compiler import can_compile_flow_graph, validate_graph_for_compile` | `from miles_ai.flow_runtime.compiler import can_compile_flow_graph, validate_graph_for_compile` |
| `tests/miles_ai/integrations/langgraph/test_langgraph_parallel.py:4` | `from miles_ai.integrations.langgraph.compiler import validate_graph_for_compile` | `from miles_ai.flow_runtime.compiler import validate_graph_for_compile` |
| `tests/miles_ai/integrations/langgraph/test_langgraph_parallel.py:5` | `from miles_ai.integrations.langgraph.graph_analysis import compute_execution_layers` | `from miles_ai.flow_runtime.graph_analysis import compute_execution_layers` |

> `tests/miles_ai/flow_runtime/test_relevance_grade_flow.py` 用 `monkeypatch.setattr(grade_nodes_module, "evaluate_relevance", fake_evaluate)`，本条不改（`grade_nodes` 的 import 属 ③ 桶，Task 2 处理）；monkeypatch 打的是模块属性，搬迁不影响。

**另有 1 处非 import 的路径引用必须一并改** —— `tests/miles_ai/integrations/langgraph/test_canvas_state_contract.py` 是**源码扫描型守卫**（它 AST 解析 `compiler/*.py` 与 `compiler/run.py` 来锁死 `CanvasGraphState` 通道契约），第 22-23 行用字面量拼出编译器目录：

```python
_BACKEND_DIR = BACKEND_ROOT
_COMPILER_DIR = _BACKEND_DIR / "packages" / "miles-ai" / "src" / "miles_ai" / "integrations" / "langgraph" / "compiler"
```

改为（复用 `tests.paths.MILES_AI`，与仓内其余源码扫描守卫同风格；同时删掉 `_BACKEND_DIR` 与不再需要的 `BACKEND_ROOT` import，改为 import `MILES_AI`）：

```python
_COMPILER_DIR = MILES_AI / "flow_runtime" / "compiler"
```

并把该常量上方注释里的「已搬到 tests/miles_ai/integrations/langgraph/」改为「已搬到 tests/miles_ai/flow_runtime/（Task 6）」。三个用例的断言**逐字不变**（`_COMPILER_DIR.glob("*.py")` 的文件集合在搬迁前后都是 `__init__/build/report/run/state/validate`）。

> 全仓同类「路径字面量」引用已实测只有这 1 处（`rg -n '"(integrations|langchain|langgraph|compiler|flow_runner|kb_retrieval|vectorstores|visual_embeddings|grading|graphs|constants|runner|state)"\s*/' packages tests --glob '*.py'` 仅命中本行），其余 `MILES_AI / ...` 用法都指向未搬迁的 `flow_runtime/templates/*.json`。

- [ ] **Step 12: 验证**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
rg -n "integrations\.langgraph\.(compiler|flow_runner|graph_analysis)" packages tests; echo "--- 期望：无输出"
echo "=== 反向边剩余（锚定口径，与 Task 0 基线同定义）==="
rg -n "^\s*(from|import)\s+miles_ai\.(rag|flow_runtime)" packages/miles-ai/src/miles_ai/integrations -g '*.py' | wc -l
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/import-linter 2>/dev/null || .venv/bin/lint-imports | tail -3
.venv/bin/python -m pytest -q tests/miles_ai/flow_runtime tests/integration tests/miles_ai/integrations
```

Expected: 第一条无输出；**反向边剩余 `8`**（基线 21 条 = 13 条 `miles_ai.flow_runtime.*`〔全部落在本次搬迁的 `compiler/*`、`graph_analysis.py`、`flow_runner.py` 内〕+ 8 条 `miles_ai.rag.*`〔属 ③ 桶，Task 2/3/5 处理〕，本次消掉全部 13 条）；lint-imports 全绿；pytest 全 passed。

> 不要用 `rg -c "miles_ai\.(rag|flow_runtime)"` 这种**未锚定**写法来数反向边：它会把 docstring 里的路径提及也算进去（本次 Step 10 写入的 `integrations/langgraph/__init__.py` docstring 就会 +1，得 9），与基线的 `^\s*(from|import)` 口径不一致。收尾验收与 Task 0 基线都用锚定口径。

- [ ] **Step 13: 全量验证并提交**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
.venv/bin/python -m pytest -q
```

Expected: `1517 passed`（用例集合不变）。

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI
git add -A
git commit -F- <<'EOF'
refactor(ai): 画布流程引擎由 integrations 归位到 flow_runtime

integrations/langgraph 按技术名建包，把用 LangGraph 写的画布流程编译器
也塞进了 L3 适配层，使 integrations 反向依赖 flow_runtime 达 13 条。
compiler、graph_runner、graph_analysis 迁入 flow_runtime 后，这 13 条全部
成为包内引用；剩余 8 条反向边全部指向 rag，属暂未归位的 Agent RAG 图引擎。

纯搬迁，不改逻辑；对外 import 路径仅 flow_runtime 与 portal flows 服务受影响。
EOF
git log --oneline -1
```

---

### Task 2: ③ Agent RAG 图引擎迁入 `rag/graph/`

把 `constants` / `state` / `grading` / `runner` / `graphs.rag_qa` 五个模块搬进新的 `rag/graph/` 子包，并新建惰性 barrel。

**Files:**
- Create: `packages/miles-ai/src/miles_ai/rag/graph/__init__.py`
- Move: `integrations/langgraph/constants.py` → `rag/graph/constants.py`
- Move: `integrations/langgraph/state.py` → `rag/graph/state.py`
- Move: `integrations/langgraph/grading.py` → `rag/graph/grading.py`
- Move: `integrations/langgraph/runner.py` → `rag/graph/runner.py`
- Move: `integrations/langgraph/graphs/rag_qa.py` → `rag/graph/rag_qa.py`（然后删掉空目录 `graphs/`）
- Modify: `packages/miles-ai/src/miles_ai/integrations/langgraph/__init__.py`
- Modify: `packages/miles-ai/src/miles_ai/flow_runtime/nodes/grade_nodes.py`
- Modify: `packages/miles-ai/src/miles_ai/flow_runtime/graph_analysis.py`
- Modify: `packages/miles-ai/src/miles_ai/flow_runtime/compiler/state.py`
- Modify: `packages/miles-ai/src/miles_ai/rag/generate/__init__.py`（docstring）
- Modify: `packages/miles-portal/src/miles_portal/tenant/agents/services/{architecture.py,agent/chat_rag.py,agent/chat_turn.py}`

**Interfaces:**
- Consumes: Task 1 产出的 `miles_ai.flow_runtime.{compiler,graph_analysis,graph_runner}`
- Produces: `miles_ai.rag.graph`（惰性 barrel，导出 `build_rag_qa_graph`、`run_rag_workflow`、`should_use_langgraph_rag`、`build_rag_thread_id`、`evaluate_relevance`、`llm_grade_relevance`、`_score_grade`、`parse_llm_grade_response`、`RELEVANCE_GOOD`、`RELEVANCE_POOR`、`RELEVANCE_NONE`、`GRADE_BRANCH_HANDLES`、`RAGGraphState`）；`miles_ai.rag.graph.constants`、`miles_ai.rag.graph.grading`、`miles_ai.rag.graph.rag_qa`、`miles_ai.rag.graph.runner`

- [ ] **Step 1: 建目录并 `git mv` 五个文件**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
mkdir -p packages/miles-ai/src/miles_ai/rag/graph
git mv packages/miles-ai/src/miles_ai/integrations/langgraph/constants.py \
       packages/miles-ai/src/miles_ai/rag/graph/constants.py
git mv packages/miles-ai/src/miles_ai/integrations/langgraph/state.py \
       packages/miles-ai/src/miles_ai/rag/graph/state.py
git mv packages/miles-ai/src/miles_ai/integrations/langgraph/grading.py \
       packages/miles-ai/src/miles_ai/rag/graph/grading.py
git mv packages/miles-ai/src/miles_ai/integrations/langgraph/runner.py \
       packages/miles-ai/src/miles_ai/rag/graph/runner.py
git mv packages/miles-ai/src/miles_ai/integrations/langgraph/graphs/rag_qa.py \
       packages/miles-ai/src/miles_ai/rag/graph/rag_qa.py
git rm -q packages/miles-ai/src/miles_ai/integrations/langgraph/graphs/__init__.py
rmdir packages/miles-ai/src/miles_ai/integrations/langgraph/graphs
ls packages/miles-ai/src/miles_ai/integrations/langgraph/
```

Expected: 最后一条列出 `__init__.py`、`checkpointer.py`（`grading.py` 等已不在）。

- [ ] **Step 2: 新建 `rag/graph/__init__.py`（惰性 barrel）**

`packages/miles-ai/src/miles_ai/rag/graph/__init__.py`：

```python
"""
Agent RAG 的 LangGraph 引擎（L2）。

组成
----
- ``rag_qa``：``build_rag_qa_graph`` —— retrieve → grade → generate | retry | fallback
- ``runner``：``run_rag_workflow`` / ``should_use_langgraph_rag`` / ``build_rag_thread_id``
- ``grading``：``evaluate_relevance`` 等评分逻辑（画布 RelevanceGrade 节点亦复用）
- ``constants``：``RELEVANCE_*`` 三态与 ``GRADE_BRANCH_HANDLES``
- ``state``：``RAGGraphState``

画布 ``graph_json`` 的编译与运行见 ``miles_ai.flow_runtime``，与本子包为两套独立编译产物；
多轮状态持久化后端见 ``miles_ai.integrations.langgraph.checkpointer``。
"""

__all__ = [
    "GRADE_BRANCH_HANDLES",
    "RELEVANCE_GOOD",
    "RELEVANCE_NONE",
    "RELEVANCE_POOR",
    "RAGGraphState",
    "build_rag_qa_graph",
    "build_rag_thread_id",
    "evaluate_relevance",
    "llm_grade_relevance",
    "parse_llm_grade_response",
    "run_rag_workflow",
    "should_use_langgraph_rag",
]


def __getattr__(name: str):
    """延迟导出，避免 import 环（``rag.graph`` ↔ ``integrations.langgraph``）。"""
    if name in ("RELEVANCE_GOOD", "RELEVANCE_NONE", "RELEVANCE_POOR", "GRADE_BRANCH_HANDLES"):
        from miles_ai.rag.graph import constants

        return getattr(constants, name)
    if name == "RAGGraphState":
        from miles_ai.rag.graph import state

        return state.RAGGraphState
    if name in ("evaluate_relevance", "llm_grade_relevance", "parse_llm_grade_response", "_score_grade"):
        from miles_ai.rag.graph import grading

        return getattr(grading, name)
    if name == "build_rag_qa_graph":
        from miles_ai.rag.graph.rag_qa import build_rag_qa_graph

        return build_rag_qa_graph
    if name in ("run_rag_workflow", "should_use_langgraph_rag", "build_rag_thread_id"):
        from miles_ai.rag.graph import runner

        return getattr(runner, name)
    raise AttributeError(name)
```

- [ ] **Step 3: 改写 `rag/graph/grading.py` 的 1 条 import**

`packages/miles-ai/src/miles_ai/rag/graph/grading.py` 第 20 行：

```python
from miles_ai.rag.graph.constants import RELEVANCE_GOOD, RELEVANCE_NONE, RELEVANCE_POOR
```

- [ ] **Step 4: 改写 `rag/graph/rag_qa.py` 的 import 与 docstring**

`packages/miles-ai/src/miles_ai/rag/graph/rag_qa.py`：

- docstring 里的 ``状态字段见 ``integrations.langgraph.state.RAGGraphState``；`` → ``状态字段见 ``rag.graph.state.RAGGraphState``；``
- docstring 首行的「RAG 问答 LangGraph（Agent 默认 RAG 引擎）。」保持不变
- 把第 29-36 行的 import 块整体替换为（isort 序：`integrations.chat` < `rag.generate` < `rag.graph.*` < `miles_core.*`）：

```python
from miles_ai.integrations.chat.multimodal import media_refs_from_items
from miles_ai.rag.generate import build_rag_prompt, format_hits_context, generate_rag_answer, retrieve_hits
from miles_ai.rag.graph.constants import RELEVANCE_NONE, RELEVANCE_POOR
from miles_ai.rag.graph.grading import _score_grade, llm_grade_relevance
from miles_ai.rag.graph.state import RAGGraphState
from miles_core.infra.db import AsyncSessionLocal
from miles_core.models.model import ModelConfig
```

> 关键点：`rag.generate` 必须排在 `rag.graph.*` **之前**（`"generate"` < `"graph"`）；三条 `integrations.langgraph.*` 原地替换会破坏此序，必须整块重写。

- [ ] **Step 5: 改写 `rag/graph/runner.py` 的 import 与 docstring**

`packages/miles-ai/src/miles_ai/rag/graph/runner.py`：

- docstring 第 6 行 `编译实例由 ``get_compiled_rag_graph()`` 提供，checkpointer 见 ``checkpointer`` 模块。` 保持不变（Task 4 前 `get_compiled_rag_graph` 仍在 `integrations.langgraph.checkpointer`）
- docstring 末行 `否则默认走 LangGraph；线性路径见 ``rag.generate.generate_rag_answer``。` 保持不变
- 第 24-37 行的 import 块整体替换为（注意 `rag.graph.rag_qa` 必须落在 `integrations.*` **之后**、`miles_common` 之前）：

```python
from langgraph.checkpoint.memory import MemorySaver

from miles_ai.integrations.langchain.chat_models import OnDelta
from miles_ai.integrations.langchain.kb_retrieval import KbRetrievalBindings
from miles_ai.integrations.langgraph.checkpointer import checkpoint_backend, get_compiled_rag_graph
from miles_ai.integrations.litellm.usage_sink import UsageSink
from miles_ai.rag.graph.rag_qa import build_rag_qa_graph
from miles_common.schemas.media import MediaRefIn
from miles_core.models.agent import Agent
from miles_core.models.agent.constants import AgentRuntimeMode
from miles_core.models.media.reader import MediaReader
from miles_core.models.model import ModelConfig
```

> `runner.py` 新 docstring 首行改为 `LangGraph 运行入口（Agent RAG，L2）。`，并在首行下补一行：
> `状态图定义见 ``rag.graph.rag_qa``；多轮状态后端见 ``miles_ai.integrations.langgraph.checkpointer``。`

- [ ] **Step 6: 改写 `flow_runtime/nodes/grade_nodes.py`**

`packages/miles-ai/src/miles_ai/flow_runtime/nodes/grade_nodes.py`：

- 第 16 行 → `from miles_ai.rag.graph.grading import evaluate_relevance`
- docstring 第 4 行的 ``integrations.langgraph.grading.llm_grade_relevance`` → ``rag.graph.grading.llm_grade_relevance``

- [ ] **Step 7: 改写 `flow_runtime/graph_analysis.py` 与 `flow_runtime/compiler/state.py`**

- `packages/miles-ai/src/miles_ai/flow_runtime/graph_analysis.py` 第 18 行 → `from miles_ai.rag.graph.constants import GRADE_BRANCH_HANDLES`
- `packages/miles-ai/src/miles_ai/flow_runtime/compiler/state.py` 的 `from miles_ai.integrations.langgraph.constants import RELEVANCE_NONE` → `from miles_ai.rag.graph.constants import RELEVANCE_NONE`

- [ ] **Step 8: 重写 `integrations/langgraph/__init__.py`（去跨层 re-export）**

`packages/miles-ai/src/miles_ai/integrations/langgraph/__init__.py` 全文替换为：

```python
"""
LangGraph 集成包（L3）：仅保留 checkpointer 生命周期。

RAG 图引擎已归位 ``miles_ai.rag.graph``，画布流程引擎已归位 ``miles_ai.flow_runtime``；
本包不再 re-export 上层编排，避免 L3 反向依赖 L2。

应用启动时经 ``init_langgraph_checkpointer`` 绑定 Redis/Memory，关闭时 ``shutdown_langgraph_checkpointer``。
"""

from miles_ai.integrations.langgraph.checkpointer import (
    checkpoint_backend,
    get_checkpointer,
    init_langgraph_checkpointer,
    shutdown_langgraph_checkpointer,
)

__all__ = [
    "checkpoint_backend",
    "get_checkpointer",
    "init_langgraph_checkpointer",
    "shutdown_langgraph_checkpointer",
]
```

- [ ] **Step 9: 改写 `miles_portal` 的 3 处引用**

| 文件 | 改动 |
|---|---|
| `packages/miles-portal/src/miles_portal/tenant/agents/services/architecture.py:9` | `from miles_ai.integrations.langgraph.runner import should_use_langgraph_rag` → `from miles_ai.rag.graph.runner import should_use_langgraph_rag` |
| `packages/miles-portal/src/miles_portal/tenant/agents/services/agent/chat_rag.py:11` | `from miles_ai.integrations.langgraph.runner import run_rag_workflow, should_use_langgraph_rag` → `from miles_ai.rag.graph.runner import run_rag_workflow, should_use_langgraph_rag` |
| `packages/miles-portal/src/miles_portal/tenant/agents/services/agent/chat_turn.py:7` | `from miles_ai.integrations.langgraph.runner import should_use_langgraph_rag` → `from miles_ai.rag.graph.runner import should_use_langgraph_rag` |

- [ ] **Step 10: 改写 `rag/generate/__init__.py` 的 docstring**

`packages/miles-ai/src/miles_ai/rag/generate/__init__.py` 倒数第 2 行：

`Agent 默认多轮 RAG 图见 ``integrations.langgraph.graphs.rag_qa``，非本包。` → `Agent 默认多轮 RAG 图见 ``rag.graph.rag_qa``，非本包。`

- [ ] **Step 11: 改写 5 个测试文件的 import（目录留到 Task 6 再搬）**

| 文件:行 | 原文 | 改为 |
|---|---|---|
| `tests/miles_ai/flow_runtime/test_flow_runtime_constants.py:9` | `from miles_ai.integrations.langgraph import constants as lg_constants` | `from miles_ai.rag.graph import constants as lg_constants` |
| `tests/miles_ai/flow_runtime/test_flow_runtime_constants.py:10` | `from miles_ai.integrations.langgraph.constants import GRADE_BRANCH_HANDLES` | `from miles_ai.rag.graph.constants import GRADE_BRANCH_HANDLES` |
| `tests/miles_ai/integrations/langgraph/test_langgraph_grading.py:3` | `from miles_ai.integrations.langgraph.constants import RELEVANCE_POOR` | `from miles_ai.rag.graph.constants import RELEVANCE_POOR` |
| `tests/miles_ai/integrations/langgraph/test_langgraph_grading.py:4` | `from miles_ai.integrations.langgraph.grading import parse_llm_grade_response` | `from miles_ai.rag.graph.grading import parse_llm_grade_response` |
| `tests/miles_ai/integrations/langgraph/test_langgraph_rag.py:5` | `from miles_ai.integrations.langgraph.constants import RELEVANCE_GOOD, RELEVANCE_NONE, RELEVANCE_POOR` | `from miles_ai.rag.graph.constants import RELEVANCE_GOOD, RELEVANCE_NONE, RELEVANCE_POOR` |
| `tests/miles_ai/integrations/langgraph/test_langgraph_rag.py:6` | `from miles_ai.integrations.langgraph.grading import _score_grade, parse_llm_grade_response` | `from miles_ai.rag.graph.grading import _score_grade, parse_llm_grade_response` |
| `tests/miles_ai/integrations/langgraph/test_langgraph_rag.py:7` | `from miles_ai.integrations.langgraph.graphs.rag_qa import route_after_grade` | `from miles_ai.rag.graph.rag_qa import route_after_grade` |
| `tests/miles_ai/integrations/langgraph/test_langgraph_rag.py:8` | `from miles_ai.integrations.langgraph.runner import build_rag_thread_id, should_use_langgraph_rag` | `from miles_ai.rag.graph.runner import build_rag_thread_id, should_use_langgraph_rag` |
| `tests/miles_ai/integrations/langgraph/test_rag_answer_stream.py:8` | `from miles_ai.integrations.langgraph.graphs.rag_qa import fallback, generate` | `from miles_ai.rag.graph.rag_qa import fallback, generate` |
| `tests/miles_ai/integrations/langgraph/test_rag_answer_stream.py:9` | `from miles_ai.integrations.langgraph.runner import run_rag_workflow` | `from miles_ai.rag.graph.runner import run_rag_workflow` |
| `tests/miles_ai/integrations/langgraph/test_rag_answer_stream.py:52` | `"miles_ai.integrations.langgraph.runner.get_compiled_rag_graph"` | `"miles_ai.rag.graph.runner.get_compiled_rag_graph"` |
| `tests/miles_ai/integrations/langgraph/test_rag_answer_stream.py:134` | `from miles_ai.integrations.langgraph.graphs.rag_qa import grade_documents` | `from miles_ai.rag.graph.rag_qa import grade_documents` |
| `tests/miles_ai/integrations/langgraph/test_rag_answer_stream.py:153` | `"miles_ai.integrations.langgraph.graphs.rag_qa.llm_grade_relevance"` | `"miles_ai.rag.graph.rag_qa.llm_grade_relevance"` |
| `tests/miles_ai/integrations/langgraph/test_rag_multimodal.py:9` | `from miles_ai.integrations.langgraph.graphs.rag_qa import _prompt_user_query, fallback, generate` | `from miles_ai.rag.graph.rag_qa import _prompt_user_query, fallback, generate` |
| `tests/miles_ai/integrations/langgraph/test_rag_multimodal.py:10` | `from miles_ai.integrations.langgraph.runner import run_rag_workflow` | `from miles_ai.rag.graph.runner import run_rag_workflow` |
| `tests/miles_ai/integrations/langgraph/test_rag_multimodal.py:85` | `"miles_ai.integrations.langgraph.runner.get_compiled_rag_graph"` | `"miles_ai.rag.graph.runner.get_compiled_rag_graph"` |
| `tests/miles_ai/integrations/langgraph/test_rag_qa_nodes_share_generate.py:12` | `import miles_ai.integrations.langgraph.graphs.rag_qa as rag_qa_mod` | `import miles_ai.rag.graph.rag_qa as rag_qa_mod` |
| `tests/miles_ai/integrations/langgraph/test_rag_qa_nodes_share_generate.py:13` | `from miles_ai.integrations.langgraph.graphs.rag_qa import fallback, generate, retrieve` | `from miles_ai.rag.graph.rag_qa import fallback, generate, retrieve` |
| `tests/miles_ai/integrations/langgraph/test_rag_qa_nodes_share_generate.py:48,65,82` | `"miles_ai.integrations.langgraph.graphs.rag_qa.generate_rag_answer"`（3 处） | `"miles_ai.rag.graph.rag_qa.generate_rag_answer"` |
| `tests/miles_portal/tenant/agents/test_rag_usage_accumulation.py:12` | `import miles_ai.integrations.langgraph.graphs.rag_qa as rag_qa` | `import miles_ai.rag.graph.rag_qa as rag_qa` |
| `tests/miles_portal/tenant/agents/test_rag_usage_accumulation.py:14` | `from miles_ai.integrations.langgraph.graphs.rag_qa import build_rag_qa_graph` | `from miles_ai.rag.graph.rag_qa import build_rag_qa_graph` |

> `test_rag_multimodal.py` / `test_rag_answer_stream.py` 里的 `_prompt_user_query`、`route_after_grade`、`fallback`、`generate`、`grade_documents` 都是 `rag_qa` 的模块级函数，搬迁后仍在同一模块，符号名不变。

- [ ] **Step 12: 验证并提交**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
rg -n "integrations\.langgraph\.(constants|state|grading|graphs|runner)\b" packages tests; echo "--- 期望：无输出"
rg -n "miles_ai\.(rag|flow_runtime)" packages/miles-ai/src/miles_ai/integrations -g '*.py' | awk -F: '{print $3}' | sort | uniq -c
.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/lint-imports | tail -3
.venv/bin/python -m pytest -q
.venv/bin/python -m miles_server.scripts.export_openapi --check
```

Expected: 第一条无输出；剩余反向边只有 `langchain/{__init__,kb_retrieval,vectorstores,visual_embeddings}.py` 与 `langgraph/checkpointer.py` 相关（`checkpointer.py` 本身不 import rag）；pytest `1517 passed`；OpenAPI 零漂移。

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI
git add -A
git commit -F- <<'EOF'
refactor(ai): Agent RAG 图引擎由 integrations 归位到 rag/graph

RAG 问答的 LangGraph 引擎（常量、状态、评分、执行入口、rag_qa 图）按分层
应属 L2，先前因按技术名建包而落在 L3 的 integrations/langgraph 内，形成
integrations 反向依赖 rag 的 8 条边。

新子包 rag/graph 采用惰性 __getattr__ barrel，避免与
integrations.langgraph.checkpointer 互引成环；integrations/langgraph 门面
不再 re-export 上层编排，只保留本包的 checkpointer。

纯搬迁，不改逻辑。
EOF
git log --oneline -1
```

---

### Task 3: `kb_retrieval` 归位、删除 `vectorstores` 转发壳、清理 `langchain` 门面

**Files:**
- Move: `packages/miles-ai/src/miles_ai/integrations/langchain/kb_retrieval.py` → `packages/miles-ai/src/miles_ai/rag/retrieve/bindings.py`
- Delete: `packages/miles-ai/src/miles_ai/integrations/langchain/vectorstores.py`
- Modify: `packages/miles-ai/src/miles_ai/integrations/langchain/__init__.py`
- Modify: `packages/miles-ai/src/miles_ai/rag/generate/answer.py`
- Modify: `packages/miles-ai/src/miles_ai/rag/graph/runner.py`
- Modify: `packages/miles-ai/src/miles_ai/rag/retrieve/multi_kb.py`（docstring）
- Modify: `packages/miles-portal/src/miles_portal/tenant/kb/services/embeddings.py:23`

**Interfaces:**
- Consumes: Task 2 产出的 `miles_ai.rag.graph.runner`
- Produces: `miles_ai.rag.retrieve.bindings.KbRetrievalBindings`（原 `miles_ai.integrations.langchain.kb_retrieval.KbRetrievalBindings`，字段不变：`embed_query_sync`、`embed_query`、`resolve_rerank_sync`、`resolve_rerank`）

- [ ] **Step 1: `git mv` 并删除转发壳**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
git mv packages/miles-ai/src/miles_ai/integrations/langchain/kb_retrieval.py \
       packages/miles-ai/src/miles_ai/rag/retrieve/bindings.py
git rm -q packages/miles-ai/src/miles_ai/integrations/langchain/vectorstores.py
ls packages/miles-ai/src/miles_ai/integrations/langchain/
```

Expected: 列出 `__init__.py`、`chat_models.py`、`tool_agent`、`toolkit`、`visual_embeddings.py`。

- [ ] **Step 2: 更新 `rag/retrieve/bindings.py` 的 docstring**

`packages/miles-ai/src/miles_ai/rag/retrieve/bindings.py` 的模块 docstring 替换为：

```python
"""KB 检索绑定载体（L2，不依赖 tenant 域）。

供 L1 kb 域 ``tenant.kb.services.embeddings`` 构造，注入 ``rag.retrieve.multi_kb``
与 ``rag.graph.runner``；类型别名直接复用 multi_kb 的回调签名。
"""
```

`KbRetrievalBindings` 的类 docstring 与字段**逐字不变**。

- [ ] **Step 3: 改写 `rag/generate/answer.py`**

`packages/miles-ai/src/miles_ai/rag/generate/answer.py`：

- docstring 的 `- 复杂 Agent / 流程画布走 ``integrations.langchain`` / LangGraph，不经过本模块。` → `- 复杂 Agent / 流程画布走 ``rag.graph`` / ``flow_runtime``，不经过本模块。`
- docstring 的 `- 检索：``integrations.langchain.vectorstores.search_multi_kb_async`` → ``rag.retrieve.multi_kb``。` → `- 检索：``rag.retrieve.multi_kb.search_multi_kb_async``。`
- 第 26-27 行两条 import 改为：

```python
from miles_ai.rag.retrieve.bindings import KbRetrievalBindings
from miles_ai.rag.retrieve.multi_kb import search_multi_kb_async
```

> 必须**直达** `rag.retrieve.multi_kb`，不经 `rag.retrieve/__init__.py`（其 `__getattr__` 只导出 `search_multi_kb_async`，且 `multi_kb` 在导入期需要满足模块级解析）。`retrieve_hits()` 函数体与签名**逐字不变**（仍以 `bindings=bindings` 关键字传参）。

- [ ] **Step 4: 改写 `rag/graph/runner.py` 的 bindings import**

`packages/miles-ai/src/miles_ai/rag/graph/runner.py` 的 `from miles_ai.integrations.langchain.kb_retrieval import KbRetrievalBindings` → `from miles_ai.rag.retrieve.bindings import KbRetrievalBindings`

- [ ] **Step 5: 重写 `integrations/langchain/__init__.py`**

`packages/miles-ai/src/miles_ai/integrations/langchain/__init__.py` 全文替换为：

```python
"""
LangChain 集成包（L3，仅本子包内容）。

- ``chat_models``：``ainvoke_chat`` / ``get_chat_model``
- ``tool_agent``：工具调用循环与契约
- ``toolkit``：平台工具 → LangChain 工具适配

检索、RAG 生成、KB 检索绑定分别见 ``rag.retrieve.multi_kb``、``rag.generate``、
``rag.retrieve.bindings``；本包不再 re-export 上层 L2 内容。
"""

from miles_ai.integrations.langchain.chat_models import ainvoke_chat, get_chat_model

__all__ = ["ainvoke_chat", "get_chat_model"]
```

- [ ] **Step 6: 改写 `miles_portal` 的 1 处 import，并订正该文件 docstring**

`packages/miles-portal/src/miles_portal/tenant/kb/services/embeddings.py:23`（原地替换即可，`rag.retrieve.bindings` 落在 `integrations.embeddings.runtime` 之后、`miles_common.exceptions` 之前，序仍正确）：

```python
from miles_ai.rag.retrieve.bindings import KbRetrievalBindings
```

同文件 docstring 第 8 行：

`- ``build_kb_retrieval_bindings`` 构造供 L3 ``vectorstores`` 检索注入的中立载体。`
→ `- ``build_kb_retrieval_bindings`` 构造供 ``rag.retrieve`` 检索注入的中立载体（``rag.retrieve.bindings.KbRetrievalBindings``）。`

- [ ] **Step 7: 更新 `rag/retrieve/multi_kb.py` 的 docstring**

`packages/miles-ai/src/miles_ai/rag/retrieve/multi_kb.py` docstring 末两行：

```
同步 ``search_kb`` 由 L3 ``vectorstores`` 壳转发（内置工具用）；
异步 ``search_multi_kb_async`` 经 L3 壳注入 bindings 供问答/检索链路用。
```

改为：

```
同步 ``search_kb`` 供内置工具体同步路径直接调用；
异步 ``search_multi_kb_async`` 由调用方经 ``rag.retrieve.bindings`` 注入 embed/rerank 回调。
```

> 原 docstring 声称 `search_kb` 由 `vectorstores` 壳转发，实测该壳已删除且 `search_kb` 无调用方；此处只订正描述文本，**函数体与签名不动**。

- [ ] **Step 8: 验证并提交**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
rg -n "integrations\.langchain\.(kb_retrieval|vectorstores)" packages tests; echo "--- 期望：无输出"
rg -n "miles_ai\.(rag|flow_runtime)" packages/miles-ai/src/miles_ai/integrations -g '*.py'
.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/lint-imports | tail -3
.venv/bin/python -m pytest -q
.venv/bin/python -m miles_server.scripts.export_openapi --check
```

Expected: 前两条只剩 `integrations/langchain/visual_embeddings.py`（Task 5 处理）与 `integrations/langgraph/checkpointer.py`（imports `miles_core`，不涉 rag）；pytest `1517 passed`。

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI
git add -A
git commit -F- <<'EOF'
refactor(ai): KB 检索绑定归位 rag 并删除 vectorstores 转发壳

kb_retrieval 只是依赖 rag.retrieve.multi_kb 类型别名的载体，迁至
rag/retrieve/bindings；vectorstores 全文无 LangChain 代码、仅 1 处消费者，
且同步版 search_kb 零调用，按「禁止无逻辑 re-export 包」删除。
langchain 门面随之只 re-export 本子包内容。
EOF
git log --oneline -1
```

---

### Task 4: 拆分 `checkpointer`，把 RAG 图编译单例移到 `rag/graph/compiled.py`

`integrations/langgraph/checkpointer.py` 同时管「checkpointer 生命周期」与「编译并缓存 RAG 图」，后者是 ③ 的职责。拆出后 `integrations` 不再持有任何 `rag` 引用。

**Files:**
- Create: `packages/miles-ai/src/miles_ai/rag/graph/compiled.py`
- Modify: `packages/miles-ai/src/miles_ai/integrations/langgraph/checkpointer.py`
- Modify: `packages/miles-ai/src/miles_ai/rag/graph/runner.py`
- Modify: `packages/miles-server/src/miles_server/apps/application.py:18-35`

**Interfaces:**
- Consumes: `miles_ai.integrations.langgraph.checkpointer.get_checkpointer()`、`miles_ai.rag.graph.rag_qa.build_rag_qa_graph`
- Produces: `miles_ai.rag.graph.compiled.get_compiled_rag_graph() -> Any`、`miles_ai.rag.graph.compiled.bind_rag_graph() -> None`、`miles_ai.rag.graph.compiled.unbind_rag_graph() -> None`

- [ ] **Step 1: 新建 `rag/graph/compiled.py`**

`packages/miles-ai/src/miles_ai/rag/graph/compiled.py`：

```python
"""
带 checkpointer 的 RAG QA 编译图单例（L2）。

由 ``miles_server`` 的 lifespan 在 ``init_langgraph_checkpointer()`` 之后调用
``bind_rag_graph()`` 绑定；未绑定时 ``get_compiled_rag_graph()`` 回退
``build_rag_qa_graph().compile(MemorySaver())``（**不缓存**回退实例，与拆分前一致）。

多轮状态后端的选择与释放见 ``miles_ai.integrations.langgraph.checkpointer``。
"""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.memory import MemorySaver

from miles_ai.rag.graph.rag_qa import build_rag_qa_graph

_compiled_rag_graph: Any = None


def get_compiled_rag_graph() -> Any:
    """返回已绑定的 RAG 编译图；未绑定时回退内存 checkpointer 的一次性编译实例。"""
    if _compiled_rag_graph is None:
        return build_rag_qa_graph().compile(checkpointer=MemorySaver())
    return _compiled_rag_graph


def bind_rag_graph() -> None:
    """用当前 checkpointer 编译并缓存 RAG 图；由应用 lifespan 在 checkpointer 初始化后调用。"""
    global _compiled_rag_graph

    from miles_ai.integrations.langgraph.checkpointer import get_checkpointer

    _compiled_rag_graph = build_rag_qa_graph().compile(checkpointer=get_checkpointer())


def unbind_rag_graph() -> None:
    """清除进程内缓存的编译图；由应用关闭时调用。"""
    global _compiled_rag_graph
    _compiled_rag_graph = None
```

> `get_checkpointer` 采用**函数内惰性 import**，使模块导入期不触发 `integrations.langgraph` 包的 `__init__`（其 re-export 了 checkpointer），避免与 `rag.graph` barrel 形成导入期环。`build_rag_qa_graph` 为模块级 import，与拆分前 `checkpointer.py` 的惰性导入等价（拆分前也是函数内 import），行为不变。

- [ ] **Step 2: 改写 `integrations/langgraph/checkpointer.py`**

`packages/miles-ai/src/miles_ai/integrations/langgraph/checkpointer.py` 做四处改动：

1. 模块 docstring 改为：

```python
"""
LangGraph Checkpointer：优先 Redis，不可用时回退内存。

用途
----
- Agent RAG 图（``rag.graph.compiled.get_compiled_rag_graph``）：``thread_id = tenant:agent:conversation_id``
- DeepAgents / 其它需多轮状态恢复的 LangGraph 应用

应用启动时 ``init_langgraph_checkpointer``；未初始化时 ``get_checkpointer()`` 回退 ``MemorySaver``。
RAG 编译图单例不在此模块，见 ``miles_ai.rag.graph.compiled``。
"""
```

2. 删除全局 `_compiled_rag_graph: Any = None  # 进程内单例，随 checkpointer 后端初始化`，保留 `_checkpointer` / `_exit_stack` / `_backend`。

3. 删除 `get_compiled_rag_graph()` 整个函数。

4. `init_langgraph_checkpointer()` 与 `shutdown_langgraph_checkpointer()` 改为（**只**去掉 RAG 图相关语句，其余逐字保留）：

```python
async def init_langgraph_checkpointer() -> str:
    """
    应用 lifespan 启动时调用；返回实际后端 ``redis`` | ``memory``。

    受 ``Settings.langgraph_redis_checkpoint`` 与 Redis 健康检查控制；
    失败时降级 MemorySaver 并打日志，不阻塞进程启动。
    """
    global _checkpointer, _exit_stack, _backend
    # ... 函数体保持原样直到 _checkpointer = saver 与 _backend = backend 两行 ...
    _checkpointer = saver
    _backend = backend
    return backend


async def shutdown_langgraph_checkpointer() -> None:
    """应用关闭时释放 Redis checkpointer 连接。"""
    global _checkpointer, _exit_stack, _backend
    if _exit_stack is not None:
        await _exit_stack.aclose()
        _exit_stack = None
    _checkpointer = None
    _backend = "memory"
```

> 注意：`global` 声明里必须去掉 `_compiled_rag_graph`；原函数的 `_compiled_rag_graph = build_rag_qa_graph().compile(checkpointer=saver)` 一行删除；原 `from miles_ai.integrations.langgraph.graphs.rag_qa import build_rag_qa_graph` 的两处惰性 import（原第 64、84 行）一并删除。函数体其余部分（Redis 探测、`AsyncRedisSaver` 上下文、三处日志、`except ImportError` / `except Exception` 分支）**逐字保留**。

- [ ] **Step 3: 改写 `rag/graph/runner.py` 的 compiled import**

`packages/miles-ai/src/miles_ai/rag/graph/runner.py` 的 import 块改为（`integrations.langgraph.checkpointer` 只留 `checkpoint_backend`；`get_compiled_rag_graph` 改从 `rag.graph.compiled` 取，落在 `rag.graph.rag_qa` 之前）：

```python
from miles_ai.integrations.langchain.chat_models import OnDelta
from miles_ai.integrations.langchain.kb_retrieval import KbRetrievalBindings
from miles_ai.integrations.langgraph.checkpointer import checkpoint_backend
from miles_ai.integrations.litellm.usage_sink import UsageSink
from miles_ai.rag.graph.compiled import get_compiled_rag_graph
from miles_ai.rag.graph.rag_qa import build_rag_qa_graph
from miles_common.schemas.media import MediaRefIn
from miles_core.models.agent import Agent
from miles_core.models.agent.constants import AgentRuntimeMode
from miles_core.models.media.reader import MediaReader
from miles_core.models.model import ModelConfig
```

- docstring 第 6 行 `编译实例由 ``get_compiled_rag_graph()`` 提供，checkpointer 见 ``checkpointer`` 模块。` → `编译实例由 ``rag.graph.compiled.get_compiled_rag_graph()`` 提供，多轮状态后端见 ``integrations.langgraph.checkpointer``。`

- `compile_rag_graph_for_tests()`（文件末尾）保持不变。

- [ ] **Step 4: 调整 `miles_server` lifespan**

`packages/miles-server/src/miles_server/apps/application.py`，把 lifespan 改为：

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期钩子：启动时初始化日志 / OTel、执行 schema 迁移并建 LangGraph checkpointer，关闭时逆序释放。"""
    from miles_ai.integrations.langgraph.checkpointer import (
        init_langgraph_checkpointer,
        shutdown_langgraph_checkpointer,
    )
    from miles_ai.rag.graph.compiled import bind_rag_graph, unbind_rag_graph
    from miles_core.infra.otel import setup_otel, shutdown_otel

    setup_logging()
    setup_otel(get_settings(), app=app)
    # 启动时只做 schema 迁移；业务种子由 `milesai init-db` 单独执行
    run_migrations()
    # 初始化 RAG / DeepAgents 共用 checkpointer（redis | memory），见 langgraph.checkpointer
    app.state.langgraph_checkpoint = await init_langgraph_checkpointer()
    # 用该 checkpointer 编译并缓存 Agent RAG 图，见 rag.graph.compiled
    bind_rag_graph()
    yield
    unbind_rag_graph()
    await shutdown_langgraph_checkpointer()
    shutdown_otel()
```

> `create_app()` 及其后内容不动。`app.state.langgraph_checkpoint` 的取值语义不变（仍是后端名 `redis` | `memory`）。

- [ ] **Step 5: 验证并提交**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
rg -n "get_compiled_rag_graph" packages tests
echo "--- 期望：仅 rag/graph/compiled.py 定义处 + rag/graph/runner.py 使用/import + 2 个测试的 patch 字符串"
rg -n "miles_ai\.(rag|flow_runtime)" packages/miles-ai/src/miles_ai/integrations -g '*.py'; echo "--- 期望：仅 visual_embeddings.py（Task 5 处理）"
.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/lint-imports | tail -3
.venv/bin/python -m pytest -q
.venv/bin/python -m miles_server.scripts.export_openapi --check
```

Expected: pytest `1517 passed`（checkpointer 相关用例与 lifespan 冒烟一并通过）；OpenAPI 零漂移。

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
.venv/bin/python - <<'PY'
import asyncio
from miles_ai.rag.graph.compiled import bind_rag_graph, get_compiled_rag_graph, unbind_rag_graph

graph = get_compiled_rag_graph()
assert graph is not None
assert get_compiled_rag_graph() is not graph, "未绑定时回退实例不得被缓存"

bind_rag_graph()
cached = get_compiled_rag_graph()
assert get_compiled_rag_graph() is cached, "绑定后必须返回同一单例"
print("compiled.py 三态行为 OK")
PY
```

Expected: 打印 `compiled.py 三态行为 OK`。

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI
git add -A
git commit -F- <<'EOF'
refactor(ai): 拆出 rag.graph.compiled，checkpointer 回归纯基础设施

checkpointer 同时承担 checkpointer 生命周期与 Agent RAG 图的编译缓存，
后者在分层上属 L2 引擎职责，且使 integrations 反向持有 rag 引用。
拆出 compiled 模块（含绑定 / 解绑）后 integrations 不再依赖 rag，
rag 经 get_checkpointer 单向取后端。

miles_server lifespan 相应在初始化 checkpointer 后调用 bind_rag_graph，
关闭时逆序 unbind，app.state.langgraph_checkpoint 语义不变。
EOF
git log --oneline -1
```

---

### Task 5: 拆除混装文件 `visual_embeddings.py`

该文件把「CLIP 模型类型校验」（L3 适配）与「KB 视觉向量化入库策略」（L2）装在一起，是最后一个 `integrations → rag` 引用来源。

**Files:**
- Create: `packages/miles-ai/src/miles_ai/integrations/embeddings/policy.py`
- Create: `packages/miles-ai/src/miles_ai/rag/pipeline/visual_policy.py`
- Delete: `packages/miles-ai/src/miles_ai/integrations/langchain/visual_embeddings.py`
- Modify: `packages/miles-ai/src/miles_ai/rag/pipeline/ingest.py:30`
- Modify: `packages/miles-portal/src/miles_portal/tenant/kb/services/embeddings.py:54`
- Modify: `packages/miles-portal/src/miles_portal/tenant/kb/services/kb/core.py:9`

**Interfaces:**
- Consumes: `miles_ai.integrations.embeddings.constants.INVOKE_MODE_CLIP`、`miles_ai.integrations.embeddings.model_meta.invoke_mode_from_model`、`miles_ai.rag.parse.media.is_image_file`、`miles_core.models.kb.KnowledgeBase`
- Produces: `miles_ai.integrations.embeddings.policy.ensure_clip_model(model) -> None`、`miles_ai.rag.pipeline.visual_policy.should_use_visual_image_embedding(kb, filename, mime_type) -> bool`

- [ ] **Step 1: 新建 `integrations/embeddings/policy.py`**

`packages/miles-ai/src/miles_ai/integrations/embeddings/policy.py`：

```python
"""向量化模型调用策略（模型类型校验）。"""

from __future__ import annotations

from miles_ai.integrations.embeddings.constants import INVOKE_MODE_CLIP
from miles_ai.integrations.embeddings.model_meta import invoke_mode_from_model
from miles_common.exceptions import BadRequestError


def ensure_clip_model(model) -> None:
    """校验模型为 CLIP 视觉向量化类型；否则抛 ``BadRequestError``。"""
    if invoke_mode_from_model(model) != INVOKE_MODE_CLIP:
        raise BadRequestError(f"模型「{model.name}」不是 CLIP 视觉向量化模型")
```

- [ ] **Step 2: 新建 `rag/pipeline/visual_policy.py`**

`packages/miles-ai/src/miles_ai/rag/pipeline/visual_policy.py`：

```python
"""入库时的视觉向量化决策（是否对图片走 CLIP 向量化）。"""

from __future__ import annotations

from miles_ai.rag.parse.media import is_image_file
from miles_core.models.kb import KnowledgeBase


def should_use_visual_image_embedding(
    kb: KnowledgeBase,
    filename: str,
    mime_type: str,
) -> bool:
    """KB 绑定了视觉向量化模型且文件为图片时返回 ``True``。"""
    return kb.visual_embedding_model_config_id is not None and is_image_file(filename, mime_type)
```

- [ ] **Step 3: 删除原混装文件并改两处 import**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
git rm -q packages/miles-ai/src/miles_ai/integrations/langchain/visual_embeddings.py
```

- `packages/miles-ai/src/miles_ai/rag/pipeline/ingest.py` 第 29-35 行的 import 块整体替换为（`rag.pipeline.*` 必须排在 `rag.parse.*` **之后**，不可原地替换第 30 行）：

```python
from sqlalchemy.orm import Session

from miles_ai.rag.chunk import chunk_documents
from miles_ai.rag.index.gateway import upsert_chunk_vector
from miles_ai.rag.parse import vector_type_for_document
from miles_ai.rag.parse.loaders import load_documents_from_bytes
from miles_ai.rag.pipeline.visual_policy import should_use_visual_image_embedding
from miles_core.models.kb import Document, DocumentChunk, KnowledgeBase, VectorRef
```

- `packages/miles-portal/src/miles_portal/tenant/kb/services/embeddings.py:54`（`_ensure_clip` 函数内 import）：
  `from miles_ai.integrations.langchain.visual_embeddings import ensure_clip_model`
  → `from miles_ai.integrations.embeddings.policy import ensure_clip_model`
- `packages/miles-portal/src/miles_portal/tenant/kb/services/kb/core.py:9`（原地替换即可，`embeddings.model_meta` < `embeddings.policy`，序仍正确）：
  `from miles_ai.integrations.langchain.visual_embeddings import ensure_clip_model`
  → `from miles_ai.integrations.embeddings.policy import ensure_clip_model`

- [ ] **Step 4: 改写 `tests/miles_ai/integrations/embeddings/test_clip_visual_search.py`**

该文件的 3 个用例中，`test_should_use_visual_image_embedding` 随源码迁往 `tests/miles_ai/rag/test_visual_embedding_policy.py`（Task 6 Step 3）。本步先把该用例从本文件删除，并把 import 改为：

```python
from miles_ai.integrations.embeddings.constants import EXTRA_EMBEDDING_DIMENSION, INVOKE_MODE_CLIP
from miles_ai.integrations.embeddings.policy import ensure_clip_model
from miles_ai.integrations.embeddings.providers.clip import ClipEmbeddingProvider
from miles_core.models.model import ModelConfig
from miles_core.models.model.catalog import ModelCapabilityType
```

同时删除本文件已不再使用的 `from miles_core.models.kb import KnowledgeBase`。

> 删除用例后本文件保留 `test_ensure_clip_model_rejects_text_embedding` 与 `test_clip_embed_texts` 两个用例；`uuid4`、`numpy`、`MagicMock`、`patch`、`pytest` 仍被使用，不得删。

- [ ] **Step 5: 验证并提交**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
rg -n "integrations\.langchain\.(visual_embeddings|kb_retrieval|vectorstores)" packages tests; echo "--- 期望：无输出"
echo "=== 反向边（必须为 0） ==="
rg -n "^\s*(from|import)\s+miles_ai\.(rag|flow_runtime)" packages/miles-ai/src/miles_ai/integrations; echo "--- 期望：无输出"
.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/lint-imports | tail -3
.venv/bin/python -m pytest -q
.venv/bin/python -m miles_server.scripts.export_openapi --check
```

Expected: 前两条均无输出（**这是本计划的核心验收点**）；pytest `1516 passed`（少 1 个用例 —— 被删除的 `test_should_use_visual_image_embedding` 尚未在 Task 6 重建，Task 6 收尾回到 1517）。

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI
git add -A
git commit -F- <<'EOF'
refactor(ai): 拆除 visual_embeddings 混装文件

原文件把 CLIP 模型类型校验（L3 适配）与 KB 视觉向量化入库策略（L2）装在
一起，是 integrations 反向依赖 rag 的最后一处来源。按职责拆为
integrations.embeddings.policy 与 rag.pipeline.visual_policy。

至此 integrations 对 rag / flow_runtime 的引用为 0。
EOF
git log --oneline -1
```

---

### Task 6: 测试用例按镜像规则归位

源码归位后，测试目录须跟随（`tests/test_tests_layout.py` 判据 3 要求 `tests/miles_ai/<a>/…/<z>/` 对应真实源码目录）。**纯 `git mv` + import 路径改写，禁止改用例逻辑与断言。**

**Files:**
- Move: `tests/miles_ai/integrations/langgraph/test_canvas_state_contract.py` → `tests/miles_ai/flow_runtime/`
- Move: `tests/miles_ai/integrations/langgraph/test_compile_error_details.py` → `tests/miles_ai/flow_runtime/`
- Move: `tests/miles_ai/integrations/langgraph/test_langgraph_build.py` → `tests/miles_ai/flow_runtime/`
- Move: `tests/miles_ai/integrations/langgraph/test_langgraph_compiler.py` → `tests/miles_ai/flow_runtime/`
- Move: `tests/miles_ai/integrations/langgraph/test_langgraph_parallel.py` → `tests/miles_ai/flow_runtime/`
- Move: `tests/miles_ai/integrations/langgraph/test_langgraph_grading.py` → `tests/miles_ai/rag/graph/`
- Move: `tests/miles_ai/integrations/langgraph/test_langgraph_rag.py` → `tests/miles_ai/rag/graph/`
- Move: `tests/miles_ai/integrations/langgraph/test_rag_answer_stream.py` → `tests/miles_ai/rag/graph/`
- Move: `tests/miles_ai/integrations/langgraph/test_rag_multimodal.py` → `tests/miles_ai/rag/graph/`
- Move: `tests/miles_ai/integrations/langgraph/test_rag_qa_nodes_share_generate.py` → `tests/miles_ai/rag/graph/`
- Create: `tests/miles_ai/rag/test_visual_embedding_policy.py`

**Interfaces:**
- Consumes: Task 2 的 `miles_ai.rag.graph.*`、Task 1 的 `miles_ai.flow_runtime.compiler`、Task 5 的 `miles_ai.rag.pipeline.visual_policy`

- [ ] **Step 1: 建目标目录并 `git mv` 10 个文件**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
mkdir -p tests/miles_ai/rag/graph
for f in test_canvas_state_contract.py test_compile_error_details.py test_langgraph_build.py \
         test_langgraph_compiler.py test_langgraph_parallel.py; do
  git mv "tests/miles_ai/integrations/langgraph/$f" "tests/miles_ai/flow_runtime/$f"
done
for f in test_langgraph_grading.py test_langgraph_rag.py test_rag_answer_stream.py \
         test_rag_multimodal.py test_rag_qa_nodes_share_generate.py; do
  git mv "tests/miles_ai/integrations/langgraph/$f" "tests/miles_ai/rag/graph/$f"
done
rmdir tests/miles_ai/integrations/langgraph 2>/dev/null
ls tests/miles_ai/integrations/ tests/miles_ai/rag/graph/
```

Expected: `tests/miles_ai/integrations/` 只剩 `deepagents/ embeddings/ generative/ langchain/ litellm/ rerank/`（`langgraph/` 已消失）；`tests/miles_ai/rag/graph/` 列出 5 个文件。

- [ ] **Step 2: 修正搬迁后测试文件里的跨文件引用与路径**

| 文件 | 检查项 | 处理 |
|---|---|---|
| 全部 10 个 | `from tests.paths import MILES_AI` / `from tests.` 开头的 import | **不改**（`tests.` 绝对路径与文件所在层无关） |
| `tests/miles_ai/rag/graph/test_rag_answer_stream.py:11` | `from tests.miles_ai.integrations.litellm.test_litellm_adapter import _model` | **不改**（目标文件未移动） |

无需改动的项：10 个文件的 import 已在 Task 1/2 改写完毕；`MILES_AI` 路径读取的是 `flow_runtime/templates/*.json`，模板未移动。

- [ ] **Step 3: 新建 `tests/miles_ai/rag/test_visual_embedding_policy.py`**

把 `tests/miles_ai/integrations/embeddings/test_clip_visual_search.py` 中 `test_should_use_visual_image_embedding` 的用例体**逐字**搬入：

```python
"""KB 视觉向量化入库策略测试（rag.pipeline.visual_policy）。"""

from uuid import uuid4

from miles_ai.rag.pipeline.visual_policy import should_use_visual_image_embedding
from miles_core.models.kb import KnowledgeBase


def test_should_use_visual_image_embedding():
    kb = KnowledgeBase(
        id=uuid4(),
        tenant_id=uuid4(),
        name="kb",
        embedding_model_config_id=uuid4(),
        visual_embedding_model_config_id=uuid4(),
    )
    assert should_use_visual_image_embedding(kb, "photo.jpg", "image/jpeg") is True
    assert should_use_visual_image_embedding(kb, "doc.pdf", "application/pdf") is False
```

- [ ] **Step 4: 验证布局守卫与全量测试**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
.venv/bin/python -m pytest -q tests/test_tests_layout.py tests/test_no_unreferenced_modules.py tests/test_l3_neutral_imports.py
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest -q --collect-only 2>/dev/null | grep '::' | sed -E 's/^[^:]+:://' | sort > /tmp/ai-names-after.txt
diff /tmp/ai-names-before.txt /tmp/ai-names-after.txt && echo "用例集合零变化"
```

Expected: 三个守卫全 passed；全量 `1517 passed`；`diff` 无输出、打印 `用例集合零变化`。

- [ ] **Step 5: 提交**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI
git add -A
git commit -F- <<'EOF'
refactor(tests): miles_ai 测试目录跟随源码归位

画布流程引擎用例迁 tests/miles_ai/flow_runtime，Agent RAG 图引擎用例迁
tests/miles_ai/rag/graph，KB 视觉向量化策略用例迁 tests/miles_ai/rag。

纯搬迁，用例集合与断言零变化（对照 --collect-only 快照逐行一致）。
EOF
git log --oneline -1
```

---

### Task 7: 加 `import-linter` 分层契约并同步文档

**Files:**
- Modify: `backend/.importlinter`
- Modify: `docs/architecture/layering.md`（§2.4、§3.1、§3、§5.2）
- Modify: `docs/superpowers/specs/2026-09-22-miles-ai-internal-layering-design.md`（§14 补「已实施」记录）

**Interfaces:**
- Consumes: Task 1–6 全部产出
- Produces: `miles_ai` 包内分层契约（CI 门禁 `make layers-check` 的一部分）

- [ ] **Step 1: 写入契约**

在 `backend/.importlinter` 末尾追加：

```ini
# miles_ai 包内分层：编排（flow_runtime）在上、RAG（rag）居中、第三方适配（integrations）在下。
# 必要性：包级 `layers` 契约只看到 miles_ai 一个节点，管不到包内三个子包的方向；
# 而 integrations 曾长期反向依赖 rag / flow_runtime（实测 13 文件 21 条 import，2026-09-22 归位）。
# 选择 layers 而非两条 forbidden：它额外冻结 `rag ✗→ flow_runtime`。
# 该边当前实测为 0，且是真实约束——flow_runtime 依赖 rag，反向必成环。
[importlinter:contract:ai-internal-layers]
name = miles_ai 内部分层（编排在上，适配在下）
type = layers
layers =
    miles_ai.flow_runtime
    miles_ai.rag
    miles_ai.integrations
```

- [ ] **Step 2: 红测 —— 证明契约能拦住违规**

临时制造一处违规并跑契约，再撤销：

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
printf '\nfrom miles_ai.rag.chunk import split_text  # noqa: F401\n' >> packages/miles-ai/src/miles_ai/integrations/langchain/chat_models.py
.venv/bin/lint-imports | tail -14
git checkout -- packages/miles-ai/src/miles_ai/integrations/langchain/chat_models.py
git status --porcelain; echo "--- 期望：空（违规已撤销）"
```

Expected: 输出含 `miles_ai 内部分层（编排在上，适配在下） BROKEN` 且指明 `miles_ai.integrations.langchain.chat_models` 违规；末行 `Contracts: 7 kept, 1 broken.`

> 契约不能是空转的：若本步仍显示 `8 kept`，说明 `layers` 的模块路径写错（例如漏了 `miles_ai.` 前缀会命中空集合），必须修正后再继续。

- [ ] **Step 3: 绿测**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
.venv/bin/lint-imports | tail -12
```

Expected: 8 条契约全部 `KEPT`，末行 `Contracts: 8 kept, 0 broken.`

- [ ] **Step 4: 同步 `layering.md`**

`docs/architecture/layering.md`：

1. §2.4 包表格中 `miles_ai` 行改为：

```
| `miles_ai` | L2 RAG（含 `rag/graph/` Agent RAG 图引擎）+ L2 `flow_runtime`（含 `compiler/` 画布编译器）+ L3 集成（LangChain / LangGraph / LiteLLM / DeepAgents） | L2/L3 |
```

2. §2.4 硬判据表后追加一行说明：

```
**包内分层（`miles_ai`）**：`flow_runtime → rag → integrations` 单向，由 `.importlinter` 的 `ai-internal-layers` 契约强制；`integrations` 不得 import `rag` / `flow_runtime`，`rag` 不得 import `flow_runtime`。
```

3. §3 目录结构中 `miles-ai` 段改为：

```
├── miles-ai/src/miles_ai/               # L2/L3
│   ├── rag/                             # parse / chunk / index / retrieve / generate / load / pipeline
│   │   └── graph/                       # Agent RAG LangGraph 引擎（rag_qa / runner / grading / compiled）
│   ├── integrations/                    # langchain / langgraph(checkpointer) / litellm / deepagents / generative / embeddings / rerank / chat
│   └── flow_runtime/                    # 流程节点 + compiler/（画布 LangGraph 编译器）+ graph_runner
```

4. §3.1 表下追加一行：`rag.graph` 子包职责见 specs/2026-09-22-miles-ai-internal-layering-design.md。

5. §5.2 的 import 示例块中，把 `from miles_ai.integrations.langchain.vectorstores import search_kb` 一行删除，并把 `from miles_ai.integrations.langchain.kb_retrieval import ...`（若有）改为 `from miles_ai.rag.retrieve.bindings import KbRetrievalBindings`；把 `from miles_ai.integrations.langgraph.compiler import ...`（若出现在该节）改为 `from miles_ai.flow_runtime.compiler import ...`。

> 改前先 `rg -n "integrations\.(langchain|langgraph)" docs/architecture/layering.md` 列出全部待改行，逐行核对后再改；该文件其他章节（§1/§2.1/§2.2/§4）涉及 `integrations` 作为 L3 的通用描述**不需要改**。

- [ ] **Step 5: 同步其余文档与前端注释中的旧模块路径**

以下 7 处是 `rg -n "integrations\.(langgraph\.(compiler|flow_runner|graph_analysis|grading|graphs|runner|constants|state)|langchain\.(kb_retrieval|vectorstores|visual_embeddings))"` 在 `docs/`（除 `docs/superpowers/`）与 `ui/` 下的**全部**命中，逐条替换：

| 文件:行 | 原文片段 | 改为 |
|---|---|---|
| `docs/guides/knowledge-base.md:150` | `miles_ai.integrations.langchain.vectorstores` | `miles_ai.rag.retrieve.multi_kb`（并删去该行对 `search_multi_kb` 壳的表述，改为直接描述多库合并排序） |
| `docs/architecture/technical-design.md:461` | `integrations.langgraph.flow_runner` | `flow_runtime.graph_runner` |
| `docs/architecture/technical-design.md:504` | `integrations.langgraph.runner` | `rag.graph.runner` |
| `docs/guides/flows.md:45` | `integrations.langgraph.compiler` | `flow_runtime.compiler` |
| `docs/guides/flows.md:68` | `integrations.langgraph.grading.evaluate_relevance` | `rag.graph.grading.evaluate_relevance` |
| `docs/features/flow-orchestration.md:92` | `integrations.langgraph.flow_runner` | `flow_runtime.graph_runner` |
| `ui/workbench/features/flows/lib/flow-nodes.ts:6` | `integrations.langgraph.compiler.SUPPORTED_CANVAS_NODE_TYPES` | `flow_runtime.compiler.SUPPORTED_CANVAS_NODE_TYPES` |

验证无残留：

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI
rg -n "integrations\.(langgraph\.(compiler|flow_runner|graph_analysis|grading|graphs|runner|constants|state)|langchain\.(kb_retrieval|vectorstores|visual_embeddings))" \
   --glob '!docs/superpowers/**' . | rg -v '^\./backend/(packages|tests)/'; echo "--- 期望：无输出"
```

> 前端改动仅注释文本，不触发 `prettier` 差异；改后跑 `make check-ui` 里的 `format-check-ui` 确认（若本机未装 UI 依赖可跳过，该步在 CI 覆盖）。

- [ ] **Step 6: spec 补「已实施」记录**

在 `docs/superpowers/specs/2026-09-22-miles-ai-internal-layering-design.md` 的 §14 修订记录追加：

```markdown
### 2026-09-22：已实施

Task 1–7 落地。与本文的两处偏差已按实施结论修正：
1. `integrations/langchain/__init__.py` **不删除**，改为仅 re-export 本子包 `chat_models`——删除会使该目录退化为 namespace package，且与 `integrations/*/__init__.py` 的既有 re-export 约定不一致。
2. `should_use_visual_image_embedding` 落在 `rag/pipeline/visual_policy.py`（非 §4.3 所写的 `rag/parse/upload_policy.py`）：它是入库时的视觉向量化决策，唯一消费者是 `rag/pipeline/ingest.py`，与「上传白名单」语义不同。

新增（本文未预见的必要产物）：`rag/graph/compiled.py` 与 `rag/pipeline/visual_policy.py` 两个模块；`.importlinter` 契约名 `ai-internal-layers`。
```

- [ ] **Step 7: 全绿门禁（复刻 CI）**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI
make check
```

Expected: `lint-backend` / `format-check-backend` / `layers-check`（8 kept）/ `openapi-check` / `test-backend`（`1517 passed`）全部通过。

- [ ] **Step 8: 提交**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI
git add -A
git commit -F- <<'EOF'
ci(ai): 用 import-linter 冻结 miles_ai 包内分层方向

包级 layers 契约只看到 miles_ai 一个节点，管不到包内子包方向，故 integrations
得以长期反向依赖 rag / flow_runtime。新增 ai-internal-layers 契约固化
flow_runtime → rag → integrations，并额外冻结 rag 对 flow_runtime 的引用
（该边为 0 且反向必成环）。

同时同步 layering.md 的目录结构与判据表。
EOF
git log --oneline -1
```

---

## 收尾验收（对照 spec §11）

- [ ] `.venv/bin/lint-imports` → `Contracts: 8 kept, 0 broken.`
- [ ] `rg -n "^\s*(from|import)\s+miles_ai\.(rag|flow_runtime)" packages/miles-ai/src/miles_ai/integrations` → 无输出
- [ ] 全仓 `rg -n "integrations\.(langgraph\.(compiler|flow_runner|graph_analysis|grading|graphs|runner|constants|state)|langchain\.(kb_retrieval|vectorstores|visual_embeddings))" --glob '!docs/superpowers/**' .` → **无输出**（`docs/superpowers/` 下的 spec/plan 属历史记录，保留原文不提改动）
- [ ] `make check` 全绿；`1517 passed`；OpenAPI 零漂移
- [ ] `miles_ai.integrations.{generative,embeddings,rerank,deepagents,litellm,chat,langchain}` 对外路径未变：`rg -c "miles_ai\.integrations\.(generative|embeddings|rerank|deepagents|litellm|chat|langchain)\." packages tests | awk -F: '{s+=$2} END {print s}'` 与基线一致
- [ ] 新增文件均 ≤ 500 行且带中文 docstring：`wc -l packages/miles-ai/src/miles_ai/rag/graph/*.py packages/miles-ai/src/miles_ai/rag/pipeline/visual_policy.py packages/miles-ai/src/miles_ai/integrations/embeddings/policy.py`
- [ ] 手工冒烟：Agent RAG 对话（绑定 KB 的智能体发起一次对话，确认走 LangGraph 且多轮 `thread_id` 生效）；画布流程调试运行（`FlowService.run` 或工作台流程调试，确认编译预览与执行正常）
