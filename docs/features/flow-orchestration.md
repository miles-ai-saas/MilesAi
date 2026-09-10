# 流程编排

**日期：** 2026-05-27  
**状态：** 已实现  
**PRD 对照：** 模块4 可视化流程编排  
**架构：** [technical-design.md §9](../architecture/technical-design.md#9-流程编排) · [flows.md](../guides/flows.md)

---

## 1. 背景与目标

**React Flow** 画布编辑 `graph_json`，**flow_runtime** 注册节点处理器，**integrations.langgraph** 编译为 LangGraph 执行。流程可发布版本、调试运行、编译诊断；智能体绑定 `published_flow_id` 后对话走同一执行链。

### 1.1 交付范围

- 流程 CRUD、保存画布、版本列表、发布
- `POST …/run` 调试、`POST …/compile` DAG 校验
- 17 类节点（含 SubFlow / Loop / 合规 / 媒体 / 生图·生视频）
- 流程模板 `GET /flows/templates`
- 标签筛选；前端 `/workbench/flows/[id]/edit`

### 1.2 明确不做

- iframe 嵌入画布

---

## 2. 数据模型

| 表 | 说明 |
|----|------|
| `flow_flows` | 流程元数据、`current_version` |
| `flow_versions` | `version` + `graph_json` JSONB |

发布：递增 version，智能体引用已发布版本的 `graph_json`。

---

## 3. 已注册节点

| 类型 | 说明 |
|------|------|
| `TextInput` / `TextOutput` | 文本入出 |
| `KnowledgeSearch` | KB 检索 |
| `RelevanceGrade` | 相关性判定 |
| `StaticResponse` | 静态回复 |
| `PromptTemplate` | 提示词模板 |
| `LLMCall` | 大模型调用（支持识图 media） |
| `PlatformTool` | 平台工具 |
| `ConditionBranch` | 条件分支 |
| `ParallelJoin` | 并行汇聚 |
| `SubFlow` | 调用同租户已发布流程（`published`/`pinned`；环校验、最大嵌套 3 层） |
| `LoopNode` | 循环（最大 100 次迭代） |
| `ComplianceCheck` | 合规扫描 |
| `OcrExtract` | OCR 文本抽取 |
| `AudioTranscribe` | 音频转写（Whisper） |
| `ImageGenerate` / `VideoGenerate` | 生图/生视频（默认异步 job） |

注册表：`backend/app/flow_runtime/nodes/registry.py`。

---

## 4. API

前缀：`/api/v1/flows`  
权限：`flow:read` · `flow:write`

```
GET  /flows/meta
GET  /flows/templates
GET  /flows?tag_ids=
POST /flows
GET  /flows/{id}
PATCH /flows/{id}
DELETE /flows/{id}
GET  /flows/{id}/graph              # 当前版本 graph
PUT  /flows/{id}/graph              # 保存 → 新版本或覆盖草稿
GET  /flows/{id}/versions
GET  /flows/{id}/versions/{n}
POST /flows/{id}/publish
POST /flows/{id}/run                # FlowRunRequest
POST /flows/{id}/compile            # DAG / 并行层报告
```

---

## 5. 执行链路

```
PUT /graph → flow_versions.graph_json
POST /run  → get_flow_runtime().run()
    → flow_runtime.runtime_factory
    → integrations.langgraph.flow_runner
    → 节点 handler → rag / integrations / tools
POST /compile → 校验环、未知节点、ParallelJoin 层
```

智能体：`published_flow_id` + 已发布版本 → `AgentService.chat` 同链。

---

## 6. 前端

```
ui/workbench/app/workbench/flows/page.tsx
ui/workbench/app/workbench/flows/[id]/edit/page.tsx
ui/workbench/components/flow/FlowCanvas.tsx
```

画布节点类型与 `flow_runtime/constants.py` 对齐。

---

## 7. 后端文件清单

```
backend/app/models/flow.py
backend/app/tenant/flows/
backend/app/flow_runtime/
backend/app/integrations/langgraph/
backend/app/flow_runtime/templates/rag_flow.json
```

---

## 8. 测试计划

1. 创建流程 → 拖节点 save graph → compile 无 error
2. publish → agent 绑定 → chat 走流程输出
3. KnowledgeSearch + LLMCall 调试 run 返回 steps
4. ImageGenerate 异步 → generative_jobs + 调试面板 artifact

---

## 9. 参考

- [multimodal-capabilities.md](../product/multimodal-capabilities.md)
- [flows.md](../guides/flows.md)
