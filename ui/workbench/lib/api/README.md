# API 客户端模块

`import { api } from "@/lib/api"` 不变；实现按业务域拆分在本目录。

| 模块             | 职责                                          |
| ---------------- | --------------------------------------------- |
| `client.ts`      | axios 实例、`get` / `post` / `getPage` 等原语 |
| `query.ts`       | `appendTagIds` 等查询串辅助                   |
| `auth.ts`        | 登录、用户、角色                              |
| `system.ts`      | 系统配置、对象存储、基础设施                  |
| `monitor.ts`     | 监控与告警                                    |
| `audit.ts`       | 审计日志                                      |
| `compliance.ts`  | 合规词库                                      |
| `tags.ts`        | 分类、标签                                    |
| `prompts.ts`     | 提示词模板                                    |
| `models.ts`      | 模型配置                                      |
| `flows.ts`       | 流程编排                                      |
| `kb.ts`          | 知识库                                        |
| `agents.ts`      | 智能体、A2A、对话                             |
| `attachments.ts` | 附件                                          |
| `generative.ts`  | 生成任务、媒体资产                            |
| `meta.ts`        | 各域 `GET */meta`                             |
| `hooks.ts`       | 钩子                                          |
| `tools.ts`       | 工具                                          |
| `skills.ts`      | 技能包                                        |
| `mcp.ts`         | MCP 服务                                      |
| `workbench.ts`   | 工作台概览                                    |
| `tasks.ts`       | 异步任务                                      |
| `marketplace.ts` | 应用市场                                      |
| `index.ts`       | 合并为 `api` 对象                             |

新增接口请写入对应域文件，并在 `index.ts` 中确保已 spread 该模块。
