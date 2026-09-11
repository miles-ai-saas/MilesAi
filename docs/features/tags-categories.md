# 标签与分类

**状态：** 已实现  
**PRD 对照：** 各模块「分类管理」（横切能力）  
**架构：** [technical-design.md §4](../architecture/technical-design.md#4-分层与模块)

---

## 1. 背景与目标

工作台资源（智能体、提示词、技能包、工具、流程、应用市场）需要两种正交的组织方式：

| 能力 | 表 | 范围 |  cardinality | 维护方 |
|------|-----|------|--------------|--------|
| **分类** | `sys_categories` | 全平台共用 | 单选 `category_id` | 运营（租户只读） |
| **标签** | `tnt_tags` + `tnt_entity_tag_bindings` | 租户内 | 多选 `tag_ids` | 租户用户 |

**应用市场分类**（`mkt_categories`）与工作台 `sys_categories` **职责分离**，勿混用。

### 1.1 交付范围

- 租户 API：`GET /categories?domain=`（只读）、`/tags` CRUD
- 资源 CRUD 支持 `category_id` / `tag_ids` 写入与列表筛选
- 前端：`TagPicker`、`TagFilterDropdown`、`TagManageDialog`、分类 Tab 筛选

### 1.2 明确不做

- 租户自定义 `sys_categories`（二期若做走运营 API）
- 标签跨租户共享（市场展示发布方标签时用 `get_refs_map_for_tenant` 只读加载）
- 流程 `category_id`（流程仅支持标签，无分类域）

---

## 2. 数据模型

### 2.1 表 `sys_categories`

| 字段 | 说明 |
|------|------|
| `domain` | `agent` \| `prompt` \| `skill` \| `tool` |
| `parent_id` | 可选层级（当前多为扁平） |
| `name` / `slug` | 展示名与唯一键（domain 内） |
| `sort_order` | 排序 |
| `is_system` | 系统预置标记 |

资源表字段：`category_id`（UUID，可空），如 `agt_agents.category_id`。

### 2.2 表 `tnt_tags`

| 字段 | 说明 |
|------|------|
| `tenant_id` | 租户隔离 |
| `name` | 展示名 |
| `slug` | `(tenant_id, slug)` 唯一，由 `name` 自动生成 |

### 2.3 表 `tnt_entity_tag_bindings`

| 字段 | 说明 |
|------|------|
| `entity_type` | `agent` / `prompt` / `skill` / `tool` / `flow` / `marketplace_app` |
| `entity_id` | 资源主键 |
| `tag_id` | 标签 ID |

删除标签或资源时清理绑定；写入资源时 `TagService.replace_entity_tags` 全量替换。

---

## 3. API

### 3.1 分类 `/api/v1/categories`

租户只读；按 domain 校验对应模块 read 权限。

```
GET /categories/meta
GET /categories?domain=agent|prompt|skill|tool
```

运营维护：`/api/admin/v1/sys-categories`（不在租户 API）。

### 3.2 标签 `/api/v1/tags`

权限：`tag:read` · `tag:write`

```
GET    /tags/meta
GET    /tags              # 本租户全量，供 Picker/筛选器
POST   /tags              # body: { name }
DELETE /tags/{tag_id}     # 级联清理 bindings
```

### 3.3 资源侧约定

**写入**（创建/更新 body）：

- `category_id?: UUID` — agent / prompt / skill / tool
- `tag_ids?: UUID[]` — agent / prompt / skill / tool / flow / marketplace_app

**列表筛选**（query，任一标签匹配 OR）：

```
GET /agents?category_id=&tag_ids=
GET /prompt-templates?category_id=&tag_ids=
GET /skill-packages?category_id=&tag_ids=
GET /tools?category_id=&tag_ids=
GET /flows?tag_ids=
GET /marketplace/apps?tag_ids=
```

---

## 4. 服务层

```
TagService.replace_entity_tags(entity_type, entity_id, tag_ids)
TagService.clear_entity_tags(...)          # 资源删除
TagService.get_refs_map(...)               # 列表回填 tags[]
TagService.entity_id_filter(...)           # 列表 IN 子查询筛选
CategoryService.list_categories(domain)    # 按 domain 排序返回
```

各资源 Service 在 create/update 后调用 `replace_entity_tags`；deletion 走 `clear_entity_tags`。

---

## 5. 前端

### 5.1 组件

| 组件 | 用途 |
|------|------|
| `TagPicker` | 表单多选标签 |
| `TagFilterDropdown` | 列表页标签筛选 |
| `TagChips` | 卡片/行内展示 |
| `TagManageDialog` | 标签库增删 |

### 5.2 使用页面

智能体、提示词、技能包、工具、流程、应用市场列表均支持 `tag_ids` 筛选；前四者另有分类 Tab / `category_id`。

### 5.3 文件清单

```
ui/workbench/components/tag/TagPicker.tsx
ui/workbench/components/tag/TagFilterDropdown.tsx
ui/workbench/components/tag/TagChips.tsx
ui/workbench/components/tag/TagManageDialog.tsx
ui/workbench/lib/api.ts                       # tags + categories
```

---

## 6. 后端文件清单

```
backend/packages/miles-core/src/miles_core/models/meta/tag.py
backend/packages/miles-core/src/miles_core/models/meta/category.py
backend/packages/miles-portal/src/miles_portal/tenant/tags/
backend/packages/miles-portal/src/miles_portal/tenant/categories/
backend/packages/miles-portal/src/miles_portal/tenant/agents/services/agent/   # 绑定 tag/category
backend/packages/miles-portal/src/miles_portal/tenant/marketplace/services/    # marketplace_app 标签
```

---

## 7. 测试计划

1. 创建标签 → 绑定智能体 → 列表 `tag_ids` 筛选命中
2. 删除标签 → bindings 清空 → 资源不再展示该标签
3. `GET /categories?domain=agent` 需 `agent:read` 权限
4. 同名标签创建 → 409 Conflict

---

## 8. 参考

- [hooks.md](../guides/hooks.md) §9 — 全站 `/meta` 枚举约定
- [marketplace.md](./marketplace.md) — 市场应用标签与市场分类
