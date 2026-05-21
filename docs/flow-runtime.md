# 流程运行时（flow_runtime）

> 本文说明 AiEngine **实际落地**的流程编排实现，避免与第三方 [Langflow](https://github.com/langflow-ai/langflow) 产品混淆。

## 命名对照

| 名称 | 是什么 | 路径 / 包 |
|------|--------|-----------|
| **flow_runtime** | 本仓库内置的 DAG 执行引擎 | `backend/app/flow_runtime/` |
| **BuiltinFlowRuntime** | 默认运行时，按 `graph_json` 拓扑执行节点 | `builtin_runtime.py` |
| **OptionalLangflowAdapter** | 可选：检测到 PyPI 已安装 `langflow` 时的适配层（当前仍委托 Builtin） | `optional_langflow_adapter.py` |
| **Langflow（第三方）** | 开源 Python 产品，**非**本仓库模块 | `pip install langflow`（可选） |
| **@langflow/flow-builder** | 官方前端画布 npm 包（**未采用**，npm 未发布） | — |
| **React Flow** | 当前前端画布 | `@xyflow/react`，`frontend/components/flow/` |

## 数据流

```
前端 FlowCanvas (React Flow)
    → PUT /api/v1/flows/{id}/graph  (graph_json)
    → PostgreSQL flow_versions

调试 / 智能体执行
    → get_flow_runtime()  →  BuiltinFlowRuntime（默认）
    → app/flow_runtime/nodes/registry.py 执行各节点类型
```

## 目录结构

```
backend/app/flow_runtime/
├── builtin_runtime.py          # 默认 DAG 执行器
├── runtime_factory.py          # get_flow_runtime()
├── optional_langflow_adapter.py # 可选第三方 langflow 包
├── types.py                    # FlowGraph, RunContext, RunResult
├── templates/rag_flow.json     # RAG 默认模板
└── nodes/
    ├── registry.py             # 节点注册表（扩展入口）
    ├── io_nodes.py
    ├── rag_nodes.py
    └── llm_nodes.py
```

业务 API（CRUD、发布、run）在 `app/app_tenant/flows/`，**不要**与 `flow_runtime` 混为一谈。

## 扩展节点

在 `nodes/registry.py` 的 `NODE_REGISTRY` 中注册 handler，并在前端 `frontend/lib/flow-nodes.ts` 增加对应节点类型（若需在画布展示）。

## 可选对接 Langflow 产品

若未来需要复用 Langflow 生态组件：

1. `pip install langflow==<锁定版本>`
2. 在 `optional_langflow_adapter.py` 的 `run()` 中接入官方 API
3. `flows.external_flow_id` 字段用于与外部 Flow ID 映射（迁移 `006`）

**当前无需安装 Langflow 即可完成 P2 联调。**

## 相关文档

- [README.md](../README.md) — 快速启动与 API
- [技术方案.md](./技术方案.md) §10 — 架构级说明
