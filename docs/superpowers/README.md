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
| [plans/2026-05-26-flow-subflow.md](./plans/2026-05-26-flow-subflow.md) | 实施 plan | 未开工 | **未实施** | [flow-subflow-design.md](../architecture/flow-subflow-design.md)（目标规格） |

---

## 与 architecture/ 的关系

| superpowers | architecture 归档 | features As-Is |
|-------------|-------------------|----------------|
| tools-design + tools-v1 | tools-runtime.md | tools-mcp-skills.md |
| mcp-runner-sandbox | mcp-sandbox.md | tools-mcp-skills.md |
| flow-orchestration-enhancement plan | flow-orchestration-enhancement.md | flow-orchestration.md |
| flow-subflow plan | flow-subflow-design.md | —（暂无） |

---

## 维护约定

- **不再更新**本目录正文；新能力直接写 `features/`，大改写 `architecture/`
- 新立项若产生 spec/plan，放入 `specs/` 或 `plans/`，并在本 README 增一行对照
- 实施完成后在 architecture 设计稿加 **As-Is 规格** 链，并将本表「现网状态」改为已落地 / 部分 / 未实施
