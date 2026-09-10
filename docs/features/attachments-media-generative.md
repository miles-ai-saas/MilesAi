# 附件、媒体资产与生成任务

**状态：** 已实现  
**PRD 对照：** 模块6 多模态文件管理（会话侧）· 模块4 生图/生视频节点  
**架构：** [technical-design.md §10.1](../architecture/technical-design.md#101-多模态已实现)

---

## 1. 背景与目标

平台将 **文件存储** 与 **业务语义** 分层：

```text
sys_attachments     → blob 实体（MinIO + 元数据 + 配额）
media_assets        → 生成物目录（来源、标签、升格 KB）
generative_jobs     → 生图/生视频异步执行状态
kb_documents        → 可选「升格入库」后的 RAG 语料
```

生成物 **不自动进知识库**；用户在工作台「生成素材」中管理，按需 **promote-to-kb**。

### 1.1 交付范围

- 附件上传/列表/读内容（鉴权流，v1 无签名 URL）
- 生成完成后双写 `sys_attachments` + `media_assets`
- 生图/生视频默认走 `generative_jobs` 异步（工具、流程节点、API）
- 图片升格 KB；视频以描述 Markdown 入库
- 工作台页面：`/workbench/attachments`、`/workbench/media-assets`

### 1.2 明确不做

- 附件公开 CDN / 预签名 URL（见 [multimodal-capabilities.md §3.4](../product/multimodal-capabilities.md)）
- 生成物自动全量 ingest 进 KB
- 视频原生向量检索（升格为文本描述）

---

## 2. 数据模型

### 2.1 表 `sys_attachments`

| 字段 | 说明 |
|------|------|
| `filename` / `mime_type` / `file_size` | 文件信息 |
| `object_bucket` / `object_key` | MinIO 路径（含 `tenant_id` 前缀） |
| `purpose` | `general` / `chat_upload` / `chat_generated` / `flow_generated` 等 |
| `resource_type` / `resource_id` | 可选关联智能体、流程等 |

### 2.2 表 `media_assets`

| 字段 | 说明 |
|------|------|
| `attachment_id` | UNIQUE，指向 blob |
| `cover_attachment_id` | 视频封面（ffmpeg 抽帧，可选） |
| `kind` | `image` \| `video` |
| `source` | `agent_tool` / `flow_node` / `api` 等 |
| `source_ref_type` / `source_ref_id` | 追溯来源 |
| `prompt` | 生成 prompt 快照 |
| `kb_id` / `kb_document_id` / `promoted_at` | 升格 KB 后填写 |

### 2.3 与 `generative_jobs` 关系

异步生成时先创建 `generative_jobs`，Worker 完成后写入 attachment + media_asset，结果 JSON 含 `attachment_id`。任务中心见 [task-center.md](./task-center.md)。

---

## 3. API

### 3.1 附件 `/api/v1/attachments`

权限：`attachment:read` · `attachment:upload`

```
GET  /attachments?purpose=&resource_type=&resource_id=
POST /attachments                    # multipart 上传
GET  /attachments/meta
GET  /attachments/{id}
GET  /attachments/{id}/content       # 鉴权读字节（前端预览 / 识图 data URL）
DELETE /attachments/{id}
```

### 3.2 媒体资产 `/api/v1/media-assets`

权限：`attachment:read` · `attachment:write`

```
GET   /media-assets?kind=image&source=agent_tool&has_kb_document=false
GET   /media-assets/{id}
PATCH /media-assets/{id}             # title、tags 等
POST  /media-assets/{id}/promote-to-kb   # 升格入库
DELETE /media-assets/{id}
```

### 3.3 生成任务

见 [task-center.md §3.2](./task-center.md#32-生成任务-apiv1generativejobs)。

---

## 4. 执行链路

### 4.1 对话附图（识图输入）

```
用户上传 → POST /attachments (purpose=chat_upload)
ChatRequest.media → integrations/chat/multimodal
    → GET attachment content → data URL / 厂商 API
```

### 4.2 生图 / 生视频（输出）

```
generate_image / generate_video 工具
或 Flow ImageGenerate / VideoGenerate 节点
或 POST /generative/jobs/{image|video}
    → generative_jobs (pending)
    → Celery run_generative_{image|video}_job
    → integrations/generative/* 调厂商 API
    → persist: sys_attachments + media_assets
    → SSE 进度 / 对话轮询展示 artifact
```

### 4.3 升格知识库

```
POST /media-assets/{id}/promote-to-kb { kb_id }
    → 图片：创建 kb_document，走 ingest 流水线
    → 视频：以 prompt/描述 Markdown 入库（原视频仍在 attachment）
    → 更新 media_assets.kb_document_id / promoted_at
```

---

## 5. 前端

### 5.1 页面

| 路径 | 功能 |
|------|------|
| `/workbench/attachments` | 附件列表、上传、预览 |
| `/workbench/media-assets` | 生成素材目录、升格 KB |
| 对话工作台 | 附图上传、生成物预览、generative job 轮询/SSE |
| 流程调试面板 | `steps.artifact` + `ChatArtifactMedia` 预览 |

### 5.2 读图约定

模型侧由 **服务端读存储** 转 data URL，前端预览走 `GET …/content`，不做 OSS 预签名。详见 [multimodal-capabilities.md §3.4](../product/multimodal-capabilities.md)。

---

## 6. 后端文件清单

```
backend/app/models/attachment.py
backend/app/models/media_asset.py
backend/app/models/generative_job.py
backend/app/tenant/attachments/
backend/app/tenant/media_assets/
backend/app/tenant/generative/
backend/app/integrations/chat/multimodal.py
backend/app/integrations/generative/
backend/app/workers/tasks/generative.py
backend/cli.py                          # backfill-media-assets（历史回填）
```

---

## 7. 配置

| 项 | 说明 |
|----|------|
| `generative.daily_limit_per_tenant` | 生成日配额（sys_configs） |
| 模型 | 万相生图、豆包 `volcengine_video` 等，见 `integrations/generative/` |
| ffmpeg | 视频封面抽帧（未安装则跳过） |

---

## 8. 测试计划

1. 上传附件 → content 可读 → 对话识图可用
2. 生图 job → success → media_assets 列表可见 → promote-to-kb → KB 可检索
3. 生视频 job → SSE 进度 → 封面可选 → 升格为 Markdown 文档
4. 删除 media_asset 不 orphan MinIO（走 deletion 编排）

---

## 9. 参考

- [multimodal-capabilities.md](../product/multimodal-capabilities.md) — 多模态能力总览（含代码域与运维）
- [task-center.md](./task-center.md) — 生成任务 API 与 Worker
