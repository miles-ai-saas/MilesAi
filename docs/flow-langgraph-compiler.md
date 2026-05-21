# 画布 → LangGraph 编译器（P6-3）

> 状态：**画布唯一执行引擎**（已移除 BuiltinFlowRuntime）

## 能力

将 React Flow 保存的 `graph_json` 校验并编译为 LangGraph `StateGraph`：

- **并行**：同一节点多条出边 → LangGraph 多子节点并行执行；多入边 → 扇入汇合后再执行下游
- **条件**：`ConditionBranch` 节点通过 `sourceHandle: true | false` 走不同分支
- 节点逻辑仍在 `flow_runtime.nodes`，由编译器包装为 LangGraph 节点

### 支持节点类型

| 类型 | 说明 |
|------|------|
| `TextInput` / `ChatInput` | 入口输入 |
| `KnowledgeSearch` | 知识库检索 |
| `ConditionBranch` | 条件分支（见下） |
| `ParallelJoin` | 并行分支结果合并 |
| `PromptTemplate` | 提示词模板 |
| `LLMCall` | 大模型调用 |
| `TextOutput` / `ChatOutput` | 输出 |

### ConditionBranch 模式（`data.mode`）

| mode | 说明 |
|------|------|
| `has_hits` | 上游 `hits` 列表非空 → true |
| `score_above` | 检索最高分 ≥ `threshold`（默认 0.35） |
| `text_contains` | 上游文本包含 `keyword` |
| `not_empty` | 上游文本非空 |

连线约定：从条件节点拉出两条边，`sourceHandle` 分别为 **`true`**（是）与 **`false`**（否）。

### ParallelJoin（`data.merge_strategy`）

| strategy | 说明 |
|----------|------|
| `dict` | 合并为 `{handle: value}` 字典（默认） |
| `concat_text` | 文本拼接 |
| `first` | 取第一个分支 |

并行汇合也可不用该节点：下游节点多条入边时，LangGraph / Builtin 会等待所有前驱完成（扇入）。

### 启用方式

| 场景 | 行为 |
|------|------|
| 智能体绑定已发布流程 | 自动经 `get_flow_runtime()` → LangGraph |
| 流程调试运行 | `POST /flows/{id}/run`（无需再传 `use_langgraph`） |
| 图不可编译 | `400`，可先调 `compile` 查看 `errors` |

### 编译预览

```
POST /api/v1/flows/{flow_id}/compile
```

响应含 `execution_layers`（可并行层）、`parallel_groups`、`conditional_nodes`。

示例：

```json
{
  "compilable": true,
  "engine": "langgraph",
  "execution_layers": [["in"], ["a", "b"], ["join"], ["out"]],
  "parallel_groups": [["a", "b"]],
  "conditional_nodes": [],
  "errors": []
}
```

## 模块

- `app/ai_stack/langgraph/compiler.py` — 图编译与运行
- `app/ai_stack/langgraph/graph_analysis.py` — 环检测、执行层、条件边
- `app/flow_runtime/nodes/control_nodes.py` — 控制节点实现
- `app/flow_runtime/runtime_factory.py` — `get_flow_runtime()`

## 限制

- 仍要求 **有向无环图（DAG）**；存在环则不可编译
- 条件分支后 **不要** 让两条分支再汇入同一依赖「双分支都完成」的节点（会死锁）；应各自输出或使用 `ParallelJoin` 仅接已执行分支
- 画布单次 run 默认不挂 Redis checkpoint

## 示例拓扑

**并行：**

```
TextInput ─┬─► PromptTemplate A ─┐
           └─► PromptTemplate B ─┼─► ParallelJoin ─► TextOutput
```

**条件：**

```
TextInput ─► KnowledgeSearch ─► ConditionBranch ─true─► PromptTemplate ─► TextOutput
                                    └─false─► PromptTemplate（兜底）─► TextOutput
```

## 相关文档

- [flow-runtime.md](./flow-runtime.md)
- [langgraph-rag-workflow.md](./langgraph-rag-workflow.md)
