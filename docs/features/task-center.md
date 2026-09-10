# 任务中心

**日期：** 2026-05-27  
**状态：** 已实现  
**PRD 对照：** 模块8 异步任务中心  
**架构：** [technical-design.md §8](../architecture/technical-design.md#8-异步任务)

---

## 1. 背景与目标

工作台 **任务中心**（`/workbench/tasks`）聚合租户可见的异步作业，分两个 Tab：

| Tab | 数据源 | 典型场景 |
|-----|--------|----------|
| **后台任务** | `task_records`（Celery 镜像） | 知识库文档入库 `ingest_document` |
| **生成任务** | `generative_jobs` | 智能体/流程/API 触发的生图、生视频 |

智能体 **定时任务**（`agt_schedules`）不在任务中心展示，走独立「定时」Panel，见 [agent-schedules.md](./agent-schedules.md)。

### 1.1 交付范围

- REST：`GET /tasks` 分页、详情、取消、重试（仅入库）
- REST：`GET /generative/jobs` 分页、详情、取消、重试、SSE 进度
- 前端：双 Tab 列表、状态筛选、详情弹窗、生成任务进度与关联 Celery 记录跳转
- Worker：入库 / 生图 / 生视频 / 定时 chat 四类 Celery 任务

### 1.2 明确不做

- Flower 嵌入工作台（仍用独立 `:5555` 服务）
- 智能体 schedule 执行历史 UI（v1 仅 `last_run_at`）
- 跨租户任务聚合

---

## 2. 数据模型

### 2.1 表 `task_records`

Celery 任务在租户侧的镜像记录，主要由 **文档入库** 写入。

| 字段 | 说明 |
|------|------|
| `id` | UUID 主键 |
| `tenant_id` | 租户隔离 |
| `celery_task_id` | Celery 任务 ID |
| `task_name` | 如 `app.workers.tasks.ingest.ingest_document` |
| `status` | `pending` / `running` / `success` / `failed` / `cancelled` |
| `resource_type` / `resource_id` | 关联资源（如 `kb_document`） |
| `fail_reason` | 失败原因 |
| `created_by` | 创建人 |

### 2.2 表 `generative_jobs`

生图/生视频异步任务专用表（与 `task_records` 并行，生成 Worker 也会同步 Celery 状态到 `task_records`）。

| 字段 | 说明 |
|------|------|
| `kind` | `image` \| `video` |
| `status` | `pending` / `running` / `success` / `failed` / `cancelled` |
| `source` | `agent_tool` / `flow_node` / `api` 等 |
| `source_ref_type` / `source_ref_id` | 追溯智能体、流程运行等 |
| `params` / `result` | JSONB 请求参数与结果（含 `attachment_id`） |
| `progress_message` / `progress_percent` | SSE 推送用 |
| `celery_task_id` | 关联后台 Celery 记录 |

---

## 3. API

### 3.1 后台任务 `/api/v1/tasks`

权限：`task:read`（列表/详情/meta）· `task:write`（取消/重试）

```
GET  /tasks?page=1&size=20&status=running
GET  /tasks/meta
GET  /tasks/{task_id}
POST /tasks/{task_id}/cancel
POST /tasks/{task_id}/retry    # 仅 document 入库：重新 delay ingest_document
```

### 3.2 生成任务 `/api/v1/generative/jobs`

权限：`attachment:read`（列表/详情/stream/meta）· `attachment:upload`（提交/取消/重试）

```
GET  /generative/jobs?kind=video&status=running
GET  /generative/jobs/meta
GET  /generative/jobs/{job_id}
GET  /generative/jobs/{job_id}/stream   # SSE text/event-stream
POST /generative/jobs/image
POST /generative/jobs/video
POST /generative/jobs/{job_id}/cancel
POST /generative/jobs/{job_id}/retry
```

---

## 4. 调度与执行

### 4.1 文档入库

```
POST /kb/{id}/documents/upload
    → TaskService.create_record
    → ingest_document.delay(document_id)
Worker → rag.pipeline.run_ingest_pipeline
    → sync_task_by_celery_id 更新 task_records
```

队列：`parse`（`task_routes` 配置）。

### 4.2 生图 / 生视频

```
Agent 工具 / Flow 节点 / POST /generative/jobs/*
    → GenerativeJobService 写 generative_jobs (pending)
    → run_generative_{image|video}_job.delay(job_id)
Worker → integrations/generative/jobs/runner
    → 写 attachment + media_asset
    → sync_task_by_celery_id
```

队列：`default`。进度通过 SSE `GET …/stream` 推送。

### 4.3 智能体定时（不在任务中心 UI）

```
Celery Beat (60s) → tick_agent_schedules → run_agent_schedule → AgentService.chat
```

需独立启动：`python cli.py beat`。详见 [agent-schedules.md](./agent-schedules.md)。

### 4.4 启动命令

```bash
python cli.py worker    # 消费 default,parse,ocr,asr,embed
python cli.py beat      # 定时任务扫描（可选）
```

---

## 5. 前端

### 5.1 入口

- `/workbench/tasks` — 默认 Tab「后台任务」
- `/workbench/tasks?category=generative` — 生成任务 Tab

### 5.2 组件

| 组件 | 职责 |
|------|------|
| `GenerativeJobsSection` | 生成任务列表、SSE 进度、取消/重试 |
| `TaskDetailDialog` | 后台任务详情、取消/重试 |
| `useTaskMeta` / `useGenerativeJobMeta` | `/meta` 枚举文案 |

### 5.3 文件清单

```
ui/workbench/app/workbench/tasks/page.tsx
ui/workbench/app/workbench/tasks/[id]/page.tsx
ui/workbench/components/task/GenerativeJobsSection.tsx
ui/workbench/components/task/TaskDetailDialog.tsx
ui/workbench/lib/task-labels.ts
ui/workbench/lib/generative-job-labels.ts
ui/workbench/lib/api.ts                     # tasks + generative jobs CRUD
```

---

## 6. 后端文件清单

```
backend/app/models/task.py
backend/app/models/generative_job.py
backend/app/tenant/tasks/views/tasks.py
backend/app/tenant/tasks/services/task.py
backend/app/tenant/tasks/services/sync.py
backend/app/tenant/generative/views/jobs.py
backend/app/tenant/generative/services/job.py
backend/app/workers/tasks/ingest.py
backend/app/workers/tasks/generative.py
backend/app/workers/tasks/agent_schedule.py
backend/app/workers/app.py              # beat_schedule + task_routes
backend/app/integrations/generative/jobs/runner.py
```

---

## 7. 测试计划

1. **入库**：上传文档 → `task_records` 可见 → 成功后 KB 文档状态 `ready`
2. **生成**：提交 video job → SSE 收到 progress → success 后 `media_assets` 有记录
3. **取消/重试**：failed generative job retry；running ingest cancel
4. **前端**：Tab 切换、`?category=generative` 深链、跳转关联 Celery 记录

---

## 8. 参考

- [knowledge-base.md](../guides/knowledge-base.md) — 入库流水线
- [attachments-media-generative.md](./attachments-media-generative.md) — 生成物与媒体资产
- [agent-schedules.md](./agent-schedules.md) — 定时任务（Beat）
- [multimodal-capabilities.md](../product/multimodal-capabilities.md) — 多模态能力与生成任务
