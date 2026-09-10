# PRD 差距 backlog

**来源：** [prd.md](./prd.md) 文首各模块「实现对照」表中标记为 ⬜ / 部分 的项  
**维护：** 立项排期时更新优先级与状态；合入后同步改 prd 对照表与对应 `features/`

---

## 优先级说明

| 级别 | 含义 |
|------|------|
| **P2** | 增强体验、运维便利或已立项远期项 |
| **按需** | 无现网阻塞；有明确场景（如扫描件批量入库）再立项 |

---

## 待排期（🔜 按需延后）

| 项 | 模块 | 说明 |
|----|------|------|
| 违规统计报表 | 2 | 导出类，按需 |
| 导出水印 | 2 | 导出类，按需 |
| 提示词模板 A/B 实验 | 3 | 按需延后 |
| 智能体导出包 | 4 | 导出类，按需（导入包已实现） |
| 短信告警 | 9 | 按需 |
| PDF/Excel 报表 | 9 | 导出类，按需 |

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
| PaddleOCR（或等价高精度 OCR） | 6b | KB 图：`pytesseract`（`[multimodal]`）；对话：Vision；文档：Docling/pypdf | 有扫描件/票据/手写批量入库需求时再排 |
| 老格式 Office（`.doc`/`.xls`/`.ppt`） | 6 | Open XML（docx/xlsx/pptx）已支持 | 客户遗留 97-2003 文件批量迁移 |
| 云 OCR API 接入 | 6b | 同上 | 私有化不想装 Paddle、可接受外呼 |

实现形态建议：与 Docling 相同，增 `rag/parse/backends/paddleocr`（或 `PARSE_OCR_BACKEND`），不改 `pipeline/ingest` 主链。见 [layering.md](../architecture/layering.md)。

---

## 相关文档

- [prd.md](./prd.md) — 立项原文 + 文首对照表（锚点 `as-is-module-*`）
- [multimodal-capabilities.md](./multimodal-capabilities.md) — 多模态产品状态
- [docs/README.md](../README.md) — features 索引
