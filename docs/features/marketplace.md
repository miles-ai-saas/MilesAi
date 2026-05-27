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
- **应用升级**：manifest 同步到已安装资源；升级前 **diff 预览**（KB / 流程 / 智能体字段与画布结构）
- 前端：`/workbench/marketplace`、详情 Drawer、升级 diff 对话框、星级展示

### 1.2 明确不做

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
| `installed_version` | 安装/升级时的应用版本号 |
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

### 3.4 安装、升级与评分

```
POST   /marketplace/apps/{id}/install              # marketplace:install
GET    /marketplace/apps/{id}/upgrade-preview      # 升级 diff 预览
POST   /marketplace/apps/{id}/upgrade              # 确认升级（manifest → 已安装资源）
POST   /marketplace/apps/{id}/ratings              # 需已安装
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

### 4.4 升级

```
GET  /apps/{id}/upgrade-preview
    → 对比 installed_version 与市场 version
    → 逐资源 diff：KB/Agent 名称·描述·系统提示词；Flow 名称·描述·节点数·连线数·画布结构

POST /apps/{id}/upgrade
    → 校验已安装、已发布、版本不同
    → 将 manifest.resources 同步到 install 关联的 kb/flow/agent
    → 更新 installed_version
```

**Diff 范围（v1）：** 仅 manifest 中声明的字段；不合并租户侧对资源的独立修改策略（以市场 manifest 覆盖对应字段）。KB 文档内容不在升级范围内。

**前端：**「我的安装」中 `app_version ≠ installed_version` 时显示「升级到最新版」，先打开 `MarketplaceUpgradeDialog` 预览，确认后调用 upgrade API。

---

## 5. 前端

### 5.1 页面

- `/workbench/marketplace` — 广场 Tab（分类、标签、排序）、我的安装（含升级 diff）、我的应用、待审核（有 review 权限）

### 5.2 组件

```
ui/workbench/app/workbench/marketplace/page.tsx
ui/workbench/components/marketplace/MarketplaceAppDetailDrawer.tsx
ui/workbench/components/marketplace/MarketplaceUpgradeDialog.tsx
ui/workbench/components/marketplace/MarketplaceStarDisplay.tsx
ui/workbench/components/marketplace/marketplace-manifest.ts
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
    upgrade.py      # 升级预览与 manifest 同步
backend/app/tenant/marketplace/util/
    __init__.py     # RAG 模板加载
    upgrade_diff.py # diff 纯函数
backend/tests/test_upgrade_diff.py
backend/scripts/seed/marketplace.py         # 预置 mkt_categories
```

---

## 7. 测试计划

1. from-resources 打包 → publish → pending 列表可见
2. approve → 广场列表 → install → 本租户出现 flow/agent/kb
3. 重复 install → 409；未安装评分 → 403
4. reject 后 review_note 展示；tag_ids 筛选
5. 发布方 bump version → 已安装租户 upgrade-preview 可见 diff → upgrade 后 installed_version 更新

---

## 8. 参考

- [tags-categories.md](./tags-categories.md) — 应用标签
- [flows.md](../guides/flows.md) — 流程发布与 graph_json
- [platform-agents.md](../guides/platform-agents.md) — 智能体创建
