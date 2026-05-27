# 应用市场

**日期：** 2026-05-27  
**状态：** 已实现  
**PRD 对照：** 模块7 AI应用市场  
**架构：** [technical-design.md §12](../architecture/technical-design.md#12-应用市场)

---

## 1. 背景与目标

租户可将 KB / 流程 / 智能体 **打包为应用**（manifest JSON），经审核后上架广场，其他租户 **一键安装**（复制资源到本租户）并 **评分**。

### 1.1 交付范围

- 应用 CRUD、从资源打包、提交审核、通过/驳回
- 广场列表（分类、排序、标签筛选）、详情、安装、我的安装
- 评分（需已安装，`marketplace:rate`）
- 前端：`/workbench/marketplace`、详情 Drawer、星级展示

### 1.2 明确不做

- 应用版本 diff / 一键升级（安装后资源独立演进）
- 跨租户共享 KB 文档 blob（安装时创建空 KB 壳，需用户自行入库）
- 私有应用仅本租户可见（v1 审核通过后全平台 `PUBLISHED` 可见）

---

## 2. 数据模型

### 2.1 表 `mkt_categories`

应用市场专用分类（与工作台 `sys_categories` 分离）。

| 字段 | 说明 |
|------|------|
| `name` / `slug` | 展示与筛选 |
| `sort_order` | 排序 |

### 2.2 表 `mkt_apps`

| 字段 | 说明 |
|------|------|
| `publisher_tenant_id` | 发布方租户 |
| `category_id` | 市场分类 |
| `status` | `draft` / `pending_review` / `published` / `rejected` / `archived` |
| `manifest` | JSONB，见 §4.1 |
| `install_count` / `rating_avg` / `rating_count` | 统计 |
| `submitted_at` / `reviewed_at` / `reviewed_by` / `review_note` | 审核 |

标签通过 `tnt_entity_tag_bindings`（`entity_type=marketplace_app`）关联，见 [tags-categories.md](./tags-categories.md)。

### 2.3 表 `mkt_installs`

| 字段 | 说明 |
|------|------|
| `tenant_id` + `app_id` | UNIQUE，每租户每应用仅安装一次 |
| `flow_id` / `agent_id` / `kb_id` | 安装后在本租户创建的资源 ID |

### 2.4 表 `mkt_ratings`

`(tenant_id, app_id, user_id)` UNIQUE；score 1–5 + 可选 comment。

---

## 3. API

前缀：`/api/v1/marketplace`  
权限：`marketplace:read` · `marketplace:write` · `marketplace:review` · `marketplace:install` · `marketplace:rate`

### 3.1 浏览

```
GET  /marketplace/meta
GET  /marketplace/categories
GET  /marketplace/apps?category=&sort=installs|rating&tag_ids=
GET  /marketplace/apps/{id}
GET  /marketplace/apps/{id}/ratings
GET  /marketplace/installs
```

### 3.2 发布方

```
POST  /marketplace/apps
POST  /marketplace/apps/from-resources    # 从 KB/Flow/Agent 生成 manifest
PATCH /marketplace/apps/{id}
POST  /marketplace/apps/{id}/publish      # draft → pending_review
GET   /marketplace/apps/mine?tag_ids=
```

`from-resources` body 示例字段：`kb_id`、`flow_id`、`agent_id`、`name`、`category_slug`、`tag_ids`。

### 3.3 审核

```
GET  /marketplace/apps/pending?tag_ids=   # marketplace:review
POST /marketplace/apps/{id}/approve
POST /marketplace/apps/{id}/reject        # body: { note }
```

### 3.4 安装与评分

```
POST   /marketplace/apps/{id}/install     # marketplace:install
POST   /marketplace/apps/{id}/ratings       # 需已安装
DELETE /marketplace/apps/{id}/ratings/mine
```

---

## 4. 核心流程

### 4.1 Manifest 结构

```json
{
  "version": "1.0.0",
  "resources": {
    "knowledge_base": { "name": "...", "description": "..." },
    "flow": {
      "name": "...",
      "graph_json": { "...": "..." },
      "auto_publish": false
    },
    "agent": {
      "name": "...",
      "system_prompt": "...",
      "bind_kb": true,
      "bind_flow": true
    }
  }
}
```

打包时从发布方租户读取当前 `graph_json`；flow 默认 `auto_publish: false`（安装后需手动发布，除非 manifest 指定 true）。

### 4.2 状态机

```
draft → publish → pending_review → approve → published
                                 → reject  → rejected
```

### 4.3 安装

```
POST /apps/{id}/install
    → 校验 status=published、未重复安装
    → 按 manifest 顺序：create_kb → create_flow [→ publish] → create_agent
    → 写 mkt_installs，install_count++
```

安装创建的 KB 为**空壳**（名称/描述来自 manifest）；流程复制 `graph_json`；智能体按 `bind_kb` / `bind_flow` 关联新资源。

---

## 5. 前端

### 5.1 页面

- `/workbench/marketplace` — 广场 Tab（分类、标签、排序）、我的应用、待审核（有 review 权限）

### 5.2 组件

```
frontend/app/workbench/marketplace/page.tsx
frontend/components/marketplace/MarketplaceAppDetailDrawer.tsx
frontend/components/marketplace/MarketplaceStarDisplay.tsx
frontend/components/marketplace/marketplace-manifest.ts
```

---

## 6. 后端文件清单

```
backend/app/tenant/marketplace/models.py
backend/app/tenant/marketplace/views/marketplace.py
backend/app/tenant/marketplace/services/marketplace/
    catalog.py      # 浏览、列表、详情
    publish.py      # 创建、打包、提交审核
    review.py       # 审核通过/驳回
    install.py      # 安装与安装记录
backend/app/tenant/marketplace/util.py
backend/scripts/seed/marketplace.py         # 预置 mkt_categories
```

---

## 7. 测试计划

1. from-resources 打包 → publish → pending 列表可见
2. approve → 广场列表 → install → 本租户出现 flow/agent/kb
3. 重复 install → 409；未安装评分 → 403
4. reject 后 review_note 展示；tag_ids 筛选

---

## 8. 参考

- [tags-categories.md](./tags-categories.md) — 应用标签
- [flows.md](../guides/flows.md) — 流程发布与 graph_json
- [platform-agents.md](../guides/platform-agents.md) — 智能体创建
