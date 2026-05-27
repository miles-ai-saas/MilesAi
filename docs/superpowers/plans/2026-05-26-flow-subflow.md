# 画布子流程（SubFlow）— 实施计划占位

> **归档：** 未开工占位（2026-05-26）。**目标规格：** [flow-subflow-design.md](../../architecture/flow-subflow-design.md)（**未实施**，无 features 文档）

**日期：** 2026-05-26  
**立项规格：** [flow-subflow-design.md](../../architecture/flow-subflow-design.md)  
**状态：** 归档 · **未开工**

---

## 前置条件

- [flow-orchestration-enhancement](2026-05-26-flow-orchestration-enhancement.md) Phase 1–4 已在生产或预发稳定运行 ≥ 2 周
- 产品确认 §3 版本策略与合规双倍 Hook 策略

---

## 任务清单（实施时启用）

### Phase A — 运行时

- [ ] `flow_runtime/nodes/subflow_nodes.py` + `registry`
- [ ] `resolve_subflow_graph`（published / pinned）
- [ ] `build_child_context` + `input_mapping`
- [ ] `steps` 嵌套结构约定与 `FlowRunResponse` 文档

### Phase B — 编译

- [ ] `validate_graph_for_compile`：`subflow_*` errors
- [ ] 直接环检测（主图内 SubFlow 引用链）

### Phase C — 前端

- [ ] `NODE_PALETTE` / `FlowNodeInspector` / `FlowNodeCard`
- [ ] 已发布流程选择器
- [ ] 调试 steps 子流程折叠

### Phase D — 增强（可延后）

- [ ] 最大嵌套深度 3
- [ ] `GET /flows/{id}/subflow-deps`

---

## 完成定义

见立项规格 [§8 验收标准](../../architecture/flow-subflow-design.md#8-验收标准实施完成后)。
