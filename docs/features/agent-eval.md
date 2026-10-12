# Agent 评测（Eval）

> 类型：功能说明 | 状态：已实现（含升格 · rubric · CSV · Judge 模型） | 代码：`miles_portal.tenant.eval` / `ui/workbench/features/eval`

## 能力

- 数据集 / 用例 CRUD（`expected`: `exact` / `contains` / `contains_all` / `rubric`）
- **CSV 批量导入**用例（表头 `query,name,expected_mode,expected_value`）
- 创建 run → Celery `run_eval_batch` 循环调用现有 `AgentService.chat`
- 规则打分；`auto`/`llm_judge` 可对 `rubric` 做 LLM judge
- 可选 **Judge 模型**（`options.judge_model_config_id`，默认回退智能体绑定模型）
- 结果关联 `call_id` / `trace_id`；`summary` 聚合 passed/failed/errored
- 工作台 `/workbench/eval`：数据集 · 运行 · 运行详情（`?run=`）；运行中自动轮询
- **升格**：从调用记录升格用例（**成功 / 失败均可**）；运行详情 `call_id` 深链打开调用详情
- 用例表单暴露 `rubric`；运行创建提示与打分模式对齐

## API（`/api/v1/eval`）

| 方法 | 路径 | 权限 |
|------|------|------|
| GET/POST | `/datasets` | agent:read / agent:write |
| GET/PATCH/DELETE | `/datasets/{id}` | 同上 |
| GET/POST | `/datasets/{id}/cases` | 同上 |
| POST | `/datasets/{id}/cases/from-call-record` | agent:write |
| POST | `/datasets/{id}/cases/import-csv` | agent:write |
| PATCH/DELETE | `/datasets/{id}/cases/{case_id}` | agent:write |
| GET/POST | `/runs` | agent:read / agent:write |
| GET | `/runs/{id}` | agent:read |
| POST | `/runs/{id}/start` | agent:write |
| GET | `/runs/{id}/items` | agent:read |

### 升格用例（`POST .../cases/from-call-record`）

Body：`agent_id`、`call_id`；可选 `name`、`expected`、`prefer_session_text`（默认 `true`）。

- **成功 / 失败 / blocked / error** 均可升格（须有可用用户问题文本）
- 优先从会话消息取问答全文，否则退回调用记录 preview
- 有答案时默认 `{"contains": <答案>}`；失败且无答案时 expected 留空待补
- 写入 `expected._source`（`call_id` / `agent_id` / `trace_id` / `call_status`）

### CSV 导入（`POST .../cases/import-csv`）

Body：`{ "csv_text": "..." }`。表头至少含 `query`；可选 `name`、`expected_mode`、`expected_value`（或快捷列 `contains`/`exact`/`rubric`）。`contains_all` 用 `|` 分隔。单次最多 500 行。

### 创建运行

Body 可选 `judge_model_config_id`：写入 `eval_runs.options`，批跑时优先于智能体模型做 LLM Judge。

## UI

- 单页三 Tab；观测导航「评测」
- Cases：表单 + **上传 CSV**；编辑保留 `_source`
- 新建运行：打分模式 + 可选 Judge 模型
- 调用详情：有问题文本即可「升格为评测用例」
- 运行详情 Items：`call_id` 可点击打开调用详情对话框

## 非目标（后续）

确定性 replay、跨 Agent 大盘、Judge temperature / 模板库、多级历史对比。
