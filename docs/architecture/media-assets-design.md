# 生成物与媒体资产（Media Assets）

**日期：** 2026-05-26  
**状态：** v2 已实施（表 + API + 生成双写 + 工作台「生成素材」；视频升格 KB 已实现）  
**文档类型：** 设计归档  
**As-Is 规格：** [features/attachments-media-generative.md](../features/attachments-media-generative.md)  
**关联：** [flow-generative-media-design.md](./flow-generative-media-design.md)、[multimodal-capabilities.md](../product/multimodal-capabilities.md)

---

## 1. 结论（产品 + 技术）

| 决策 | 说明 |
|------|------|
| **不默认自动写入知识库** | 生成图/视频的主价值是文件本体与流程串联；静默进 KB 会带来解析成本、权限边界混乱、视频能力缺口 |
| **引入租户级「媒体资产」** | 在 **`sys_attachments`（blob）** 之上登记 **`media_assets`（目录与治理）**；OSS 只存一份 |
| **升格入库（可选动作）** | 用户在工作台选择目标 KB → 创建 `kb_documents` 并走现有解析/向量流水线；资产表可记录 `kb_document_id` |

与技能包目录内 `assets/`（包内静态文件路径）**命名区分**：本方案表名建议 **`media_assets`** 或 **`creative_assets`**，勿与 Skill 布局混淆。

---

## 2. 概念分层

```text
┌─────────────────────────────────────────────────────────────┐
│  media_assets（资产目录：谁生成、能否复用、是否已升格 KB）      │
└───────────────────────────┬─────────────────────────────────┘
                            │ attachment_id (FK, 唯一 blob)
┌───────────────────────────▼─────────────────────────────────┐
│  sys_attachments（文件实体：OSS object_key、配额、purpose）     │
└───────────────────────────┬─────────────────────────────────┘
                            │ 用户「加入知识库」
┌───────────────────────────▼─────────────────────────────────┐
│  kb_documents → chunks → vectors（RAG 检索语料，按 KB 隔离）  │
└─────────────────────────────────────────────────────────────┘
```

| 层 | 回答的问题 |
|----|------------|
| **Attachment** | 文件在哪、多大、谁上传、扣哪类存储配额 |
| **Media Asset** | 这是不是「可管理的创作物」、从哪次 agent/flow 来、能否再打标签/复用 |
| **KB Document** | 是否进入某个知识库的检索索引 |

当前实现：生成物写入 **`sys_attachments`**（`purpose ∈ { chat_generated, flow_generated }`）并登记 **`media_assets`**；工作台 **「生成素材」**（`/workbench/media-assets`）已上线。详见 [features/attachments-media-generative.md](../features/attachments-media-generative.md)。

---

## 3. 表设计（已实现）

表名：**`media_assets`**（租户域，建议前缀与现有约定对齐，如 `med_assets` 或放 `sys_media_assets`，实施时与 `technical-design.md` §库表统一）。

| 列 | 类型 | 说明 |
|----|------|------|
| `id` | UUID PK | |
| `tenant_id` | UUID | 租户隔离 |
| `attachment_id` | UUID UNIQUE | 指向 `sys_attachments.id`；**禁止重复存 blob** |
| `kind` | varchar(16) | `image` \| `video`（后续 `audio`） |
| `source` | varchar(32) | `agent_tool` \| `flow_node` \| `manual_promote` |
| `source_ref_type` | varchar(32) NULL | `agent` \| `flow` \| `flow_run` \| `tool_invocation` |
| `source_ref_id` | UUID NULL | 与 source 组合追溯 |
| `prompt` | text NULL | 生成时 prompt（快照） |
| `model_config_id` | UUID NULL | 使用的 `image_gen` / `video_gen` 配置 |
| `title` | varchar(512) NULL | 用户可编辑展示名 |
| `tags` | jsonb NULL | 字符串数组，v2 |
| `kb_id` | UUID NULL | 升格目标库（冗余便于筛选） |
| `kb_document_id` | UUID NULL | 升格后写入；未升格为空 |
| `promoted_at` | timestamptz NULL | 升格时间 |
| `created_by` | UUID | 等同 attachment.uploaded_by 或操作者 |
| `created_at` / `updated_at` | timestamptz | |
| `deleted_at` | timestamptz NULL | 软删；删资产不强制删 attachment（可 GC 策略另定） |

**索引建议：** `(tenant_id, created_at desc)`、`(tenant_id, kind)`、`(tenant_id, kb_document_id)` where not null、`attachment_id` unique。

**约束：** 同一 `attachment_id` 至多一条资产；升格后 `kb_document_id` 不可指向他租户文档。

---

## 4. 与现有 `purpose` 的关系

| 场景 | attachment.purpose | 是否写 media_assets |
|------|-------------------|---------------------|
| 对话 `generate_image` / `generate_video` | `chat_generated` | **是**（v2 起） |
| 流程 `ImageGenerate` / `VideoGenerate` | `flow_generated` | **是** |
| 用户对话附图（识图） | `chat` | 否（非生成物目录） |
| 流程调试附图 | `flow` | 否 |

v1 可仅用附件列表 + `purpose` 筛选；**v2 生成时双写** `persist_generated_bytes` → `register_media_asset(...)`。

---

## 5. API（租户 API，已实现）

前缀：`/api/v1/media-assets`（名称实施时可调整为 `/creative-assets`）。

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 分页列表；筛选 `kind`、`source`、`tag`、时间范围、是否已升格 `has_kb_document` |
| GET | `/{id}` | 详情 + `attachment` 元数据（不含 object_key） |
| PATCH | `/{id}` | 更新 `title`、`tags` |
| DELETE | `/{id}` | 软删资产（可选同步删 attachment，默认仅软删资产行） |
| POST | `/{id}/promote-to-kb` | **升格入库** body: `{ kb_id, filename?, run_parse: true }` |

**升格入库 `promote-to-kb` 行为：**

1. 校验资产未删除、`kb_document_id` 为空。  
2. 从 attachment 读 object_key，在目标 KB 创建 `kb_documents`（可复用现有「从 OSS 复制/同一 bucket 引用」策略，与上传文档路径对齐）。  
3. 触发既有 Celery 解析任务（图片 OCR / 占位文本；视频 v3 再定义）。  
4. 回写 `media_assets.kb_id`、`kb_document_id`、`promoted_at`。  

预览/下载：仍走 **`GET /attachments/{id}/content`**（鉴权），资产 API 只返回 `attachment_id`。

---

## 6. 代码接入点（实施时）

| 步骤 | 位置 |
|------|------|
| 模型 + Alembic | `app/models/media_asset.py` |
| 登记 | `integrations/generative/persist.py` 在 `persist_generated_bytes` 成功后调用 `MediaAssetService.register_from_attachment` |
| 升格 | `app/tenant/media_assets/services/` 调 `tenant/kb` 文档创建 + 任务下发 |
| 权限 | 与 attachment 相同租户；升格需 KB 写权限 |
| 配额 | 附件存储仍走 `assert_can_upload_bytes`；升格入库额外计 KB 文档配额（沿用 KB 规则） |
| 前端 | 工作台「生成素材」列表 + 详情 +「加入知识库」；对话/流程生成成功后可跳转 |

**后续已补：** 历史附件回填 ``python cli.py backfill-media-assets``；生成日配额 ``generative.daily_limit_per_tenant``（见 ``integrations/generative/quota.py``）。  
**仍待：** 流式进度（见 [multimodal-roadmap.md](./multimodal-roadmap.md)）。

---

## 7. 实施阶段

| 阶段 | 交付 |
|------|------|
| **v1.5** | 仅附件：列表筛 `chat_generated` / `flow_generated` + 展示 prompt（metadata 可先 JSON 存在 attachment 扩展字段，无新表） |
| **v2** | `media_assets` 表 + 生成双写 + 素材库 CRUD API |
| **v2.1** | `promote-to-kb` + 工作台升格 UI |
| **v3** | 视频升格策略（关键帧/描述文本）、标签、合集、审计日志 |

---

## 8. 非目标（与 flow-generative-media-design 一致）

- 生成完成 **自动** 创建 `kb_documents`（无用户确认）  
- 在 `LLMCall` 内隐式生图  
- 资产表重复存储 OSS 字节  
- 与 Skill 包 `assets/` 目录合并

---

## 9. 生成模型默认厂商优先级

未在工具/节点/智能体中指定 ``generative_*_model_id`` 时，``pick_default_generative_model`` 在租户/平台启用模型中按顺序选取：

1. ``vendor=qwen``（通义万相）
2. ``vendor=doubao``
3. 其它 vendor

解析到模型后，``registry.resolve_invoke_mode`` 再路由到万相或豆包 HTTP Provider。

---

## 10. 变更记录

| 日期 | 说明 |
|------|------|
| 2026-05-26 | 初版：不自动入库 KB、media_assets 表与升格 API、分阶段实施 |
| 2026-05-26 | 补充默认模型 qwen 优先选取说明 |
| 2026-05-26 | 回填 CLI、生成日配额配置键 |
