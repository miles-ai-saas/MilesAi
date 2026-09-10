# 运营后台（Admin）

**状态：** 基线 + Phase 0–5 已实现（见 [admin-ops-design.md](../architecture/admin-ops-design.md)）  
**PRD 对照：** 模块1 系统管理（平台侧）· 模块7 市场分类  
**架构：** [technical-design.md §运营域](../architecture/technical-design.md#4-分层与模块) · **增强方案：** [admin-ops-design.md](../architecture/admin-ops-design.md)

---

## 1. 背景与目标

**运营后台**（`ui/admin/`，`:3001`）与租户工作台分离：独立 JWT（`adm_admins`）、API 前缀 `/api/admin/v1`，用于平台管理员维护租户、计费、风控、内置模型目录、系统分类与应用市场分类。

### 1.1 交付范围

- 管理员登录 / 登出 / 改密 / 会话
- 租户 CRUD、配额
- 计费计划与账单
- 风控事件、IP 黑名单、限流规则
- 运营审计日志
- 内置模型目录发布/下架
- `sys_categories`（工作台分类）、`mkt_categories`（市场分类）维护

### 1.2 明确不做

- 租户内 RBAC（在租户 `/system/*`）
- 应用市场审核：按 `MARKETPLACE_REVIEW_MODE` — `platform` 在运营 `/marketplace-review`，`tenant` 在工作台「上架审核」（见 [marketplace-review-design.md](../architecture/marketplace-review-design.md)）

---

## 2. 与租户 API 分离

| 项 | 租户 | 运营 |
|----|------|------|
| 前端 | `ui/workbench/` :3000 | `ui/admin/` :3001 |
| API | `/api/v1` | `/api/admin/v1` |
| 认证 | `sys_users` JWT | `adm_admins` JWT |
| 用户 | 租户管理员/成员 | 平台管理员 |

---

## 3. API 概览

### 3.1 认证 `/api/admin/v1`

```
POST /auth/login
POST /auth/logout
GET  /auth/me
POST /auth/change-password
GET  /auth/sessions
DELETE /auth/sessions/{admin_id}
```

### 3.2 运营 `/api/admin/v1`

```
GET  /dashboard/summary

GET/POST/PATCH/DELETE /admins          # super_admin
POST   /admins/{id}/reset-password

GET/POST/PATCH/DELETE /tenants
PATCH /tenants/{id}/quota
GET  /tenants/{id}/usage

GET/POST/PATCH /billing/plans
GET /billing/bills
POST /billing/bills/generate
PATCH /billing/bills/{id}              # paid / void

GET /risk/events · POST …/resolve
GET/POST/PATCH /risk/ip-blacklist
GET/POST/PATCH /risk/rate-limits

GET /audit/logs

GET  /marketplace/review-mode
GET  /marketplace/apps/pending
GET  /marketplace/apps/{id}
POST /marketplace/apps/{id}/approve|reject   # review_mode=platform

GET/POST/PATCH/DELETE /model-catalog
POST /model-catalog/{id}/publish|deprecate

GET/POST/PATCH/DELETE /marketplace-categories
GET/POST/PATCH/DELETE /sys-categories
```

完整路径以运行实例 OpenAPI 为准。

---

## 4. 前端页面（`ui/admin/app/`）

| 路径 | 功能 |
|------|------|
| `/login` | 运营登录 |
| `/` | 控制台（`GET /dashboard/summary`） |
| `/tenants` | 租户列表 |
| `/tenants/[id]` | 租户详情与配额 |
| `/model-catalog` | 内置模型目录 |
| `/marketplace-review` | 应用审核（`review_mode=platform` 时侧栏可见） |
| `/sys-categories` | 工作台资源分类 |
| `/marketplace-categories` | 应用市场分类 |
| `/billing` | 计费计划、生成账单、标记已付/作废 |
| `/risk` | 风控 |
| `/audit` | 审计（含 CSV 导出） |
| `/admins` | 平台管理员（`super_admin`） |
| `/profile` | 改密、会话、强制下线 |

壳层：`ui/admin/components/layout/AdminShell` · `AdminUserMenu`；导航 `ui/admin/lib/admin-nav.ts`。

---

## 5. 与租户功能关系

| 运营配置 | 租户消费 |
|----------|----------|
| 内置 `agt_model_configs`（tenant_id 空） | `/workbench/models` 只读 + BYOK 凭证 |
| `sys_categories` | `GET /api/v1/categories?domain=` |
| `mkt_categories` | `GET /api/v1/marketplace/categories` |
| 租户 quota | 创建 KB/资源上限 |

---

## 6. 后端与前端文件清单

```
backend/app/admin/
    router.py
    app_sys/views/auth.py
    app_sys/session_store.py
    app_ops/views/{admins,dashboard,tenants,billing,risk,audit,model_catalog,marketplace_review,sys_categories,marketplace_categories}.py
    app_ops/services/{admins,dashboard,marketplace_review,risk_enforce,...}.py
backend/app/middlewares/platform_risk.py
backend/app/marketplace/{review_config,review_core}.py

ui/admin/
    app/{page.tsx,login/,tenants/,model-catalog/,marketplace-review/,billing/,risk/,audit/,admins/,profile/,...}
    lib/{api.ts,admin-nav.ts,auth-store.ts}
    components/layout/{AdminShell,AdminSidebar,AdminUserMenu,...}
```

---

## 7. 部署

- Docker：`admin-web` 服务，端口 `ADMIN_WEB_PORT`（默认 3001）
- 环境变量：`NEXT_PUBLIC_ADMIN_API_URL=http://localhost:8000/api/admin/v1`
- 种子平台管理员：`scripts/seed/admin_ops.py`（默认见 database-setup）

详见 [operations/deployment.md](../operations/deployment.md)。

---

## 8. 测试计划

1. 运营 login → 租户列表 → 创建租户
2. 发布内置模型 → 租户 `/models` 可见
3. 修改 sys_categories → 租户 agents 分类 Tab 更新
4. 租户 JWT 无法访问 `/api/admin/v1`

---

## 9. 参考

- [admin-ops-design.md](../architecture/admin-ops-design.md) — Phase 0–4 增强技术方案
- [features/system-management.md](./system-management.md) — 租户侧系统管理
- [features/tags-categories.md](./tags-categories.md) — sys_categories 消费方
- [features/marketplace.md](./marketplace.md) — mkt_categories
- [model-providers.md](../guides/model-providers.md) — 内置模型目录
