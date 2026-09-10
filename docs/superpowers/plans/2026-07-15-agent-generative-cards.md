# 对话生成结果卡片化 Implementation Plan

> **归档：** 实施 checklist（2026-07-15）。**现网规格：** [features/attachments-media-generative.md](../../features/attachments-media-generative.md)、[features/agent-chat-websocket.md](../../features/agent-chat-websocket.md)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在智能体对话消息内用同一张生成卡片完成「进度 → 结果预览 → 素材库轻链」，并扩展 ChatArtifact / job.result 契约以支持落库与刷新恢复。

**Architecture:** 扩展 `ChatArtifact`（可选 `attachment_id` + `job_id`/`status`/`media_asset_id` 等）；后端异步入队时写入 pending artifact，成功时在 job.result 与同步产出中带回 `media_asset_id`；前端用 `ChatGenerativeCard` 渲染并在 `useAgentsChatGenerativeStatus` 中按 `job_id` 原地 patch；全局琥珀色进度条仅作无占位卡时的兜底。

**Tech Stack:** FastAPI/Pydantic、Celery generative jobs、React（workbench `features/agents`）、现有 WS `generative_job.*` 与 `api.retryGenerativeJob` / `cancelGenerativeJob`。

**规格：** [2026-07-15-agent-generative-cards-design.md](../specs/2026-07-15-agent-generative-cards-design.md)

## Global Constraints

- 对话优先；素材库仅文字链 `/workbench/media-assets?id=`（无 id 则链列表）
- 不做对话内入库、素材页大改、强制同步生图改异步
- 保留同轮 `generate_image` / `generate_video` 去重
- 旧消息：无 `status` 且有 `attachment_id` → 视为 success
- Commit message 使用简体中文 Conventional Commits
- workbench 新 UI 落在 `features/agents/`（及素材高亮落在 `features/media-assets/`）

---

## File map

| 文件 | 职责 |
|------|------|
| `backend/app/tenant/agents/schemas/agent.py` | ChatArtifact 契约 |
| `backend/app/integrations/langchain/tool_agent.py` | pending/success/failed artifact 产出 |
| `backend/app/integrations/generative/types.py` | Image/Video 结果带 media_asset_id(s) |
| `backend/app/integrations/generative/image/service.py` | 同步生图回传 media_asset_ids |
| `backend/app/integrations/generative/video/service.py` | 生视频回传 media_asset_id |
| `backend/app/integrations/generative/jobs/runner.py` | job.result 写入 media_asset_id(s) |
| `backend/tests/tenant/generative/test_generative_image.py` | 契约单测 |
| `ui/workbench/lib/types/agents.ts` | ChatArtifact TS |
| `ui/workbench/features/agents/lib/chat-sessions.ts` | ChatMessageArtifact |
| `ui/workbench/lib/generative-jobs.ts` | job→artifact、status 归一 |
| `ui/workbench/features/agents/components/ChatGenerativeCard.tsx` | 卡片 UI（新） |
| `ui/workbench/features/agents/components/ChatMessageThread.tsx` | 接入卡片 + 横幅条件 |
| `ui/workbench/features/agents/hooks/use-agents-chat-generative-status.tsx` | pending 插入 + job_id patch |
| `ui/workbench/features/agents/index.ts` | 按需导出 |
| `ui/workbench/features/media-assets/components/MediaAssetsPageView.tsx` | `?id=` 高亮 |

---

### Task 1: 后端 ChatArtifact 契约 + `_artifacts_from_tool_output`

**Files:**
- Modify: `backend/app/tenant/agents/schemas/agent.py`（`ChatArtifact`）
- Modify: `backend/app/integrations/langchain/tool_agent.py`（`_artifacts_from_tool_output`）
- Modify: `backend/tests/tenant/generative/test_generative_image.py`

**Interfaces:**
- Consumes: 工具 invoke `output` dict（含 `kind`、`attachment_id(s)`、`media_asset_id(s)`、`generative_job_id`、`status`、`message`）
- Produces: `ChatArtifact(..., attachment_id: UUID | None = None, status=..., job_id=..., media_asset_id=..., ...)`

- [ ] **Step 1: 写失败用例**

在 `test_generative_image.py` 新增：

```python
def test_artifacts_from_tool_output_pending_job():
    jid = uuid4()
    arts = _artifacts_from_tool_output(
        {
            "kind": "video",
            "status": "pending",
            "generative_job_id": str(jid),
            "message": "已提交",
        }
    )
    assert len(arts) == 1
    assert arts[0].attachment_id is None
    assert arts[0].status == "pending"
    assert arts[0].job_id == str(jid)
    assert arts[0].kind == "video"


def test_artifacts_from_tool_output_with_media_asset_id():
    aid = uuid4()
    mid = uuid4()
    arts = _artifacts_from_tool_output(
        {
            "kind": "image",
            "attachment_ids": [str(aid)],
            "media_asset_ids": [str(mid)],
            "mime_type": "image/png",
        }
    )
    assert arts[0].attachment_id == aid
    assert arts[0].media_asset_id == mid
    assert arts[0].status == "success"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && pytest tests/tenant/generative/test_generative_image.py::test_artifacts_from_tool_output_pending_job tests/tenant/generative/test_generative_image.py::test_artifacts_from_tool_output_with_media_asset_id -v`

Expected: FAIL（缺字段或逻辑未实现）

- [ ] **Step 3: 改 `ChatArtifact` schema**

```python
class ChatArtifact(BaseModel):
    kind: str = Field(default="image", description="产物类型：image | video | audio（扩展）")
    attachment_id: UUID | None = Field(default=None, description="附件 ID；pending 时可空")
    mime_type: str | None = Field(default=None, description="MIME 类型")
    caption: str | None = Field(default=None, description="展示说明")
    status: str | None = Field(
        default=None,
        description="pending | running | success | failed | cancelled；缺省且有 attachment 视为 success",
    )
    job_id: str | None = Field(default=None, description="异步 generative job id")
    media_asset_id: UUID | None = Field(default=None, description="生成素材 ID")
    progress_percent: int | None = Field(default=None, description="0-100")
    progress_message: str | None = Field(default=None, description="进度文案")
    error_message: str | None = Field(default=None, description="失败文案")
```

- [ ] **Step 4: 实现 `_artifacts_from_tool_output`**

1. 若 `status == "pending"` 且有 `generative_job_id`：返回 pending artifact（`job_id`、`kind`、`caption=message`）。
2. 若 `status == "failed"`：返回 failed artifact。
3. image：按 `attachment_ids` / `attachment_id`；对齐 `media_asset_ids` / `media_asset_id`；`status="success"`。
4. video：单 `attachment_id` + 可选 `media_asset_id`；`status="success"`。

- [ ] **Step 5: 跑测试确认通过**

Run: `cd backend && pytest tests/tenant/generative/test_generative_image.py::test_artifacts_from_tool_output tests/tenant/generative/test_generative_image.py::test_artifacts_from_tool_output_pending_job tests/tenant/generative/test_generative_image.py::test_artifacts_from_tool_output_with_media_asset_id -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/tenant/agents/schemas/agent.py \
  backend/app/integrations/langchain/tool_agent.py \
  backend/tests/tenant/generative/test_generative_image.py
git commit -m "$(cat <<'EOF'
feat(agents): 扩展 ChatArtifact 契约以支持 pending 与素材 ID

pending 任务可无 attachment_id；成功产物可带回 media_asset_id 供对话链路跳转。
EOF
)"
```

---

### Task 2: 生成服务与 job.result 写入 `media_asset_id`

**Files:**
- Modify: `backend/app/integrations/generative/types.py`
- Modify: `backend/app/integrations/generative/image/service.py`
- Modify: `backend/app/integrations/generative/video/service.py`
- Modify: `backend/app/integrations/generative/jobs/runner.py`
- Modify: `backend/tests/tenant/generative/test_generative_image.py`、`test_generative_video.py`

**Interfaces:**
- Consumes: `register_media_asset(...)` → MediaAsset row（含 `.id`）
- Produces: `ImageGenerateResult.media_asset_ids`；`VideoGenerateResult.media_asset_id`；`job.result["media_asset_id(s)"]`

- [ ] **Step 1: 扩展 DTO**（`media_asset_ids` / `media_asset_id` 可选字段）
- [ ] **Step 2: image/video service 使用 `row = await register_media_asset(...)` 并回填 DTO**
- [ ] **Step 3: runner 成功分支写入 `media_asset_id` / `media_asset_ids` 到 `job.result`**
- [ ] **Step 4: mock `register_media_asset` 返回 `SimpleNamespace(id=...)`；跑**

```bash
cd backend && pytest tests/tenant/generative/test_generative_image.py tests/tenant/generative/test_generative_video.py -v
```

Expected: PASS

- [ ] **Step 5: 确认工具 invoke 输出 dict 含 media_asset 字段（搜索 generate_* 包装）**
- [ ] **Step 6: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(generative): 生成结果回传 media_asset_id 写入 job.result

供对话产物卡片链到生成素材页。
EOF
)"
```

---

### Task 3: tool_agent 异步 pending 时写入 artifacts

**Files:**
- Modify: `backend/app/integrations/langchain/tool_agent.py`（约 709–732 行 pending 早退）

**Interfaces:**
- Consumes: Task 1 `_artifacts_from_tool_output`
- Produces: `ChatResponse(artifacts=[pending...], generative_jobs=[...], ...)`

- [ ] **Step 1: pending 早退时 `artifacts.extend(_artifacts_from_tool_output(output))` 并放入 `ChatResponse.artifacts`**
- [ ] **Step 2: 若 output 缺 `status`/`generative_job_id`，在调用前补全再解析**
- [ ] **Step 3: `BadRequestError` 且 slug 为 generate_* 时追加 `status=failed` artifact**
- [ ] **Step 4: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(agents): 异步生成入队时落库 pending artifact

刷新会话后仍可恢复生成中卡片，无需仅依赖内存横幅。
EOF
)"
```

---

### Task 4: 前端类型与 generativeJobToArtifacts

**Files:**
- Modify: `ui/workbench/lib/types/agents.ts`
- Modify: `ui/workbench/features/agents/lib/chat-sessions.ts`
- Modify: `ui/workbench/lib/generative-jobs.ts`

**Interfaces:**
- Produces: `effectiveArtifactStatus`、`generativeJobToArtifacts`（含新字段；多图拆多张）、`replaceArtifactsForJob`、`patchArtifactsForJobProgress`

- [ ] **Step 1: `ChatArtifact` / `ChatMessageArtifact`：`attachment_id` 可选 + status/job_id/media_asset_id/progress_*/error_message**
- [ ] **Step 2: 在 `generative-jobs.ts` 实现上述四个函数**（终态用 `replaceArtifactsForJob` 拆多图；进行中用 `patchArtifactsForJobProgress`；无同 job 卡时插入）
- [ ] **Step 3: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(ui): 对齐 ChatArtifact 类型与 job 转卡片映射

支持按 job_id 更新进度与多图拆卡。
EOF
)"
```

---

### Task 5: ChatGenerativeCard 组件

**Files:**
- Create: `ui/workbench/features/agents/components/ChatGenerativeCard.tsx`
- Modify: `ui/workbench/features/agents/index.ts`

**Interfaces:**
- Props: `artifact`, `onCancel?(jobId)`, `onRetried?(job: GenerativeJobOut)`

- [ ] **Step 1: 按 status 渲染 pending/running（占位+进度+取消）、success（大预览+素材链）、failed（错误+重试）、cancelled**
- [ ] **Step 2: 素材链：`media_asset_id ? /workbench/media-assets?id= : /workbench/media-assets`**
- [ ] **Step 3: 重试调用 `api.retryGenerativeJob`**
- [ ] **Step 4: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(agents): 新增对话生成结果卡片组件

同一卡片承载生成中、成功预览、失败与取消态。
EOF
)"
```

---

### Task 6: ChatMessageThread 接入卡片并收敛横幅

**Files:**
- Modify: `ui/workbench/features/agents/components/ChatMessageThread.tsx`

**Interfaces:**
- 新增 props：`onCancelGenerativeJob?`, `onGenerativeJobRetried?`
- 用 `effectiveArtifactStatus` 判断 in-flight，有则不渲染 `generativeStatus`

- [ ] **Step 1: artifacts 区改为 `ChatGenerativeCard` 列表**
- [ ] **Step 2: 最后一条助手仅当无 pending/running artifact 时显示 `generativeStatus`**
- [ ] **Step 3: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(agents): 消息区用生成卡片替代裸缩略图

进行中卡片可见时隐藏重复全局进度横幅。
EOF
)"
```

---

### Task 7: useAgentsChatGenerativeStatus 按 job_id 更新

**Files:**
- Modify: `ui/workbench/features/agents/hooks/use-agents-chat-generative-status.tsx`
- Modify: `ui/workbench/features/agents/hooks/use-agents-chat-messaging.tsx`
- Modify: `ui/workbench/features/agents/components/AgentsChatLayout.tsx`

**Interfaces:**
- WS/轮询 done → `replaceArtifactsForJob`；progress → `patchArtifactsForJobProgress`
- `applyResponseGenerativeJobs`：合并响应 artifacts，并为缺失的 job 补 pending

- [ ] **Step 1: 重写 merge / WS handlers 使用 Task 4 helpers**
- [ ] **Step 2: applyResponse 补 pending 占位**
- [ ] **Step 3: 接通 cancel/retry 到 Thread**
- [ ] **Step 4: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(agents): 生成进度按 job_id 原地更新对话卡片

覆盖 WS/轮询、取消与重试，减少双通道进度展示。
EOF
)"
```

---

### Task 8: 素材页 `?id=` 定位高亮

**Files:**
- Modify: `ui/workbench/features/media-assets/components/MediaAssetCard.tsx`
- Modify: `ui/workbench/features/media-assets/components/MediaAssetsPageView.tsx`

- [ ] **Step 1: card 加 `id={media-asset-${id}}` 与 highlight class**
- [ ] **Step 2: `useSearchParams` 读 id，`scrollIntoView` + 高亮约 3s**
- [ ] **Step 3: 当前页找不到时轻提示（不跨页深查）**
- [ ] **Step 4: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(media-assets): 支持从对话深链定位并高亮素材卡片

对接生成结果卡片的「在生成素材中查看」入口。
EOF
)"
```

---

### Task 9: 端到端验收

- [ ] 异步生视频：pending → 进度 → success → 素材链
- [ ] 取消 → cancelled
- [ ] 失败 + 重试（环境允许时）
- [ ] 同步生图 success + media_asset 链
- [ ] 刷新会话恢复卡
- [ ] 旧消息仅 attachment_id 仍可显示
- [ ] WS 不可用时轮询更新
- [ ] `pytest tests/tenant/generative/test_generative_image.py tests/tenant/generative/test_generative_video.py -v`
- [ ] workbench typecheck（仓库既有脚本）

---

## Spec coverage checklist

| 规格项 | Task |
|--------|------|
| ChatArtifact 扩展 / attachment 可选 | 1 |
| media_asset_id 回传 | 2 |
| 异步 pending artifact 落库 | 3 |
| 前端类型与 job 映射 / 多图拆卡 | 4 |
| ChatGenerativeCard | 5 |
| Thread + 横幅降级 | 6 |
| job_id patch、取消重试 | 7 |
| 素材页 ?id= | 8 |
| 兼容与验收 | 4+6+7+9 |

## Placeholder / 一致性自检

- 无 TBD；字段统一 `job_id`、`media_asset_id`、`progress_percent`
- 多图：success 按 `attachment_ids` 拆多卡、同 `job_id`
- 横幅降级以 Thread in-flight 判断为准
