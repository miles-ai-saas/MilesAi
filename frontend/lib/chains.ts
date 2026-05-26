/**
 * 前端必要链路索引（新增能力时在此登记，并在链路入口文件注明章节号）。
 *
 * ## 1. 鉴权
 * `app/login` → `api.login` → `auth-store`（zustand persist）→ `getAccessToken`
 * → `api` 请求拦截器附加 Bearer → 401 时 logout 并跳转 `/login`
 * → 受保护页 `useRequireAuth().ready` 为 true 后再拉数据
 * → `AppShell`：有 token 无 user 时 `api.fetchMe`
 *
 * ## 2. HTTP / 业务 API
 * `lib/api.ts`：axios → `unwrap(ApiResponse)` → `get` / `post` / `getPage`
 * 错误：`api-error.getApiErrorMessage`（拦截器与页面 catch 共用）
 *
 * ## 3. 标准列表页（工作台 CRUD）
 * `useRequireAuth(ready)` → `usePagedList(api.listX)` → `pagination.normalizePageResult`
 * → `filterBySearch`（客户端关键字）→ `ResourceListLayout` + `ResourceListFooter`
 * → `useConfirmAction` 删除/危险操作确认
 * 可选：`useCategoryTabs`、`TagFilterSelect`、`use*Meta`（枚举见 §4）
 *
 * ## 4. 枚举展示
 * 见 `lib/enum-meta.ts`、`docs/guides/hooks.md` §9
 *
 * ## 5. 对话工作台
 * `app/workbench/agents/chat`：`useInfiniteList` 拉智能体列表
 * → `chat-sessions`（localStorage 多会话，与后端 `conversation_id` 对齐）
 * → `api.chatAgent` → `ChatResponse.steps` → `agent-steps` 解析 → `agent-trace` 按轮展示
 *
 * ## 6. 流程编排
 * `flow-nodes`（graph_json）↔ `FlowCanvas` ↔ 后端 `langgraph.compiler` / `NODE_REGISTRY`
 * 编辑页：`flows/[id]/edit` → `getFlowGraph` / `saveFlowGraph` / `testFlow`
 *
 * ## 7. 导航与壳层
 * `nav-config` → `AppShell`（工作台顶栏 + `WorkbenchHeaderNav`）
 * → `SystemShell`（系统管理侧栏 + 面包屑）
 *
 * ## 8. 知识库文档入库
 * `uploadDocument` → 文档 `status` 轮询 → `document-status` + `KbMeta.document_statuses`
 *
 * ## 9. 技能包 SKILL.md
 * `skill-md` 解析 frontmatter ↔ 后端 `parse_skill_md`；编辑页读写 `api.writeSkillFile`
 *
 * ## 10. 定时任务（智能体调度等）
 * `cron-celery` 五段 Cron ↔ 后端 Celery crontab
 *
 * ## 11. MCP 工作台
 * `mcp/page` → `api` CRUD / sync → `mcp-labels` + `useMcpMeta`；STDIO 经 Runner 沙箱
 *
 * ## 12. 应用市场
 * `marketplace/page`：广场/安装/上架/审核多视图 + `usePagedList` + `useMarketplaceMeta`
 *
 * ## 13. 合规词库
 * `compliance/page`：词库 CRUD、扫描绑定、拦截日志；`useComplianceMeta`；旧路径 `/sensitive-words` 跳转
 *
 * ## 14. 监控
 * `monitor/page`：`getMonitorStats` / trends / health + `useMonitorMeta`（可与 `useKbMeta` 联动展示）
 *
 * ## 15. 工作台概览
 * `dashboard/page`：`api.getWorkbenchOverview`；根路径 `/`、`/workbench` 重定向至此
 */

export {};
