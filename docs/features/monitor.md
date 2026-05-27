# 监控与统计

**日期：** 2026-05-27  
**状态：** 基础已实现  
**PRD 对照：** 模块9 监控与统计  
**架构：** [technical-design.md §4 monitor](../architecture/technical-design.md#4-分层与模块)

---

## 1. 背景与目标

租户 **监控** 页聚合资源用量、调用趋势、健康快照与 **HTTP Webhook 告警** 配置。非完整 APM；组件级 CPU/磁盘监控依赖外部运维。

### 1.1 交付范围

- 统计卡片：智能体/KB/流程/任务等 COUNT 聚合
- 趋势：近 N 日调用量（默认 7 天）
- 健康报告 + CSV 导出
- 告警配置：阈值 + Webhook URL，支持 test
- 工作台概览：`GET /workbench/overview`（快捷入口统计）
- 前端：`/workbench/monitor`、`/workbench/dashboard`

### 1.2 明确不做

- PostgreSQL/Redis/MinIO 进程级监控 UI
- PDF 报表、自定义报表模板
- 多通道告警（邮件/短信）

---

## 2. 数据来源

| 指标 | 来源 |
|------|------|
| 资源数量 | PG COUNT（agents、kb、flows…） |
| 调用趋势 | 审计/日志表聚合（实现见 MonitorService） |
| 任务统计 | `task_records`、`generative_jobs` |
| 健康检查 | API 侧探测 DB/Redis 等（简化） |

告警配置持久化：`sys_configs` 或 MonitorService 专用 key（见实现）。

---

## 3. API

### 3.1 监控 `/api/v1/monitor`

权限：`monitor:read` · `monitor:write`

```
GET  /monitor/meta
GET  /monitor/stats
GET  /monitor/trends?days=7
GET  /monitor/report
GET  /monitor/report/export     # CSV download
GET  /monitor/health
GET  /monitor/alerts
PUT  /monitor/alerts
POST /monitor/alerts/test
```

### 3.2 工作台概览 `/api/v1/workbench`

```
GET /workbench/overview         # 聚合 COUNT，减少多路列表请求
```

---

## 4. 前端

```
ui/workbench/app/workbench/monitor/page.tsx
ui/workbench/app/workbench/dashboard/page.tsx
```

---

## 5. 后端文件清单

```
backend/app/tenant/monitor/
backend/app/tenant/workbench/services/overview.py
```

---

## 6. 测试计划

1. stats 返回各模块 count 与 DB 一致
2. trends days=30 边界
3. export CSV Content-Disposition
4. alerts test → Webhook 收到 payload

---

## 7. 参考

- [system-management.md](./system-management.md) — sys_configs
- [task-center.md](./task-center.md) — 任务统计
