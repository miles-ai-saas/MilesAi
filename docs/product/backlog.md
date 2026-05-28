# PRD 差距 backlog

**日期：** 2026-05-28  
**来源：** [prd.md](./prd.md) 文首各模块「实现对照」表中标记为 ⬜ / 部分 的项  
**维护：** 立项排期时更新优先级与状态；合入后同步改 prd 对照表与对应 `features/`  
**最近同步：** 2026-05-28 已与 [prd.md](./prd.md) 文首对照表、`features/*`、`technical-design.md` §16 对齐

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

> **2026-05-27 已实现**（✅ / 🔜 按需延后）

| 项 | 模块 | 状态 | 实现说明 |
|----|------|------|----------|
| 基础设施可视化配置 UI | 1 | ✅ | `GET /system/infra/status` + 监控面板 |
| Redis 缓存管理 UI | 1 | ✅ | `GET /system/infra/redis-info` + 面板 |
| 审计 / 任务日志导出 | 1/8 | ❌ 不立项 | 产品确认不做；审计查询保留 `GET /audit/logs` |
| 敏感词 Excel 导入 UI | 2 | ✅ | `ComplianceLibraryDetail` CSV 上传 |
| 违规统计报表 | 2 | 🔜 | 导出类，按需 |
| 数据脱敏 | 2 | ✅ | `compliance/desensitize.py` PII 掩码 |
| 导出水印 | 2 | 🔜 | 导出类，按需 |
| 音视频内容安全模型审核 | 2 | ✅ | `media_audit.py` Vision 审核 |
| 提示词模板导入/导出 | 3 | ✅ | 工作台 JSON 导入导出按钮 |
| 提示词模板 A/B 实验 | 3 | 🔜 | 按需延后 |
| 智能体导入包 | 4 | ✅ | `GET /agents/{id}/export` + `POST /agents/import` |
| 智能体导出包 | 4 | 🔜 | 导出类，按需 |
| 流程版本 diff UI | 4 | ✅ | `FlowVersionHistoryDialog` 对比 |
| OCR 画布节点 | 4 | ✅ | `OcrExtract` |
| Whisper 画布节点 | 4 | ✅ | `AudioTranscribe` |
| 循环画布节点 | 4 | ✅ | `LoopNode` |
| 合规画布节点 | 4 | ✅ | `ComplianceCheck` |
| 网页搜索工具 | 5 | ✅ | `web_search` DuckDuckGo |
| 代码执行工具 | 5 | ✅ | `code_execution` Runner 沙箱 |
| MCP 自定义协议插件 | 5 | ✅ | `custom` transport |
| 行业技能包种子扩充 | 5 | ✅ | 4 个新 SKILL.md |
| 应用 sandbox 试用 | 7 | ✅ | `POST /apps/{id}/trial` + 试用按钮 |
| 任务图表统计 | 8 | ✅ | 监控趋势分析 |
| Worker 配置 UI | 8 | ✅ | `GET /system/infra/worker-info` + 面板 |
| 组件级 PG/Redis/MinIO 监控 | 9 | ✅ | `/system/infra/status` 含 latency_ms |
| 多模态处理量专统计 | 9 | ✅ | MonitorStats 图片/音频/视频计数 |
| 邮件告警 | 9 | ✅ | SMTP + `email_notify_to` |
| 短信告警 | 9 | 🔜 | 按需 |
| PDF/Excel 报表 | 9 | 🔜 | 导出类，按需 |
| TTS / 语音生成 | 6b | ✅ | `generate_speech` CosyVoice |

---

## 不立项 — 产品确认不做

| 项 | 模块 | 说明 |
|----|------|------|
| 审计 / 任务日志 CSV·Excel 导出 | 1/8 | 不做专导出；现网审计列表查询已满足 |

---

## 按需 — 有场景再立项

PRD 原文提及、现网已有替代路径，**不阻塞交付**。

| 项 | 模块 | 现网替代 | 触发条件 |
|----|------|----------|----------|
| PaddleOCR（或等价高精度 OCR） | 6b | KB 图：`pytesseract`（`[multimodal]`）；对话：Vision；文档：Docling/pypdf | **后续版本**；有扫描件/票据/手写批量入库需求时再排 |
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
