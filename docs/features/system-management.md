# 系统管理

**日期：** 2026-05-27  
**状态：** 已实现  
**PRD 对照：** 模块1 系统管理  
**架构：** [technical-design.md §5](../architecture/technical-design.md#5-多租户与权限) · **增强方案：** [system-management-design.md](../architecture/system-management-design.md)

---

## 1. 背景与目标

租户工作台 **系统管理区**（`/system/*`）提供 RBAC、用户、角色、租户（多租户管理员）、运行时配置与操作审计。认证走 JWT；**平台运营**见 [admin-ops.md](./admin-ops.md)（`ui/admin` · `/api/admin/v1`）。

### 1.1 交付范围

- 认证：`login` / `logout` / `refresh` / `me`
- 用户 CRUD、软禁用
- 角色与权限分配
- 租户 CRUD（平台级权限）
- 系统配置读写（`sys_configs`）
- 租户审计日志查询

### 1.2 明确不做

- 租户自助修改向量库/OSS 引擎类型（见 technical-design §6.5 L2 规划）
- **租户后台修改资源配额**（`max_*`）；配额变更仅运营后台
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
POST   /users/batch-deactivate   # 批量软禁用，返回 { deactivated, skipped }
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

### 3.5.1 租户对象存储 BYOK `/api/v1/system/object-storage`（L2）

权限：`system:config:read` · `system:config:write`

```
GET  /system/object-storage              # 当前租户配置（Secret 脱敏）
PUT  /system/object-storage              # 保存/启用租户 S3 兼容桶
POST /system/object-storage/test-connection
```

启用后新上传（KB 文档、附件、生成物）写入租户 bucket；`object_key` 仍含 `tenant_id/` 前缀。历史文件保留在原桶。

### 3.5.2 基础设施 `/api/v1/system/infra`（只读 + 探测）

权限：`GET /status` 需 `system:config:read`；`POST /test-connection` 仅租户超管。

```
GET  /system/infra/status              # 组件状态 + 脱敏配置预览
POST /system/infra/test-connection     # 测试 PG/Redis/对象存储/向量库/Celery Broker
```

### 3.6 审计 `/api/v1/audit`

权限：`audit:read`

```
GET /audit/meta
GET /audit/logs?user_id=&action=&resource_type=
GET /audit/logs/export?action=&resource_type=&limit=   # CSV 导出（UTF-8 BOM）
```

### 3.7 资源配额 `/api/v1/system/quota`（只读）

权限：`system:quota:read`

```
GET /system/quota    # 本租户 KB/存储/智能体/流程/Token/生成日次数汇总
```

配额上限修改仅在运营后台；租户侧无写接口。

### 3.8 用户扩展

```
POST /users/{id}/reset-password    # 管理员重置密码（system:user:write），并重置全部会话
```

登录成功写入审计：`action=auth.login`。

### 3.9 健康检查

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
| `/system/users` | 用户管理（批量启用/禁用/赋角色/删除、重置密码） |
| `/system/roles` | 角色权限 |
| `/system/sessions` | 登录会话 |
| `/system/quota` | 资源配额（只读） |
| `/system/config` | 系统配置（L2 业务参数 + 租户对象存储 BYOK + L1 基础设施只读） |
| `/system/audit` | 审计日志（含 CSV 导出） |
| `/workbench/dashboard` | 概览页配额摘要（需 `system:quota:read`） |

侧栏按 RBAC 过滤：`ui/workbench/lib/nav-config.ts` · `lib/permissions.ts`

---

## 6. 后端文件清单

```
backend/app/tenant/auth/
backend/app/tenant/system/views/{users,roles,tenants,configs,quota,health}.py
backend/app/tenant/system/services/quota.py
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

- [system-management-design.md](../architecture/system-management-design.md) — Phase 0–3 增强技术方案
- [operations/database-setup.md](../operations/database-setup.md) — 种子与迁移
- [admin-ops.md](./admin-ops.md) — 运营后台
