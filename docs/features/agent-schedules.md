# 智能体定时任务

**状态：** 已实现  
**技术栈：** FastAPI · Celery Beat · 标准 5 段 Cron · 对话工作台 UI

---

## 1. 背景与目标

对话工作台右侧「定时」Tab 允许用户为当前智能体配置**按计划自动发送消息**的定时任务。触发时调用既有 `AgentService.chat`，走合规、Hook 与完整编排链路。

### 1.1 交付范围

- 标准 **5 段 Cron**（`分 时 日 月 周`），与 `celery.schedules.crontab` / `croniter` 一致
- 每条任务：消息内容（≤500 字）、Cron 表达式、启用/禁用
- REST API：按智能体嵌套 CRUD（`/agents/{id}/schedules`）
- Celery Beat 每分钟扫描到期任务并异步执行
- 前端：任务列表 Panel + 创建/编辑 `lg` 弹窗（Cron 可视化选择器 + 常用预设）

### 1.2 明确不做

- Quartz 6/7 段 Cron（无秒字段、无 `?` 语法）
- 秒级 / `interval` 调度（Celery `crontab` 最小粒度为分钟）
- 定时任务执行历史 UI（v1 仅更新 `last_run_at`；可后续对接任务中心）
- 跨智能体批量调度

---

## 2. 数据模型

### 2.1 表 `agt_schedules`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID | 主键 |
| `tenant_id` | UUID | 租户隔离 |
| `agent_id` | UUID | 目标智能体 |
| `content` | TEXT | 触发时作为 `ChatRequest.query`，≤500 字 |
| `cron` | VARCHAR(64) | 5 段 Cron，如 `0 8 * * 1-5` |
| `enabled` | BOOLEAN | 是否参与 Beat 扫描 |
| `last_run_at` | TIMESTAMPTZ NULL | 上次执行时间 |
| `next_run_at` | TIMESTAMPTZ NULL | 下次计划执行（创建/更新/tick 时计算） |
| `created_by` | UUID NULL | 创建人，Worker 构造 `TenantContext` |
| `created_at` / `updated_at` / `deleted_at` | TIMESTAMPTZ | 时间戳与软删 |

索引：`tenant_id`、`agent_id`、`next_run_at`（Beat 扫描）。

### 2.2 Cron 约定

**格式：** `minute hour day_of_month month day_of_week`（空格分隔，5 段）

| 段 | 范围 | 示例 |
|----|------|------|
| 分 | 0–59 | `0`、`*/5` |
| 时 | 0–23 | `8`、`*` |
| 日 | 1–31 | `*`、`1` |
| 月 | 1–12 | `*` |
| 周 | 0–6（0=周日） | `1-5`（工作日）、`1`（周一） |

校验：`croniter` 解析；创建/更新时写入 `next_run_at`。

---

## 3. API

前缀：`/api/v1/agents/{agent_id}/schedules`  
权限：`agent:read`（列表/详情）· `agent:write`（创建/更新/删除）

### 3.1 列表

```
GET /agents/{agent_id}/schedules?page=1&size=20
→ PageResult<AgentScheduleOut>
```

### 3.2 创建

```
POST /agents/{agent_id}/schedules
Body: { "content": string, "cron": string, "enabled": boolean }
→ AgentScheduleOut
```

### 3.3 更新 / 删除

```
PATCH /agents/{agent_id}/schedules/{schedule_id}
DELETE /agents/{agent_id}/schedules/{schedule_id}
```

### 3.4 响应体 `AgentScheduleOut`

```json
{
  "id": "uuid",
  "agent_id": "uuid",
  "content": "每日巡检摘要",
  "cron": "0 8 * * 1-5",
  "cron_description": "工作日 08:00 执行",
  "enabled": true,
  "last_run_at": "2026-05-25T00:00:00Z",
  "next_run_at": "2026-05-26T00:00:00Z",
  "created_at": "...",
  "updated_at": "..."
}
```

`cron_description` 由服务端 `describe_cron()` 生成，供列表展示。

---

## 4. 调度与执行

### 4.1 架构

```
Celery Beat (60s)
    → tick_agent_schedules
        → 查 next_run_at <= now 且 enabled
        → 预写 next_run_at（防重复触发）
        → run_agent_schedule.delay(id)

Celery Worker
    → run_agent_schedule(id)
        → asyncio.run + AsyncSession
        → TenantContext(created_by)
        → AgentService.chat(agent_id, ChatRequest)
        → 更新 last_run_at
```

### 4.2 启动命令

```bash
# Worker（已有）
python cli.py worker

# Beat
python cli.py beat
```

Docker 全栈：`docker-compose.yml` 已含 `beat` 服务（与 `worker` 同镜像）。本地仅中间件时需手动起 Beat。

### 4.3 执行上下文

- `conversation_id = f"schedule:{schedule.id}"`，隔离 LangGraph checkpoint
- `TenantContext` 使用 `created_by` 用户；权限集含 `agent:read`
- 智能体 `status != enabled` 时 `chat` 抛错，任务失败不重试（v1）

### 4.4 级联删除

`before_delete_agent` 软删该智能体下全部 schedules。

---

## 5. 前端

### 5.1 入口

- 对话工作台右侧栏 Tab「定时」→ `AgentSchedulePanel`
- URL：`/workbench/agents/chat?agent={id}&tab=schedule`

### 5.2 列表 Panel

- 加载态 / 错误重试（对齐 `AgentStatsPanel`）
- `ResourceItemCard`：内容摘要、Cron 人话、下次执行、启用徽章
- 新建 / 编辑 → `AgentScheduleDialog`（`ResourceDialog size="lg"`）
- 删除 → `ConfirmDialog`

### 5.3 弹窗表单

| 字段 | 组件 |
|------|------|
| 输入内容 * | textarea，500 字计数 |
| 执行策略 * | 5 字段 `CronFieldPicker` |
| Cron 表达式 | 只读 `CronExpressionPreview` |
| 常用 | `CronPresetLinks` |
| 状态 | `ToggleSwitch` |

工具模块：`ui/workbench/lib/cron-celery.ts`（build / parse / describe / validate / presets）。

### 5.4 文件清单

```
ui/workbench/lib/cron-celery.ts
ui/workbench/lib/types.ts                    # AgentSchedule
ui/workbench/lib/api.ts                      # schedule CRUD
ui/workbench/components/ui/ToggleSwitch.tsx
ui/workbench/components/agent/CronFieldPicker.tsx
ui/workbench/components/agent/CronPresetLinks.tsx
ui/workbench/components/agent/CronExpressionPreview.tsx
ui/workbench/components/agent/AgentScheduleDialog.tsx
ui/workbench/components/agent/AgentSchedulePanel.tsx
ui/workbench/components/agent/AgentWorkbenchOverlay.tsx
ui/workbench/components/agent/agent-workbench-tabs.ts
```

---

## 6. 后端文件清单

```
backend/app/models/agent_schedule.py
backend/app/common/cron.py
backend/app/tenant/agents/schemas/schedule.py
backend/app/tenant/agents/services/schedule.py
backend/app/tenant/agents/views/agents.py      # 路由追加
backend/app/workers/tasks/agent_schedule.py
backend/app/workers/app.py                     # beat_schedule
backend/app/deletion/cascade.py                # before_delete_agent
backend/cli.py                                 # beat 子命令
backend/tests/test_cron.py
```

依赖：`croniter>=2.0.0`（`pyproject.toml`）。

---

## 7. 测试计划

1. **单元**：`validate_cron` / `compute_next_run` / `describe_cron`（合法/非法表达式）
2. **API**：创建 schedule → 列表可见 → PATCH enabled → DELETE
3. **Worker**：mock `AgentService.chat`，验证 tick 选中到期任务
4. **前端**：Cron 选择器与预设生成正确 5 段表达式；保存后列表刷新

---

## 8. 参考

- [frontend/design.md](../frontend/design.md) §5.7 弹窗选型
- [platform-agents.md](../guides/platform-agents.md) 智能体编排
- Celery Beat：https://docs.celeryq.dev/en/stable/userguide/periodic-tasks.html
