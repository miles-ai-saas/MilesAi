# Agent 评测（Eval）

> 类型：功能说明 | 状态：已实现（API + Workbench UI） | 代码：`miles_portal.tenant.eval` / `ui/workbench/features/eval`

## 能力

- 数据集 / 用例 CRUD（`expected`: `exact` / `contains` / `contains_all` / `rubric`）
- 创建 run → Celery `run_eval_batch` 循环调用现有 `AgentService.chat`
- 规则打分；`auto`/`llm_judge` 可对 `rubric` 做 LLM judge
- 结果关联 `call_id` / `trace_id`；`summary` 聚合 passed/failed/errored
- 工作台 `/workbench/eval`：数据集 · 运行 · 运行详情（`?run=`）；运行中自动轮询

## API（`/api/v1/eval`）

| 方法 | 路径 | 权限 |
|------|------|------|
| GET/POST | `/datasets` | agent:read / agent:write |
| GET/PATCH/DELETE | `/datasets/{id}` | 同上 |
| GET/POST | `/datasets/{id}/cases` | 同上 |
| PATCH/DELETE | `/datasets/{id}/cases/{case_id}` | agent:write |
| GET/POST | `/runs` | agent:read / agent:write |
| GET | `/runs/{id}` | agent:read |
| POST | `/runs/{id}/start` | agent:write |
| GET | `/runs/{id}/items` | agent:read |

## UI 一期范围

- 单页三 Tab；观测导航「评测」
- Cases 表单仅暴露 `exact` / `contains`（不编辑 JSON）
- Items 表展示 passed / score / latency / `call_id` 文本（无 call-records 深链）

## 非目标（本批）

确定性 replay、从 call-records 升格、跨 Agent 大盘、CSV 导入、LLM judge 高级配置 UI。
