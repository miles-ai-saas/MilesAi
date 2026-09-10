# 立项归档（superpowers）

**日期：** 2026-05-27  
**用途：** 保存立项阶段的 spec / plan / 实施 checklist，供追溯决策过程。  
**勿当作现网规格** — 能力以 [features/](../features/) 与同主题 [architecture/](../architecture/) / [guides/](../guides/) 为准。

---

## 阅读顺序

1. 查 [README.md §功能节点 ↔ 文档速查](../README.md#功能节点--文档速查) 或对应 `features/*.md`
2. 需了解「为何这样设计」时再读本目录过程稿
3. 架构原则与 As-Is 头见 `architecture/` 各设计稿

---

## 文档清单

| 文档 | 类型 | 立项状态 | 现网状态 | 现网对照 |
|------|------|----------|----------|----------|
| [specs/2026-05-25-tools-design.md](./specs/2026-05-25-tools-design.md) | 设计 spec | 已批准 | **部分落地**（v1 HTTP + schema） | [tools-runtime.md](../architecture/tools-runtime.md)、[guides/tools.md](../guides/tools.md)、[features/tools-mcp-skills.md](../features/tools-mcp-skills.md) |
| [plans/2026-05-25-tools-v1.md](./plans/2026-05-25-tools-v1.md) | 实施 plan | 已完成 | **已落地** | 同上 |
| [specs/2026-05-25-mcp-runner-sandbox-design.md](./specs/2026-05-25-mcp-runner-sandbox-design.md) | 设计 spec | 待评审 → 已实施 MVP | **部分落地**（mcp-runner 容器；STDIO sync/invoke） | [mcp-sandbox.md](../architecture/mcp-sandbox.md)、[features/tools-mcp-skills.md](../features/tools-mcp-skills.md) |
| [plans/2026-05-26-flow-orchestration-enhancement.md](./plans/2026-05-26-flow-orchestration-enhancement.md) | 实施 plan | Phase 0–4 完成 | **已落地** | [flow-orchestration-enhancement.md](../architecture/flow-orchestration-enhancement.md)、[features/flow-orchestration.md](../features/flow-orchestration.md) |
| [plans/2026-05-26-flow-subflow.md](./plans/2026-05-26-flow-subflow.md) | 实施 plan | 已完成（后补实施） | **已落地**（2026-05-27 `feat(flow): 支持SubFlow`） | [flow-subflow-design.md](../architecture/flow-subflow-design.md)、[features/flow-orchestration.md](../features/flow-orchestration.md) |
| [plans/2026-07-15-agent-api-access.md](./plans/2026-07-15-agent-api-access.md)、[agent-api-keys](./plans/2026-07-15-agent-api-keys.md) | 实施 plan | 已完成 | **已落地** | [features/agent-api-access.md](../features/agent-api-access.md) |
| [plans/2026-07-15-agent-generative-cards.md](./plans/2026-07-15-agent-generative-cards.md) | 实施 plan | 已完成 | **已落地** | [features/attachments-media-generative.md](../features/attachments-media-generative.md) |
| [plans/2026-07-28-tool-agent-chat-split.md](./plans/2026-07-28-tool-agent-chat-split.md)、[2026-07-29-agent-chat-true-streaming.md](./plans/2026-07-29-agent-chat-true-streaming.md) | 实施 plan | 已完成 | **已落地** | [features/agent-chat-websocket.md](../features/agent-chat-websocket.md) |
| [plans/2026-07-29-eng-debt-hygiene-openapi-otel.md](./plans/2026-07-29-eng-debt-hygiene-openapi-otel.md) | 实施 plan | 已完成 | **已落地** | `openapi/openapi.snapshot.json` + `app/infra/otel.py` |
| [plans/2026-08-05-flow-video-param-recipes.md](./plans/2026-08-05-flow-video-param-recipes.md)、[generate-video-no-confirm](./plans/2026-08-05-generate-video-no-confirm.md) | 实施 plan | 已完成 | **已落地** | [features/flow-orchestration.md](../features/flow-orchestration.md) |
| [plans/2026-09-08 ~ 2026-09-10 `engine-di-*`（16 份）](./plans/) | 实施 plan | 已完成 | **已落地** | [engine-di-convergence.md](../architecture/engine-di-convergence.md)、[layering.md](../architecture/layering.md) §8 |

---

## 与 architecture/ 的关系

| superpowers | architecture 归档 | features As-Is |
|-------------|-------------------|----------------|
| tools-design + tools-v1 | tools-runtime.md | tools-mcp-skills.md |
| mcp-runner-sandbox | mcp-sandbox.md | tools-mcp-skills.md |
| flow-orchestration-enhancement plan | flow-orchestration-enhancement.md | flow-orchestration.md |
| flow-subflow plan | flow-subflow-design.md | flow-orchestration.md |

---

## 维护约定

- **不再更新**本目录正文；新能力直接写 `features/`，大改写 `architecture/`
- 新立项若产生 spec/plan，放入 `specs/` 或 `plans/`，并在本 README 增一行对照
- 实施完成后在 H1 下补 `> **归档：** …` 状态头（现网规格/实现入口写进该行），并把本表「现网状态」改为已落地 / 部分 / 未实施
- plan 正文里的 `- [ ]` 勾选框**保留为历史 checklist**，不作为待办信号；状态以顶部归档行为准
