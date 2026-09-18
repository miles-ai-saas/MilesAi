# 安全合规

**状态：** 已实现  
**PRD 对照：** 模块2 安全合规模块  
**架构：** [technical-design.md §11.1](../architecture/technical-design.md#111-合规) · [compliance-word-libraries.md](../guides/compliance-word-libraries.md)

---

## 1. 背景与目标

租户可维护 **多词库** 敏感词，配置 **扫描绑定**，在智能体对话、流程运行等路径对入参/出参扫描；命中 `warn` 或 `block`，并写 **拦截日志**。

### 1.1 交付范围

- 词库 CRUD、库内词条（单条/批量）、词条跨库关联
- 租户级扫描绑定（启用哪些词库参与扫描）
- `POST /compliance/scan` 试跑
- 对话/流程集成：`ComplianceService.check_input` / `check_output`
- 前端：`/workbench/compliance`

### 1.2 明确不做 / 局限

- Python 钩子（见 [hooks.md](./hooks.md)；合规独立）
- 违规统计专报表与导出（拦截日志可查；报表按需）
- 导出水印（按需）
- 多模态 OCR 结果自动合规（需文本化后再扫；画布可用 `ComplianceCheck`）
- **PII 脱敏**与**音视频 Vision 审核**均未生效：`desensitize.py`（PII 掩码）曾实现但全仓
  零调用方，已删除；`services/compliance/media_audit.py` 保留实现但仍无调用方，且只覆盖
  `image/*`（音/视频走「非图片附件 ⇒ safe」短路）。两者按需立项后再实现/接线

### 1.3 已增强（P2）

- 词库 **CSV 批量导入** UI（`ComplianceLibraryDetail`）

---

## 2. 数据模型

| 表 | 说明 |
|----|------|
| `cmp_word_libraries` | 词库（租户内 name 唯一） |
| `cmp_sensitive_word_entries` | 词条（租户内 word 唯一） |
| `cmp_library_word_bindings` | 库-词 M:N，含 `action`: warn/block |
| `cmp_compliance_library_bindings` | 租户启用哪些库参与扫描 |
| `cmp_intercept_logs` | 拦截记录 |

种子：新租户创建时自动「默认词库」（`DEFAULT_WORD_LIBRARY_NAME`）。

---

## 3. API

前缀：`/api/v1/compliance`  
权限：`compliance:read` · `compliance:write`

```
GET  /compliance/meta
GET  /compliance/bindings
PUT  /compliance/bindings
GET  /compliance/libraries
POST /compliance/libraries
GET  /compliance/libraries/{id}/words
POST /compliance/libraries/{id}/words
POST /compliance/libraries/{id}/words/batch
PATCH/DELETE …/words/{binding_id}
GET  /compliance/entries/{entry_id}
PUT  /compliance/entries/{entry_id}/libraries
POST /compliance/scan
GET  /compliance/logs
```

---

## 4. 运行时集成

```
AgentService.chat
    → check_input(query) → 执行 → check_output(answer)
FlowService.run
    → 同上（按 agent/flow 配置）
```

命中 `block` 抛业务错误并写 `cmp_intercept_logs`；`warn` 可记录后继续（按实现策略）。

---

## 5. 前端

- `/workbench/compliance` — 词库、词条、扫描绑定、拦截日志
- `GET /compliance/meta` — 枚举文案

---

## 6. 后端文件清单

```
backend/packages/miles-portal/src/miles_portal/tenant/compliance/models.py
backend/packages/miles-portal/src/miles_portal/tenant/compliance/views/compliance.py
backend/packages/miles-portal/src/miles_portal/tenant/compliance/services/compliance/
backend/packages/miles-portal/src/miles_portal/tenant/compliance/services/word_resolve.py
backend/packages/miles-portal/src/miles_portal/tenant/agents/services/agent/   # 调用合规
```

---

## 7. 测试计划

1. 创建词库 + block 词条 → scan 命中 → logs 有记录
2. bindings 未启用库 → scan 不命中
3. 对话 block 词 → chat 4xx + log
4. 词条跨库 action 不一致时以绑定为准

---

## 8. 参考

- [compliance-word-libraries.md](../guides/compliance-word-libraries.md)
- [hooks.md](../guides/hooks.md) — 钩子与合规并行
