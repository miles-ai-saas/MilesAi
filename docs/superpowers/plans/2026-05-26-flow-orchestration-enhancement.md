# 流程编排增强 — 实施计划

> **归档：** 实施 checklist（2026-05-26）。**现网规格：** [features/flow-orchestration.md](../../features/flow-orchestration.md)

**日期：** 2026-05-26  
**设计文档：** [flow-orchestration-enhancement.md](../../architecture/flow-orchestration-enhancement.md)  
**状态：** 归档（Phase 1–4 已实现）

---

## 执行顺序

按 Phase 0 → 4 顺序合并 PR，每 Phase 可独立验收。

| Phase | 主题 | 预估 | 依赖 |
|-------|------|------|------|
| 0 | 设计文档与索引 | 已完成 | — |
| 1 | 工作台可用性 | 2–3d | Phase 0 |
| 2 | PlatformTool + 编译体验 | 1–2d | Phase 1 |
| 3 | RAG 增强节点 + 模板 | 2d | Phase 1 |
| 4 | 版本历史等 P2 | 按需 | Phase 1 |

---

## Phase 1 任务分解

### 后端

1. `FlowRunRequest` 增加 `kb_ids: list[UUID]`
2. `FlowService.run` → `RunContext.kb_ids`
3. （可选）`compile_preview` errors 结构化 — 若 Phase 1 时间紧可挪 Phase 2

### 前端

1. 新增 `lib/flow-node-schemas.ts`（字段 + Handle 表）
2. 新增 `components/flow/FlowNodeInspector.tsx`（Sheet）
3. `FlowCanvas`：选中节点 → Inspector；`updateNodeData`
4. 重构 `FlowNodeCard`：按 `NODE_HANDLES` 渲染 Handle
5. 新增 `components/flow/FlowRunPanel.tsx`；编辑页接入 `listKbs` + `runFlow`
6. 编辑页 `getFlow` 加载名称；「插入 RAG 模板」按钮
7. `lib/chains.ts` §6 登记新文件

### 验证

```bash
cd backend && pytest tests/test_langgraph_compiler.py tests/test_langgraph_parallel.py -q
# 手动：编辑页选 KB → 运行 → steps 含 flow_node
```

---

## Phase 2 任务分解

1. Inspector 内 `PlatformTool`：`api.listToolsCatalog` 选 slug + 动态 params
2. `FlowCanvas.onConnect`：非法 handle  toast 警告（不阻止）
3. `validate_graph_for_compile`：errors 带 `node_id`

---

## Phase 3 任务分解

### 后端

1. `relevance_grade` handler（复用 `grading.py`）
2. `static_response` handler
3. `registry` 注册；`graph_analysis` 扩展三路条件
4. `templates/rag_flow_with_grade.json`
5. `tests/test_relevance_grade_node.py`、`test_compile_grade_graph.py`

### 前端

1. 调色板 + `DEFAULT_DATA` + Inspector 表单
2. `FlowNodeCard` 三路 source handle（good/poor/none）
3. `RAG_TEMPLATE_WITH_GRADE` + 插入模板

---

## Phase 4 ✅

- `GET /flows/{id}/versions`、`GET /flows/{id}/versions/{v}` + `FlowVersionHistoryDialog`
- 恢复 = `saveFlowGraph` + remark `恢复自 vN`
- `LLMCall.max_tokens`、`KnowledgeSearch.retrieval_mode`（default/vector/hybrid）

---

## 完成定义（Phase 1）

- [x] 不修改 JSON 文件即可配置 PromptTemplate / KnowledgeSearch / ConditionBranch
- [x] 调试运行可选择至少一个 KB 且检索非空（有文档时）
- [x] 运行结果展示 `steps` 列表
- [x] 现有编译测试全部通过
