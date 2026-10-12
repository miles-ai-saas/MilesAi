# Agent 评测（Eval）

> 类型：功能说明 | 状态：已实现（含二期升格 · 三期 rubric UI） | 代码：`miles_portal.tenant.eval` / `ui/workbench/features/eval`

## 能力

- 数据集 / 用例 CRUD（`expected`: `exact` / `contains` / `contains_all` / `rubric`）
- 创建 run → Celery `run_eval_batch` 循环调用现有 `AgentService.chat`
- 规则打分；`auto`/`llm_judge` 可对 `rubric` 做 LLM judge
- 结果关联 `call_id` / `trace_id`；`summary` 聚合 passed/failed/errored
- 工作台 `/workbench/eval`：数据集 · 运行 · 运行详情（`?run=`）；运行中自动轮询
- **二期**：从成功调用记录升格用例；运行详情 `call_id` 深链打开调用详情
- **三期**：用例表单暴露 `rubric`（评分标准）；运行创建提示与打分模式对齐

## API（`/api/v1/eval`）

| 方法 | 路径 | 权限 |
|------|------|------|
| GET/POST | `/datasets` | agent:read / agent:write |
| GET/PATCH/DELETE | `/datasets/{id}` | 同上 |
| GET/POST | `/datasets/{id}/cases` | 同上 |
| POST | `/datasets/{id}/cases/from-call-record` | agent:write |
| PATCH/DELETE | `/datasets/{id}/cases/{case_id}` | agent:write |
| GET/POST | `/runs` | agent:read / agent:write |
| GET | `/runs/{id}` | agent:read |
| POST | `/runs/{id}/start` | agent:write |
| GET | `/runs/{id}/items` | agent:read |

### 升格用例（`POST .../cases/from-call-record`）

Body：`agent_id`、`call_id`；可选 `name`、`expected`、`prefer_session_text`（默认 `true`）。

- 仅 `status=success` 的调用可升格
- 优先从会话消息取问答全文，否则退回调用记录 preview
- 未传 `expected` 时默认 `{"contains": <答案>}`；并写入 `expected._source`（`call_id` / `agent_id` / `trace_id`），打分忽略未知键

## UI

- 单页三 Tab；观测导航「评测」
- Cases 表单：`exact` / `contains` / `rubric` / 不校验（不编辑原始 JSON）；编辑时保留 `_source`
- 新建运行：打分模式说明（规则 vs auto / LLM Judge）
- 智能体调用详情：成功记录可「升格为评测用例」
- 运行详情 Items：`call_id` 可点击打开调用详情对话框

## 非目标（本批）

确定性 replay、跨 Agent 大盘、CSV 导入、LLM judge 高级配置（独立 judge 模型 / temperature / 模板库）、失败调用升格。
