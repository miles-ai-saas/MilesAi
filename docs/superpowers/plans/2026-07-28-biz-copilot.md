# Biz Copilot（业务协作助手）技术方案

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 AI 工作台落地「业务协作助手」作为路由/澄清层，业务中心仅提供带上下文的 deep link 捷径；复用现有对话页与 `project_ai` 推荐，不新建内嵌聊天壳。

**Architecture:** Copilot 是租户级智能体（tag `biz-copilot`），对话仍走 `/workbench/agents/chat/`。业务上下文以 sessionStorage + URL（`biz=1`/`projectId`/`wpId`）传递，chat 页在 storage 缺失时用 `getProjectAiContext` 回补。MVP 不做服务端自动切 Agent；路由靠 deep link 选中推荐 Agent + Copilot 文案引导用户切换。

**Tech Stack:** Next.js workbench（静态导出 trailingSlash）、现有 agents chat 状态机、`GET /biz/projects/{id}/ai-context`、TenantTag → Agent 绑定、sessionStorage `miles:biz-context`。

## Global Constraints

- 对话产品归属 **AI 工作台**；业务中心只做捷径，不内嵌完整聊天。
- Copilot **不执行写业务数据**（不结项、不改预算/合同）；最多给业务页链接。
- 涉密客户：`rag_enabled=false` 时禁止外部 RAG/案例；**仍可注入项目摘要**（与当前「完全不 prepend」不同，需修正）。
- URL 必须带尾斜杠：`/workbench/agents/chat/?…`
- Commit message 简体中文 Conventional Commits；UI 新代码落 `features/<域>/`。
- 跨分区 deep link 沿用 `buildAgentChatDeepLink`，勿另起一套 storage key。

---

## 产品与技术边界

| 层级 | 职责 | 落地位置 |
|------|------|----------|
| 专业智能体 | 按服务线创作（文案/活动等） | 已有 `agent_tag` + seed |
| Biz Copilot | 澄清对象、带上下文开聊、引导切专业体 | 新 Agent + 入口 |
| 业务捷径 | 项目页头 /（可选）业务顶栏 | deep link → chat |
| 对话壳 | 会话/消息/Banner | 现有 agents chat |

**不做（MVP）：** 业务壳内嵌聊天、服务端根据意图自动换 Agent、Copilot 写操作工具、把 Copilot 当业务总控 Dashboard。

---

## 现状依赖（已有）

| 能力 | 路径 |
|------|------|
| 上下文存储/deep link | `ui/workbench/features/projects/lib/business-context.ts` |
| 注入首条 query | `use-agents-chat-messaging.tsx` → `prependBusinessContext` |
| Banner | `BusinessContextBanner.tsx` |
| 项目页头入口 | `ProjectOpenChatButton.tsx` |
| AI 推荐 Tab | `ProjectAiTab.tsx` |
| 路由状态机 | `use-agents-chat-route.ts` / `agents-chat-href.ts` |
| 后端上下文 | `backend/app/biz/services/project_ai.py` · `GET …/ai-context` |
| Tag 解析 Agent | `_resolve_agent_by_tag` |

**已知缺口：** 无 `biz-copilot` Agent；全局/业务顶栏无入口；`projectId` 在 URL 但 storage 空时不回补；`wpId` 未消费；`rag_enabled=false` 时完全不注入摘要；页头打开对话不带默认 Agent；`biz=1` 不自动建会话。

---

## 目标架构

```text
[业务中心]
  项目「打开对话」 / 工作包「针对此工作包提问」 / （可选）顶栏捷径
       │ buildAgentChatDeepLink + saveBusinessContext
       ▼
[AI 工作台 /workbench/agents/chat/?agent=&projectId=&wpId=&biz=1&prompt=]
       │
       ├─ hydrate: storage miss → getProjectAiContext(projectId, wpId)
       ├─ Banner: 展示项目/WP，链回业务详情
       ├─ 若 agent=Copilot 或无 agent → 选中 Copilot（可配置）
       └─ 若 agent=专业体 → 直接专业创作（已有）
       │
       ▼
  prependBusinessContext(query) → POST /agents/{id}/chat
```

### 上下文分层（实现约定）

| 层 | 来源 | MVP |
|----|------|-----|
| L0 租户/用户 | auth store | 隐式（Agent 权限） |
| L1 路由意图 | URL `biz` + 可选最近项目 | 可选 chip，二期 |
| L2 对象摘要 | `context_text` + 元数据 | **必做** |
| L3 任务 | `chat_hint` / `prompt` / 复盘 prompt | 已有 deep link |

### 涉密策略修正

```ts
// 目标行为
prependBusinessContext(userText, ctx):
  if (!ctx) return userText
  // 始终注入项目摘要（含涉密提示行，后端已写入 context_text）
  // ragEnabled 仅影响：是否展示 related_cases、是否允许 KB 工具（Agent 侧）
  return header + userText
```

---

## 文件与职责（拟新增/修改）

| 文件 | 职责 |
|------|------|
| `backend/scripts/seed/biz_ai.py`（或新 seed） | 创建 `biz-copilot` Agent + tag 绑定 + 系统提示 |
| `backend/.../project_ai.py` + schema | `default_agent_id` / `copilot_agent_id`（解析 `biz-copilot` tag） |
| `ui/.../business-context.ts` | 修正 prepend；可选 `resolveBizChatHref` 统一拼链 |
| `ui/.../use-agents-chat-page.tsx` | URL `projectId` hydrate；`biz=1` 落地体验 |
| `ui/.../BusinessContextBanner.tsx` | 清除时同步清 URL query |
| `ui/.../ProjectOpenChatButton.tsx` | 优先带 `copilot` 或推荐 `default_agent_id` |
| `ui/.../BizTopBar.tsx` 或 dashboard | **可选**轻量「AI 助手」捷径 → Copilot |
| `ui/.../features/agents/...` 测试 | hydrate / prepend / href 单测 |

---

## Phase 划分

### Phase 1 — MVP（本方案主交付）

1. Seed Biz Copilot Agent（系统提示 + `biz-copilot` tag）
2. `ai-context` 增加 `copilot_agent_id`（及 name）
3. 上下文韧性：storage miss → API hydrate；修正涉密仍注入摘要
4. 业务入口：页头「打开对话」默认落到 Copilot（有 WP 推荐时仍可由 AI Tab 进专业体）
5. Chat 落地：`biz=1` + 有 `agent` 时若无 `conv`，引导/一键「新建对话」（自动建会话可选，需防重复）
6. Banner 清除与 URL 同步

### Phase 2 — 体验增强

- 业务顶栏「AI 助手」捷径（无对象 → Copilot；有最近项目 chip）
- `wpId` 参与 hydrate；Composer 展示「当前工作包」
- `prompt` 可选自动发送首条（需产品确认）
- Copilot 快捷 chip：最近项目 / 去选专业智能体

### Phase 3 — 结构化与工具（非必须）

- Chat API body 增加可选 `biz_context: { project_id, work_package_id }`（服务端拼 system/context，替代纯字符串 prepend）
- 只读工具：搜项目/客户、拉 ai-context
- 明确禁止写工具直至有确认+审计

---

## Task 1：Seed Biz Copilot Agent

**Files:**
- Modify: `backend/scripts/seed/biz_ai.py`（或并列 seed 脚本）
- Test: 手工/现有 seed 跑通后 `list agents` 可见；tag `biz-copilot` 可被 `_resolve_agent_by_tag` 解析

- [ ] **Step 1:** 增加 TenantTag `biz-copilot`（label：业务协作助手）
- [ ] **Step 2:** 创建 ENABLED Agent，系统提示包含：角色=路由/澄清；不写业务数据；有项目上下文时先确认任务再建议切换服务线智能体；涉密勿用外部知识库
- [ ] **Step 3:** EntityTagBinding 绑定 Agent ↔ tag
- [ ] **Step 4:** 本地跑 seed，确认 `_resolve_agent_by_tag("biz-copilot")` 返回该 Agent
- [ ] **Step 5:** Commit  
  `chore(biz): 种子数据增加业务协作助手智能体`

**系统提示要点（写入 Agent，非前端文案）：**

```text
你是业务中心的协作助手（Biz Copilot），不是业务系统操作员。
- 帮助用户澄清项目/工作包，并基于已注入的项目上下文协作（提纲、纪要、问答）。
- 具体服务线创作（设计说明、活动脚本等）应建议用户切换到对应专业智能体。
- 禁止声称已修改预算、合同、结项或审批状态；需要操作时给出业务中心页面路径说明。
- 若上下文标明涉密/禁止外部知识库，不得引用未授权资料或外部案例。
```

---

## Task 2：ai-context 返回 Copilot Agent

**Files:**
- Modify: `backend/app/biz/schemas/project_ai.py`
- Modify: `backend/app/biz/services/project_ai.py`
- Modify: `ui/workbench/lib/types/biz.ts`
- Test: `backend/tests/biz/test_project_ai_context.py`

- [ ] **Step 1:** Schema 增加 `copilot_agent_id: Optional[UUID]`、`copilot_agent_name: Optional[str]`
- [ ] **Step 2:** `get_ai_context` 内调用 `_resolve_agent_by_tag("biz-copilot")` 填入
- [ ] **Step 3:** 前端 `BizProjectAiContext` 同步字段
- [ ] **Step 4:** 单测：有绑定则非空；无绑定则为 null（不 500）
- [ ] **Step 5:** Commit  
  `feat(biz): 项目 AI 上下文返回协作助手智能体`

---

## Task 3：上下文韧性 + 涉密 prepend 修正

**Files:**
- Modify: `ui/workbench/features/projects/lib/business-context.ts`
- Modify: `ui/workbench/features/agents/hooks/use-agents-chat-page.tsx`（或等价 hydrate hook）
- Test: `ui/workbench/features/agents/__tests__/` 或 projects 下单测

- [ ] **Step 1:** 改 `prependBusinessContext`：有 ctx 则始终注入摘要；`ragEnabled` 不再作为注入开关（可在 header 加一行说明是否允许 RAG）
- [ ] **Step 2:** chat 页：`route.projectId` 且 `loadBusinessContext()` 为空时，调用 `api.getProjectAiContext(projectId, wpId)` → `saveBusinessContext(projectAiContextToStored(...))`
- [ ] **Step 3:** hydrate 期间 Banner 显示「加载项目上下文…」或静默
- [ ] **Step 4:** 单测：ragEnabled false 仍 prepend；storage miss + mock API 后有 context
- [ ] **Step 5:** Commit  
  `fix(agents): 业务上下文支持 URL 回补且涉密仍注入摘要`

---

## Task 4：统一业务 → Chat 入口行为

**Files:**
- Modify: `ui/workbench/features/projects/components/ProjectOpenChatButton.tsx`
- Modify: `ui/workbench/features/projects/lib/business-context.ts`（可选 `buildBizCopilotChatHref`）
- Modify: `ui/workbench/features/projects/components/ProjectAiTab.tsx`（文案已区分全局/WP，保持专业体 deep link）

- [ ] **Step 1:** 页头按钮：优先 `copilot_agent_id`，否则无 agent（保持现状空态选 Agent）
- [ ] **Step 2:** AI Tab「针对此工作包提问」继续带 `recommended_agent_id`（专业体），不改为 Copilot
- [ ] **Step 3:** 手动点开验证：页头 → Copilot；WP → 专业体
- [ ] **Step 4:** Commit  
  `feat(projects): 打开对话默认进入业务协作助手`

---

## Task 5：Chat 业务落地体验

**Files:**
- Modify: `ui/workbench/features/agents/hooks/use-agents-chat-page.tsx` 或 session hook
- Modify: `ui/workbench/features/agents/components/BusinessContextBanner.tsx`
- Modify: `ui/workbench/features/agents/lib/agents-chat-href.ts`（清 biz query 辅助函数）

- [ ] **Step 1:** `biz=1` 且有 `agent`、无 `conv`：空态文案强化「新建对话以带上项目上下文」；可选自动 `handleNewSession`（若采用自动，须只触发一次，用 ref 防 StrictMode 双建）
- [ ] **Step 2:** Banner「清除上下文」：清 storage + 本地 state + `replaceAgentsChat` 去掉 `biz`/`projectId`/`wpId`
- [ ] **Step 3:** 验证刷新带 `projectId` 仍能回补上下文
- [ ] **Step 4:** Commit  
  `fix(agents): 完善业务 deep link 落地与上下文清除`

---

## Task 6（可选 Phase 2）：业务顶栏捷径

**Files:**
- Modify: `ui/workbench/components/layout/BizTopBar.tsx`
- 依赖 Task 2 的 `copilot_agent_id` 或单独 `GET` 解析 tag 的轻量 API

- [ ] **Step 1:** 顶栏增加「AI 助手」链接 → `/workbench/agents/chat/?agent={copilot}&biz=1`（无 project 时可不带 projectId）
- [ ] **Step 2:** 无 Copilot 绑定时隐藏或退化为 `/workbench/agents/chat/`
- [ ] **Step 3:** Commit  
  `feat(business): 顶栏增加 AI 助手捷径`

---

## 接口约定（MVP）

### 已有

```http
GET /api/v1/biz/projects/{project_id}/ai-context?work_package_id=
POST /api/v1/agents/{agent_id}/chat
```

### 扩展响应字段

```json
{
  "copilot_agent_id": "uuid|null",
  "copilot_agent_name": "业务协作助手",
  "context_text": "...",
  "rag_enabled": true,
  "recommendations": [ ]
}
```

### Deep link

```text
/workbench/agents/chat/?agent={copilot|specialist}&projectId={id}&wpId={id}&biz=1&prompt={optional}
```

Chat body **MVP 不改**；上下文仍在 `query` 前缀中。Phase 3 再议 `biz_context` 字段。

---

## 测试计划

- [ ] Seed 后 tag `biz-copilot` 可解析
- [ ] 涉密项目：摘要仍进入 API query；Banner 提示涉密；related_cases 为空
- [ ] 新标签打开仅含 `projectId&biz=1` 的 URL → hydrate 成功
- [ ] 页头 → Copilot；AI Tab 工作包 → 推荐专业体
- [ ] 清除 Banner 后 URL 无 biz/projectId，且后续消息不再 prepend
- [ ] 无 Copilot 绑定的租户：页头不 500，可降级无 agent

---

## 风险与决策

| 风险 | 缓解 |
|------|------|
| 自动新建会话导致双会话 | 默认不自动建；或 ref 单次触发 |
| 多 Agent 同 tag 取第一个 | 文档约定每租户一个 `biz-copilot` |
| 字符串 prepend 污染历史展示 | 保持现状：UI 显示用户原文，仅 API query 带前缀 |
| 用户把 Copilot 当总控 | 系统提示 + 产品文案明确边界 |

---

## 建议实施顺序

Task 1 → 2 → 3 → 4 → 5 →（可选）6。  
每 Task 独立可测、可提交；全部完成后 Biz Copilot MVP 可用。
