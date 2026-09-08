# 业务中心

> **⚠️ 已归档（2026-09-07）**：业务中心（广告试点）全量代码已从主分支摘除，进入重设计。
> 本文档保留作为重设计素材；实现代码恢复见 tag `archive/business-center-p0-p4`。
> `biz_*` 数据表已于 2026-09-08 从开发库删除（无存量数据迁移），重设计时按新模型重建。

**日期：** 2026-06-01  
**状态：** 已实现（Phase 0–4）；Phase 5 按需  
**架构：** [business-center-design.md](../architecture/business-center-design.md)  
**试点场景：** 广告公司（八条服务线：品牌、影视、展览、活动、培训、标识、文创、印刷）

---

## 1. 背景与目标

租户工作台在 **AI 工作台** 与 **组织设置**（原系统管理）之外，新增 **业务中心**（`/business/*`），承载广告/文创类租户的项目制交付管理：客户、商机、项目、工作包、交付物与轻量预算。

### 1.1 交付范围（分期）

| 阶段 | 范围 |
|------|------|
| **MVP（P1）** | 客户、项目、工作包、交付物、业务仪表盘、RBAC、`biz:*` API |
| **P2** | 商机 pipeline、报价、里程碑、结项与案例沉淀 KB |
| **P3** | 合同、回款、供应商、成本汇总 |
| **P4** | 项目上下文 AI deep link、服务线 Agent/Flow 模板 |

### 1.2 明确不做（MVP）

- 独立前端应用 `ui/business`（见架构文档：扩 workbench 第三分区）
- 后端 `app/tenant/biz/` 嵌套包（业务域用 **`app/biz/` 与 tenant 同级**）
- 重复文件存储（交付物走现有 `attachments` / `media-assets`）
- 八条业务线八个顶级菜单（统一为项目 + 工作包 + 服务线模板）
- ERP 硬对接（三期前仅 Excel 导出）
- 涉密项目默认进入知识库 RAG

---

## 2. 后端包与 ORM

| 项 | 约定 |
|----|------|
| 域包 | `backend/app/biz/`（与 `app/tenant/` **同级**，见架构 §4.1） |
| ORM | `backend/app/models/biz.py`（不在 `biz/models/` 再建一层） |
| 路由 | `app/biz/router.py` → 由 `app/tenant/router.py` 挂载 `prefix="/biz"` |
| API 前缀 | `/api/v1/biz/*`（与 JWT、`TenantContext` 同平面） |

子域建议：`biz/clients/`、`biz/projects/`、`biz/work_packages/`、`biz/deliverables/`（各含 `views` / `services` / `repositories` / `schemas` 或按子包扁平拆分）。

---

## 3. 数据模型

### 3.1 表 `biz_clients`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID | 主键 |
| `tenant_id` | UUID | 租户隔离 |
| `name` | VARCHAR(256) | 客户名称 |
| `short_name` | VARCHAR(64) NULL | 简称 |
| `industry` | VARCHAR(64) NULL | 行业：government / enterprise / park / commercial / tourism / other |
| `confidentiality_level` | VARCHAR(32) | `normal` / `internal` / `restricted`（涉密） |
| `address` | TEXT NULL | 地址 |
| `remark` | TEXT NULL | 备注 |
| `created_by` | UUID NULL | 创建人 |
| `created_at` / `updated_at` / `deleted_at` | TIMESTAMPTZ | 时间戳与软删 |

索引：`tenant_id`、`name`（租户内检索）。

### 3.2 表 `biz_client_contacts`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID | 主键 |
| `tenant_id` | UUID | |
| `client_id` | UUID | 所属客户 |
| `name` | VARCHAR(128) | 联系人 |
| `title` | VARCHAR(128) NULL | 职务 |
| `phone` | VARCHAR(32) NULL | |
| `email` | VARCHAR(256) NULL | |
| `is_primary` | BOOLEAN | 主联系人 |
| `created_at` / `updated_at` / `deleted_at` | TIMESTAMPTZ | |

### 3.3 表 `biz_opportunities`（P2）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID | |
| `tenant_id` | UUID | |
| `client_id` | UUID | |
| `title` | VARCHAR(256) | 商机名称 |
| `stage` | VARCHAR(32) | `lead` / `proposal` / `pitch` / `won` / `lost` |
| `estimated_amount` | NUMERIC(14,2) NULL | 预估金额 |
| `owner_id` | UUID NULL | 负责人 `sys_users.id` |
| `project_id` | UUID NULL | 赢单后关联项目 |
| `created_at` / `updated_at` / `deleted_at` | TIMESTAMPTZ | |

### 3.4 表 `biz_projects`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID | |
| `tenant_id` | UUID | |
| `client_id` | UUID | |
| `code` | VARCHAR(32) NULL | 项目编号（租户内可唯一） |
| `name` | VARCHAR(256) | 项目名称 |
| `status` | VARCHAR(32) | `draft` / `active` / `on_hold` / `delivered` / `closed` / `cancelled` |
| `start_date` | DATE NULL | |
| `end_date` | DATE NULL | |
| `owner_id` | UUID NULL | 项目经理 |
| `description` | TEXT NULL | |
| `total_budget` | NUMERIC(14,2) NULL | 项目总预算（MVP 可选） |
| `opportunity_id` | UUID NULL | 来源商机 |
| `created_by` | UUID NULL | |
| `created_at` / `updated_at` / `deleted_at` | TIMESTAMPTZ | |

索引：`tenant_id`、`client_id`、`status`、`owner_id`。

### 3.5 表 `biz_work_packages`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID | |
| `tenant_id` | UUID | |
| `project_id` | UUID | |
| `service_line` | VARCHAR(64) | 见架构文档八条线编码 |
| `name` | VARCHAR(256) | 工作包名称 |
| `stage` | VARCHAR(64) | 当前阶段（来自模板） |
| `stage_index` | INT | 模板内序号，便于排序 |
| `status` | VARCHAR(32) | `pending` / `in_progress` / `review` / `done` / `cancelled` |
| `owner_id` | UUID NULL | 负责人 |
| `budget` | NUMERIC(14,2) NULL | 工作包预算 |
| `actual_cost` | NUMERIC(14,2) NULL | 实际成本（MVP 手工录入） |
| `planned_start` / `planned_end` | DATE NULL | |
| `created_at` / `updated_at` / `deleted_at` | TIMESTAMPTZ | |

索引：`tenant_id`、`project_id`、`service_line`、`status`。

### 3.6 表 `biz_milestones`（P2，MVP 可用工作包 stage 代替）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID | |
| `tenant_id` | UUID | |
| `work_package_id` | UUID | |
| `title` | VARCHAR(256) | |
| `due_date` | DATE NULL | |
| `completed_at` | TIMESTAMPTZ NULL | |
| `sort_order` | INT | |

### 3.7 表 `biz_deliverables`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID | |
| `tenant_id` | UUID | |
| `project_id` | UUID | |
| `work_package_id` | UUID NULL | |
| `name` | VARCHAR(256) | 交付物名称 |
| `type` | VARCHAR(64) | `document` / `video` / `design` / `print` / `other` |
| `attachment_id` | UUID NULL | 关联 `attachments` |
| `media_asset_id` | UUID NULL | 关联生成素材 |
| `kb_document_id` | UUID NULL | 沉淀到知识库后 |
| `version` | VARCHAR(32) NULL | 版本号 |
| `status` | VARCHAR(32) | `draft` / `submitted` / `accepted` / `rejected` |
| `submitted_at` / `accepted_at` | TIMESTAMPTZ NULL | |
| `created_by` | UUID NULL | |
| `created_at` / `updated_at` / `deleted_at` | TIMESTAMPTZ | |

### 3.8 表 `biz_service_line_templates`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID | |
| `tenant_id` | UUID NULL | NULL 表示平台种子模板 |
| `service_line` | VARCHAR(64) | |
| `stages` | JSONB | `[{"key":"script","label":"脚本","sort":0}, ...]` |
| `is_active` | BOOLEAN | |
| `created_at` / `updated_at` | TIMESTAMPTZ | |

### 3.9 表 `biz_project_members`

| 字段 | 类型 | 说明 |
|------|------|------|
| `project_id` | UUID | |
| `user_id` | UUID | `sys_users.id` |
| `role_in_project` | VARCHAR(64) | `pm` / `creative` / `executor` / `viewer` |
| `tenant_id` | UUID | |

主键：`(project_id, user_id)`。

---

## 4. API

前缀：`/api/v1/biz`  
权限：见 §6；列表均分页 `page` / `size`。

### 4.1 Meta

```
GET /biz/meta
→ {
  "service_lines": [{ "key", "label" }],
  "project_statuses": [...],
  "work_package_statuses": [...],
  "industries": [...],
  "confidentiality_levels": [...]
}
```

权限：`biz:project:read` 或任意 `biz:*:read`。

### 4.2 客户

权限：`biz:client:read` · `biz:client:write`

```
GET    /biz/clients?page=&size=&search=
POST   /biz/clients
GET    /biz/clients/{id}
PATCH  /biz/clients/{id}
DELETE /biz/clients/{id}          # 软删

GET    /biz/clients/{id}/contacts
POST   /biz/clients/{id}/contacts
PATCH  /biz/clients/{id}/contacts/{contact_id}
DELETE /biz/clients/{id}/contacts/{contact_id}
```

**ClientOut（摘要）**

```json
{
  "id": "uuid",
  "name": "某市文旅局",
  "industry": "government",
  "confidentiality_level": "restricted",
  "primary_contact": { "name": "张三", "phone": "..." },
  "project_count": 3,
  "created_at": "2026-06-01T00:00:00Z"
}
```

### 4.3 项目

权限：`biz:project:read` · `biz:project:write`

```
GET    /biz/projects?page=&size=&client_id=&status=&owner_id=
POST   /biz/projects
GET    /biz/projects/{id}
PATCH  /biz/projects/{id}
DELETE /biz/projects/{id}

GET    /biz/projects/{id}/work-packages
POST   /biz/projects/{id}/work-packages      # 追加工作包
GET    /biz/projects/{id}/deliverables
POST   /biz/projects/{id}/deliverables
GET    /biz/projects/{id}/members
PUT    /biz/projects/{id}/members            # 全量替换成员列表
```

**ProjectCreate**

```json
{
  "client_id": "uuid",
  "name": "XX 展馆整体设计",
  "owner_id": "uuid",
  "work_packages": [
    { "service_line": "exhibition", "name": "展陈主包" },
    { "service_line": "signage", "name": "导视系统" }
  ]
}
```

创建时按 `service_line` 从模板初始化 `stage` / `stage_index`。

### 4.4 工作包

```
GET    /biz/work-packages?page=&project_id=&service_line=&status=
PATCH  /biz/work-packages/{id}
POST   /biz/work-packages/{id}/advance-stage   # 推进到下一阶段（校验 stage_index）
POST   /biz/work-packages/{id}/rollback-stage  # 可选，需 write + 审计
```

**WorkPackagePatch**：`stage`、`status`、`owner_id`、`budget`、`actual_cost`、`planned_start`、`planned_end`。

### 4.5 交付物

```
GET    /biz/deliverables/{id}
PATCH  /biz/deliverables/{id}
DELETE /biz/deliverables/{id}
POST   /biz/deliverables/{id}/submit
POST   /biz/deliverables/{id}/accept
```

创建时 `attachment_id` 由前端先调 `POST /attachments` 上传后填入。

### 4.6 仪表盘

```
GET /biz/dashboard/summary
→ {
  "active_projects": 12,
  "pending_acceptance": 3,
  "work_packages_by_stage": { "in_progress": 8, ... },
  "recent_projects": [ ProjectOut, ... ]
}
```

权限：`biz:dashboard:read`。

### 4.7 商机（P2）

```
GET/POST/PATCH/DELETE /biz/opportunities ...
POST /biz/opportunities/{id}/convert   # → 创建 project
```

---

## 5. 前端清单

### 5.1 路由

| 路径 | 页面 | 阶段 |
|------|------|------|
| `/business` | 重定向 `/business/dashboard` | P0 |
| `/business/dashboard` | 业务总览 | P1 |
| `/business/clients` | 客户列表 | P1 |
| `/business/clients/[id]` | 客户详情（联系人、历史项目） | P1 |
| `/business/projects` | 项目列表 | P1 |
| `/business/projects/[id]` | 项目详情（工作包 Tab、交付物 Tab、成员、AI 入口） | P1 |
| `/business/opportunities` | 商机看板 | P2 |

### 5.2 Feature 模块

| Feature | 路径 | 说明 |
|---------|------|------|
| `business-dashboard` | `features/business-dashboard/` | 仪表盘 VM |
| `clients` | `features/clients/` | 客户 CRUD |
| `projects` | `features/projects/` | 项目详情、成员 |
| `work-packages` | `features/work-packages/` | 阶段推进、看板 |
| `deliverables` | `features/deliverables/` | 交付物与附件关联 |

### 5.3 壳层与导航

- `BusinessShell` / `BusinessSidebar`（参考 `SystemShell`）
- `nav-config.ts`：`BUSINESS_NAV`、`filterBusinessNav(user)`
- `AppShell`：`section === "business"` 分支
- `SectionLink`：三分区切换
- 文案：「系统管理」→「组织设置」

### 5.4 复用组件

- `ResourceListLayout`、`ResourceListFooter`、`usePagedList`
- `useConfirmAction`、标签筛选（客户行业）
- 附件上传：现有 attachments 组件/ API

---

## 6. 角色与权限

<a id="6-角色与权限"></a>

| 角色 | 权限概要 |
|------|----------|
| 总经理 | 全部 `biz:*` |
| 商务 / 客户经理 | `biz:client:*`、`biz:opportunity:*`、`biz:project:read`、报价只读 |
| 项目经理 | `biz:project:*`、`biz:work_package:*`、`biz:deliverable:*` |
| 创意 / 设计 | 被分配工作包的 read/write、交付物 write |
| 执行 / 场务 | 工作包 read、交付物 read |
| 财务 | `biz:finance:read`、项目/工作包 read、预算字段 write（P3） |

种子数据在 `scripts/seed/` 增加试点角色与权限（实施 Phase 1 时）。

---

## 7. 调度与异步

MVP 无专用 Celery 任务。P2 可选：

- 里程碑到期提醒：`biz.check_milestone_due`（Beat）
- 结项案例入库：复用 `ingest_document` Celery 链

---

## 8. 测试

| 用例 | 说明 |
|------|------|
| 租户隔离 | A 租户不可读写 B 租户客户/项目 |
| 组合项目 | 一次创建多 `service_line` 工作包，阶段模板正确 |
| 阶段推进 | `advance-stage` 边界与审计 |
| 涉密客户 | `restricted` 项目禁止 `POST` 案例入库 KB（P2） |
| 权限 | 创意角色不可删客户 |

---

## 9. 相关文档

- [business-center-design.md](../architecture/business-center-design.md) — 架构、分期、与 AI 映射
- [system-management.md](./system-management.md) — 组织设置（原系统管理）
- [attachments-media-generative.md](./attachments-media-generative.md) — 交付物文件
- [kb-ingest-retrieval.md](./kb-ingest-retrieval.md) — 案例沉淀
- [tags-categories.md](./tags-categories.md) — 客户/项目标签
