# 多模态能力 — 技术总览与实施路线

**日期：** 2026-05-26  
**状态：** 核心已落地（识图、RAG 带图、万相/豆包生图生视频、媒体资产、回填 CLI、生成日配额）  
**产品说明：** [multimodal-capabilities.md](../product/multimodal-capabilities.md)

---

## 1. 文档地图

| 能力 | 产品文档 | 技术设计 | 主要代码域 |
|------|----------|----------|------------|
| 生文 | [multimodal-capabilities.md §2](../product/multimodal-capabilities.md) | [flows.md](../guides/flows.md)、[platform-agents.md](../guides/platform-agents.md) | `ainvoke_chat`、`AgentService.chat` |
| 识图（输入） | §3 | [flow-llm-multimodal-design.md](./flow-llm-multimodal-design.md)、[agent-multimodal-design.md](./agent-multimodal-design.md) | `integrations/chat/multimodal`、`llm_nodes` |
| 生图/生视频（输出） | §4 | [flow-generative-media-design.md](./flow-generative-media-design.md) | `integrations/generative`（万相 + 豆包 `volcengine_video`） |
| 资料入库 | §5 | [knowledge-base.md](../guides/knowledge-base.md)、[media-assets-design.md](./media-assets-design.md) | `app/rag/parse`、`media_assets` |

---

## 2. 共享基础设施

```text
integrations/chat/multimodal.py   # build_user_message、resolve_media_refs
tenant/attachments/...            # 上传、GET .../content 读字节
integrations/generative/          # 生图/生视频 + quota + volcengine_client
media_assets                      # 生成物目录 + promote-to-kb（图片）
```

### 2.1 附件与读图（无签名 URL）

- 模型侧：服务端读字节 → data URL 或厂商 API。
- 前端预览：`GET /api/v1/attachments/{id}/content`（鉴权流）。

---

## 3. 实施顺序

```text
1. ✅ integrations/chat/multimodal + GET /attachments/{id}/content
2. ✅ Agent / Flow 识图、RAG 带 media
3. ✅ integrations/generative + generate_image / generate_video 工具
4. ✅ Flow ImageGenerate / VideoGenerate + 画布
5. ✅ 豆包 volcengine_video（contents/generations/tasks）
6. ✅ media_assets + 升格 KB（图片）+ 工作台「生成素材」
7. ✅ backfill-media-assets CLI + generative.daily_limit_per_tenant
8. ✅ 有 KB + enable_generative_tools → tool_agent（knowledge_search + generate_*）
9. ✅ 流程调试面板生成物预览（steps.artifact + ChatArtifactMedia）
```

**P2 已完成：**

- 生视频异步任务：`generative_jobs` 表 + `POST/GET /generative/jobs` + Celery `run_generative_video_job`
- 智能体工具 / 流程 `VideoGenerate` 默认异步（`generative_video_async`）；流程调试 `async_generative` 可关同步
- 对话与流程调试面板轮询任务完成后展示视频
- 视频升格 KB：以生成描述 Markdown 入库（原视频仍在 attachment）

**P2+ 已完成（体验闭环）：**

- `GET /generative/jobs` 分页列表 + `GET /generative/jobs/meta`（状态/来源筛选枚举）
- SSE：`GET /generative/jobs/{id}/stream`；`POST .../cancel`；前端进度条与取消
- 工作台 **任务中心**（`/workbench/tasks?category=generative`）聚合生成任务

**P2+ 已完成（生图异步）：**

- 生图 `generative_jobs`（`kind=image`）+ Celery `run_generative_image_job`
- 工具 `generate_image`、流程 `ImageGenerate` 默认异步（`generative_image_async`）；流程调试 `async_generative` 可关同步
- `POST /generative/jobs/image`；任务中心列表含生图/生视频

**P3 已完成：**

- 视频封面 `media_assets.cover_attachment_id`（ffmpeg 抽首帧，未安装则跳过）
- 识图多轮：`agent.config.carry_forward_media` + 对话工作台自动沿用上一轮附图
- 流程模板 `GET /flows/templates`（registry + 创建/插入模板 UI，此前已落地）

**待做（实时通道，见设计稿）：**

- [realtime-transport-design.md](./realtime-transport-design.md)：**对话 WebSocket** + **生成任务/任务中心 SSE** 分场景；非全站 WS
- ~~任务失败重试 API~~（✅ `POST /generative/jobs/{id}/retry`）
- ~~任务中心：关联 Celery 记录、类型筛选~~（✅）

**P1 已完成：**

- 画布生图/生视频节点附件选择器（`AttachmentIdField`）
- 高分辨率/多张生图工具二次确认（`integrations/generative/policy`）
- 生成 prompt 合规扫描（`SCAN_MODULE_GENERATIVE`）

---

## 4. 运维

| 操作 | 命令 / 配置 |
|------|-------------|
| 历史生成物登记 | `python cli.py backfill-media-assets [--dry-run]` |
| 生成日限额 | `system_config` → `generative.daily_limit_per_tenant`（0=不限） |
| 迁移 | `python cli.py migrate`（含 `media_assets` 表） |

---

## 5. 变更记录

| 日期 | 说明 |
|------|------|
| 2026-05-26 | 初版 |
| 2026-05-26 | 豆包视频、配额、回填；KB+生图工具路由 |
| 2026-05-26 | 图生图、首尾帧生视频；P0 文档对齐与生视频确认/进度文案 |
| 2026-05-26 | P1：附件选择器、高分辨率生图确认、生成 prompt 合规扫描 |
| 2026-05-26 | P2：异步生视频任务、轮询 UI、视频升格 KB（描述入库） |
| 2026-05-26 | SSE 进度流、任务取消、进度条 UI |
| 2026-05-26 | 任务中心生成任务 Tab；列表/meta API；产品文档与路线图同步 |
| 2026-05-26 | 生图异步任务（generative_image_async、ImageGenerate、generate_image） |
| 2026-05-26 | 视频封面、识图多轮附图；确认流程模板 API 已上线 |
| 2026-05-26 | 新增 [realtime-transport-design.md](./realtime-transport-design.md)（对话 WS + 资源 SSE） |
