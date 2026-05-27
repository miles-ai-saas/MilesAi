# PRD 差距 backlog

**日期：** 2026-05-27（PaddleOCR 调整为按需暂缓）  
**来源：** [prd.md](./prd.md) 文首各模块「实现对照」表中标记为 ⬜ / 部分 的项  
**维护：** 立项排期时更新优先级与状态；合入后同步改 prd 对照表与对应 `features/`

---

## 优先级说明

| 级别 | 含义 |
|------|------|
| **P0** | 影响核心 RAG/多模态承诺或大面积用户路径 |
| **P1** | 企业交付常见诉求，中等工作量 |
| **P2** | 增强体验、运维便利或已立项远期项 |
| **按需** | 无现网阻塞；有明确场景（如扫描件批量入库）再立项 |

---

## P0 — 多模态与 RAG 核心差距

> **2026-05-27 MVP 已落地**（以图搜图为 OCR 派生 + media_types 过滤；非 CLIP 向量）。真·视觉相似度检索列为 P1 增强。

| 项 | 模块 | 状态 |
|----|------|------|
| 以图搜图 / 文本搜图（MVP） | 6b | ✅ `media_types` + `query_document_id` OCR 检索 |
| 视觉向量以图搜图（CLIP 等） | 6b | ✅ CLIP Provider + visual_search |
| 视频入库 | 6b | ✅ 白名单 + `parse_video`（ffmpeg + Whisper/OCR） |

---

## P1 — 平台能力与交付

| 项 | 模块 | 说明 |
|----|------|------|
| 视觉向量以图搜图（CLIP / 多模态 embedding） | 6b | ✅ CLIP + visual_search API/UI |
| 私有应用 / 租户内可见市场包 | 7 | ✅ `visibility` + 广场过滤 |
| 应用安装后版本升级与 diff | 7 | ✅ 升级 API + diff 预览 UI |
| 批量文档入库 / 批量任务取消 | 8 | ✅ 批量上传 + batch-cancel |
| Token / 分模型调用报表 | 9 | ✅ `agt_model_usage_logs` + 监控「模型用量」 |
| 智能体定时执行历史 UI | 4 / 8 | ✅ `agt_schedule_runs` + 面板历史 |
| 会话设备列表与强制登出 UI | 1 | ✅ 多设备会话 + `/system/sessions` |
| 模型健康自动探测 cron | 3 | ✅ Beat 每 15 分钟 `probe_models_health` |
| Python 钩子 | 2 | ✅ `app.tenant.hooks.plugins.*` |
| 子流程 SubFlow | 4 | ✅ SubFlow 节点 + 编译校验 + 前端 |

---

## P2 — 体验与运维增强

| 项 | 模块 | 说明 |
|----|------|------|
| 基础设施可视化配置 UI | 1 | DB/MinIO/向量库/Celery 走 `.env` |
| Redis 缓存管理 UI | 1 | 命中率、清理 |
| 审计 / 任务日志导出 | 1 / 8 | — |
| 敏感词 Excel 导入 UI | 2 | API 批量已有 |
| 违规统计报表 | 2 | 拦截日志可查 |
| 数据脱敏、导出水印 | 2 | PRD §2.3 |
| 音视频内容安全模型审核 | 2 | 非文本合规 |
| 提示词模板导入/导出、A/B | 3 | — |
| 智能体一键导出/导入包 | 4 | CRUD 已有 |
| 流程版本 diff UI | 4 | 版本列表 + 发布已有 |
| OCR/Whisper 画布专用节点 | 4 | 能力在 KB 链 |
| 循环 / 合规画布节点 | 4 | 合规在运行时 |
| 网页搜索、代码执行等内置工具 | 5 | 部分 PRD 清单 |
| MCP 自定义协议插件 | 5 | — |
| 行业技能包种子扩充 | 5 | — |
| 应用 sandbox 试用 | 7 | — |
| 任务图表、Worker 配置 UI | 8 | Flower 独立 |
| 组件级 PG/Redis/MinIO 监控 | 9 | 建议外部 Prometheus |
| 多模态处理量专统计 | 9 | OCR/Whisper 计数 |
| PDF/Excel 报表、邮件短信告警 | 9 | Webhook 已有 |
| TTS / 语音生成 | 6b | 生图/生视频已支持 |

---

## 按需 — 有场景再立项

PRD 原文提及、现网已有替代路径，**不阻塞交付**；客户有扫描件/高精度 OCR 诉求时再排期。

| 项 | 模块 | 现网替代 | 触发条件 |
|----|------|----------|----------|
| PaddleOCR（或等价高精度 OCR） | 6b | KB 图：`pytesseract`（`[multimodal]`）；对话：Vision 模型；文档：Docling/pypdf | 大量扫描件/票据/手写/表格 OCR 入库 |
| 老格式 Office（`.doc`/`.xls`/`.ppt`） | 6 | Open XML（docx/xlsx/pptx）已支持 | 客户遗留 97-2003 文件批量迁移 |
| 云 OCR API 接入 | 6b | 同上 | 私有化不想装 Paddle、可接受外呼 |

实现形态建议：与 Docling 相同，增 `rag/parse/backends/paddleocr`（或 `PARSE_OCR_BACKEND`），不改 `pipeline/ingest` 主链。见 [layering.md](../architecture/layering.md)。

---

## 已关闭（近期）

| 项 | 说明 |
|----|------|
| Celery Beat 独立进程 | Compose `beat` 服务已默认包含 |
| 任务中心（入库 + 生成） | [task-center.md](../features/task-center.md) |
| 运营后台 | [admin-ops.md](../features/admin-ops.md) |
| 对话 WebSocket v1 | [agent-chat-websocket.md](../features/agent-chat-websocket.md) |
| 识图 / 生图 / 生视频 | [multimodal-capabilities.md](./multimodal-capabilities.md) |
| KB Office 上传白名单（docx/pptx/xlsx） | `upload_policy.py` 已含；解析需 `[parse-docling]` |
| 视频入库 MVP | `video_parser.py` + 白名单 mp4/mov/webm |
| 文本搜图 / 以图搜图 MVP | `POST /kb/{id}/search` · `media_types` · `query_document_id` |

---

## 相关文档

- [prd.md](./prd.md) — 立项原文 + 文首对照表（锚点 `as-is-module-*`）
- [multimodal-capabilities.md](./multimodal-capabilities.md) — 多模态产品状态
- [docs/README.md](../README.md) — features 索引
