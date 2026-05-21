# 流程运行时（flow_runtime）

> 画布 `graph_json` **仅由 LangGraph 编译执行**；`flow_runtime` 提供节点 handler 与类型，不依赖第三方 Langflow 产品。

## 命名对照

| 名称 | 是什么 | 路径 |
|------|--------|------|
| **flow_runtime** | 流程节点注册表 + `get_flow_runtime()` | `backend/app/flow_runtime/` |
| **LangGraph** | `graph_json` → `StateGraph` → `ainvoke` | `ai_stack/langgraph/` |
| **React Flow** | 前端画布 | `@xyflow/react` |

需求文档中的「Langflow」指可视化编排能力；本仓库落地为 **React Flow + LangGraph**，非 PyPI `langflow` 包。

## 数据流

```
前端 FlowCanvas (React Flow)
    → PUT /api/v1/flows/{id}/graph  (graph_json)
    → PostgreSQL flow_versions

调试 / 智能体执行
    → get_flow_runtime().run(graph_json, ctx)
    → LangGraph（并行 / 条件分支 / 扇入）
    → flow_runtime.nodes.registry
```

## 目录结构

```
backend/app/flow_runtime/
├── runtime_factory.py      # get_flow_runtime() → LangGraphFlowRuntime
├── types.py                # FlowGraph, RunContext, RunResult
├── templates/rag_flow.json
└── nodes/
    ├── registry.py
    ├── io_nodes.py
    ├── rag_nodes.py
    ├── llm_nodes.py
    └── control_nodes.py    # ConditionBranch, ParallelJoin

backend/app/ai_stack/langgraph/
├── compiler.py
├── flow_runner.py          # run_flow_graph()
└── graph_analysis.py
```

## 编译与运行

- DAG 校验（无环、节点类型、条件节点 true/false 出边）
- 不可编译 → `400` + `errors`
- 预览：`POST /api/v1/flows/{id}/compile`
- 详见 [flow-langgraph-compiler.md](./flow-langgraph-compiler.md)

## 扩展节点

1. `nodes/registry.py` 注册 handler  
2. 前端 `frontend/lib/flow-nodes.ts` 增加调色板项  

## 与智能体

| 场景 | 路径 |
|------|------|
| 绑定 `published_flow_id` | LangGraph 画布 |
| 仅绑知识库 | RAG LangGraph 或 `legacy` 线性 RAG |
| 绑子智能体 | DeepAgents 规划 |

## 历史说明

- 曾存在 `BuiltinFlowRuntime` 自研调度器 → 已移除，统一 LangGraph  
- 曾存在 `OptionalLangflowAdapter` 对接第三方产品 → 已移除，无 `langflow` 依赖  

`flow_flows.external_flow_id` 字段仍保留于数据库，当前运行时未使用，仅作预留（迁移 `008` 补齐；`006` 曾误用旧表名 `flows`）。
