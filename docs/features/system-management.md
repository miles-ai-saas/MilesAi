# 系统管理

**日期：** 2026-05-27  
**状态：** 已实现  
**PRD 对照：** 模块1 系统管理  
**架构：** [technical-design.md §5](../architecture/technical-design.md#5-多租户与权限)

---

## 1. 背景与目标

租户工作台 **系统管理区**（`/system/*`）提供 RBAC、用户、角色、租户（多租户管理员）、运行时配置与操作审计。认证走 JWT；**平台运营**见 [admin-ops.md](./admin-ops.md)（`admin_frontend` · `/api/admin/v1`）。

### 1.1 交付范围

- 认证：`login` / `logout` / `refresh` / `me`
- 用户 CRUD、软禁用
- 角色与权限分配
- 租户 CRUD（平台级权限）
- 系统配置读写（`sys_configs`）
- 租户审计日志查询

### 1.2 明确不做

- 租户自助修改向量库/OSS 引擎类型（见 technical-design §6.5 L2 规划）
- 会话设备管理与强制登出 UI（JWT 黑名单 logout 已支持）

---

## 2. 数据模型

| 表 | 说明 |
|----|------|
| `sys_tenants` | 租户、配额字段 |
| `sys_users` | 用户、所属租户、密码哈希 |
| `sys_roles` / `sys_permissions` / 关联表 | RBAC |
| `sys_configs` | 键值配置（如生成日配额） |
| `aud_logs` | 租户操作审计 |

ORM 无库级外键；`TenantContext` 注入 `tenant_id`、`user_id`、权限集。

---

## 3. API

### 3.1 认证 `/api/v1/auth`

```
POST /auth/login          # body: username, password → TokenResponse
POST /auth/logout         # 需 JWT，黑名单
GET  /auth/me               # UserInfo + permissions
POST /auth/refresh
```

### 3.2 用户 `/api/v1/users`

权限：`system:user:read` · `system:user:write`

```
GET    /users?page=
POST   /users
PATCH  /users/{id}
DELETE /users/{id}         # 软禁用
```

### 3.3 角色 `/api/v1/roles`

权限：`system:role:read` · `system:role:write`

```
GET  /roles/permissions    # 权限树
GET  /roles/assignable
GET  /roles
POST /roles
PATCH /roles/{id}
DELETE /roles/{id}
```

### 3.4 租户 `/api/v1/tenants`

权限：`system:tenant:read` · `system:tenant:write`

```
GET  /tenants
POST /tenants
GET  /tenants/{id}
PATCH /tenants/{id}
```

### 3.5 配置 `/api/v1/system/configs`

```
GET /system/configs/definitions
GET /system/configs/runtime
GET /system/configs
PUT /system/configs/{key}
```

### 3.6 审计 `/api/v1/audit`

权限：`audit:read`

```
GET /audit/meta
GET /audit/logs?user_id=&action=&resource_type=
```

### 3.7 健康检查

```
GET /api/v1/health
```

---

## 4. 权限模型

- 路由依赖 `require_permissions("xxx:read|write")`
- Service 层 `assert_tenant_access` + `tenant_filters`
- 种子用户：租户 `admin` / `admin123`（`scripts/seed/`）

---

## 5. 前端

| 路径 | 功能 |
|------|------|
| `/login` | JWT 登录 |
| `/system/users` | 用户管理 |
| `/system/roles` | 角色权限 |
| `/system/config` | 系统配置 |
| `/system/audit` | 审计日志 |

导航：`frontend/lib/nav-config.ts` → `SYSTEM_NAV`。

---

## 6. 后端文件清单

```
backend/app/tenant/auth/
backend/app/tenant/system/views/{users,roles,tenants,configs,health}.py
backend/app/tenant/system/services/
backend/app/tenant/audit_log/
backend/app/core/deps.py              # get_tenant_context, require_permissions
backend/app/core/tenant.py
backend/app/models/{tenant,user,role,system}.py
```

---

## 7. 测试计划

1. login → me 含 permissions → 无权限 API 403
2. 创建角色赋权 → 用户绑定 → 对应模块可访问
3. 跨租户 user_id 访问 → 404/403
4. audit/logs 按 action 筛选

---

## 8. 参考

- [operations/database-setup.md](../operations/database-setup.md) — 种子与迁移
- [admin-ops.md](./admin-ops.md) — 运营后台
