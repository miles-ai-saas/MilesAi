# 智能体对话：生成结果卡片化（进度 → 结果 → 素材库联动）

**日期：** 2026-07-15  
**状态：** 待实现  
**范围：** 对话优先；素材库仅必要联动  
**选定方案：** 生成结果卡片化（消息内同一卡片承载 pending → progress → success/failed）

## 背景与目标

当前对话生图/生视频体验割裂：底部琥珀色进度横幅与消息内小缩略图是两套 UI；产物难预览；与「生成素材」几乎无入口。近期已有同轮 `generate_image` / `generate_video` 去重与会话游标分页，本设计在其上统一交互。

**成功标准（对话优先）：**

1. 用户在同一消息位置看到：排队/进度（可取消）→ 大预览 → 失败可理解（可选重试）
2. 成功产物可轻链进入「生成素材」列表（有 id 时可定位）
3. 旧会话/旧字段兼容；不同时强制同步生图改为异步 job

**明确不做：**

- 对话内「加入知识库」
- 素材页大改版、A2A/配置向导大改
- 把已有同步生图路径全部改成强制 job

## 心智模型

```text
用户确认工具 / 自动执行
        ↓
助手消息内出现 ChatGenerativeCard（pending）
        ↓
WS 或轮询 patch 同卡（progress%）
        ↓
success → 大预览 + 「在生成素材中查看」
failed / cancelled → 错误态（failed 可重试）
```

全局琥珀色横幅降级为兜底：仅当已有 job 但消息上尚未挂上 pending artifact 时使用。

## 数据契约

### `ChatArtifact` 扩展

后端：`backend/app/tenant/agents/schemas/agent.py`  
前端：`ui/workbench/lib/types/agents.ts`（及 `chat-sessions` 中镜像类型）

| 字段 | 类型 | 说明 |
|------|------|------|
| `kind` | string | `image` \| `video`（现有） |
| `attachment_id` | UUID \| null | **改为可选**；pending 时可无；success 必填 |
| `mime_type` | string \| null | 现有 |
| `caption` | string \| null | 现有 |
| `status` | string \| null | `pending` \| `running` \| `success` \| `failed` \| `cancelled`；缺省且有 attachment → 视为 success（兼容旧数据） |
| `job_id` | string \| null | 异步任务 ID；进度/取消/重试 |
| `media_asset_id` | string \| null | 成功后链到素材库 |
| `progress_percent` | number \| null | 0–100 |
| `progress_message` | string \| null | 进度文案 |
| `error_message` | string \| null | 失败文案 |

会话消息 `artifacts` 为 JSONB，`model_dump` 即可落库，无需改表。

### 兼容规则

- 历史消息：无 `status` + 有 `attachment_id` → 按 `success` 渲染
- 无 `media_asset_id`：隐藏深链或仅链到 `/workbench/media-assets` 列表
- `n>1` 多图：每张图一张卡片（实现简单，进度可只在第一张挂 job，或每张共享同一 `job_id` 完成后拆卡——优先「完成后按 attachment 拆多张 success 卡」）

## 前端设计

### 组件：`ChatGenerativeCard`

路径：`ui/workbench/features/agents/components/ChatGenerativeCard.tsx`

| 状态 | UI |
|------|-----|
| pending / running | `aspect-[4/3]` 灰底占位 + 进度条 + 文案 +「取消」 |
| success | 较大预览（约 `max-h-80`）+ 点击大图/播视频 |
| failed | `error_message` +「重试」（调用现有 retry API） |
| cancelled | 「已取消」 |

成功态底部文字链：「在生成素材中查看」→ `/workbench/media-assets`；有 `media_asset_id` 时 `?id=<uuid>`。

### `ChatMessageThread`

- 助手消息 artifacts 用 `ChatGenerativeCard` 列表替代裸 `ChatArtifactMedia`
- 存在进行中卡片时不重复挂全局横幅

### `useAgentsChatGenerativeStatus`

- WS/轮询：按 `job_id` **原地 patch** 对应 artifact（进度、附件、失败），而非仅 append 新 attachment
- 首响应仅有 `generative_jobs`：在最后一条助手消息插入 pending 占位 artifact
- 更新 `generativeJobToArtifacts`（`lib/generative-jobs.ts`）输出新字段，并从 `job.result` 读取 `media_asset_id`

### 素材库联动（最小）

- 仅上述链接；素材页若存在 `?id=`，滚动定位并短暂高亮对应卡片（小改动则做）

### 工具确认

- 沿用 `generative-tool-ui` 确认/busy 文案；卡片在确认后或响应返回后出现，不另开弹窗

## 后端设计

### Schema

- 扩展 `ChatArtifact`；`attachment_id` 可选（Pydantic + OpenAPI）

### 工具输出 → artifact

- `register_media_asset` 已返回 row：同步生图路径写入 `media_asset_id`（多图列表对齐）
- 异步入队：`ChatResponse.artifacts` 同步写入 pending 占位（`job_id`、`kind`、`status=pending`），便于落库后刷新仍见卡
- job `result` 成功时写入 `media_asset_id` + 现有 `attachment_id(s)`，供 WS `done` / GET job 使用

### 工具逻辑配套

- 保留同轮 generate 去重
- 确认后执行失败：返回 `status=failed` + `error_message` 的 artifact（或可被前端映射的 steps）
- 重试：现有 `retry_generative_job`；前端用新 `job_id` 更新/替换卡片

### 错误与边界

| 场景 | 行为 |
|------|------|
| WS 断线 | 回退轮询；卡片保持「生成中」 |
| 取消中 | → `cancelled`，不可再取消 |
| 无 media_asset_id | 弱链列表页或不显示深链 |
| 旧前端忽略新字段 | 仍能显示有 attachment 的成功图 |

## 涉及主要文件

**后端**

- `backend/app/tenant/agents/schemas/agent.py` — ChatArtifact
- `backend/app/integrations/langchain/tool_agent.py` — pending/success/failed 产出
- `backend/app/integrations/generative/image/service.py`、`video/service.py` — result 带 media_asset_id
- `backend/app/tenant/agents/services/chat_sessions.py` — 确认 dump 含新字段

**前端**

- `ui/workbench/lib/types/agents.ts`、`lib/generative-jobs.ts`
- `features/agents/components/ChatGenerativeCard.tsx`（新）
- `features/agents/components/ChatMessageThread.tsx`
- `features/agents/hooks/use-agents-chat-generative-status.tsx`
- `features/media-assets/...` — 可选 `?id=` 高亮

## 测试要点

1. 异步生视频：确认 → pending 卡 → 进度 → success 大预览 + 素材链接
2. 取消：卡片 → cancelled
3. 失败与重试（若启 retry）
4. 同步生图：直接 success 卡且有 media_asset_id（若后端已带回）
5. 刷新会话：pending/成功卡片从 JSONB 恢复且行为正确
6. 旧消息（仅 attachment_id）：仍正常显示
7. WS 不可用时轮询路径仍能更新卡片

## 实现顺序建议

1. 契约：ChatArtifact 前后端 + generativeJobToArtifacts / job.result
2. ChatGenerativeCard + Thread 接入（success/旧数据先跑通）
3. status hook：pending 占位 + 按 job_id patch；横幅降级
4. 后端 pending artifact 落库、media_asset_id 回传
5. 取消/失败/重试与素材页 `?id=` 高亮
