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

**待做（非阻塞）：** 视频升格 KB、生图参考图、生成流式进度。

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
