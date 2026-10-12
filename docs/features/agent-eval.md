# Agent 评测（Eval）后端 MVP

> 类型：功能说明 | 状态：已实现（API only） | 代码：`miles_portal.tenant.eval` / `miles_core.models.eval`

## 能力

- 数据集 / 用例 CRUD（`expected`: `exact` / `contains` / `contains_all` / `rubric`）
- 创建 run → Celery `run_eval_batch` 循环调用现有 `AgentService.chat`
- 规则打分；`auto`/`llm_judge` 可对 `rubric` 做 LLM judge
- 结果关联 `call_id` / `trace_id`；`summary` 聚合 passed/failed/errored

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

## 非目标（本批）

Workbench UI、确定性 replay、从 call-records 升格、跨 Agent 大盘。
