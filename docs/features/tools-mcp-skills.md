# 工具、MCP 与技能包

**状态：** 已实现  
**PRD 对照：** 模块5 工具与MCP协议生态  
**架构：** [tools-runtime.md](../architecture/tools-runtime.md) · [mcp-sandbox.md](../architecture/mcp-sandbox.md)

---

## 1. 背景与目标

平台提供 **内置工具**、租户 **自定义 HTTP/脚本工具**、**MCP 服务** 同步与 invoke，以及 **技能包**（SKILL.md + 工具/提示词组合）供智能体挂载。

### 1.1 交付范围

- 工具目录：builtin + custom CRUD、`POST /tools/{name}/invoke`
- 内置：calculator、http_request、knowledge_search、compliance_check_text、run_flow_once、invoke_tenant_hook、web_search、code_execution、generate_* 等（见 registry）
  - 外呼/执行类标 `opt_in`，须在 `agent.config.tool_slugs` 勾选才进入 function schema
- MCP：CRUD、sync tools/list、HTTP/SSE/STDIO invoke（STDIO 经 mcp-runner）
- 技能包：导入（本地/ZIP/Git）、SKILL.md 编辑、分类
- 钩子：`before_tool` / `after_tool`
- 调用日志 `tool_invocation_logs`

### 1.2 明确不做

- 统一 tools-runtime 目标架构全部落地（见 design 文档，部分仍为演进方向）
- MCP 全协议自定义扩展插件化

---

## 2. 数据模型

| 表 | 说明 |
|----|------|
| `tool_tools` | 自定义工具配置（HTTP、脚本等） |
| `tool_invocation_logs` | 调用审计 |
| `tool_mcp_services` | MCP 服务注册、tools_cache |
| `mcp_runner_sessions` | STDIO Runner 会话 |
| `skl_skill_packages` | 技能包元数据 + 磁盘路径 |

内置工具无 DB 行，来自 `BUILTIN_REGISTRY`。

---

## 3. API

### 3.1 工具 `/api/v1/tools`

权限：`tools:read` · `tools:write`

```
GET  /tools/meta
GET  /tools/catalog?source=builtin|custom&category_id=&tag_ids=
GET  /tools
POST /tools
GET/PATCH/DELETE /tools/{id}
POST /tools/{tool_name}/invoke
GET  /tools/builtin
GET  /tools/invocation-logs
```

### 3.2 MCP `/api/v1/mcp`

权限：`mcp:read` · `mcp:write`

```
GET  /mcp/meta
GET  /mcp
POST /mcp
PATCH/DELETE /mcp/{id}
POST /mcp/{id}/sync
POST /mcp/{id}/tools/{name}/invoke
```

STDIO：`MCP_RUNNER_ENABLED` + `mcp-runner` 容器。

### 3.3 技能包 `/api/v1/skill-packages`

权限：`skill:read` · `skill:write`

```
GET  /skill-packages/meta
GET  /skill-packages?category_id=&tag_ids=
POST /skill-packages              # 创建
POST /skill-packages/import/...   # 本地/ZIP/Git
GET/PATCH/DELETE /skill-packages/{id}
GET/PUT …/content                 # SKILL.md
```

---

## 4. 执行平面

```
invoke_tool_with_context
    → HookRunner before_tool
    → builtin | custom HTTP | script | MCP
    → HookRunner after_tool
    → tool_invocation_logs
```

变换脚本在 Runner 沙箱子进程执行，预注入 `json` / `re` / `math` / `datetime`（仍禁用户 `import`）。
智能体 `config.skill_ids`（列表，兼容旧 `config.skill_package_id`）、`config.mcp_service_ids` 注入可用工具集；
绑定知识库时 `knowledge_search` 强制可用（RAG 与 function calling 共存），命中回填 `sources`。

---

## 5. 前端

| 路径 | 功能 |
|------|------|
| `/workbench/tools` | 工具列表、试调用 |
| `/workbench/mcp` | MCP 服务管理 |
| `/workbench/skills` | 技能包列表 |
| `/workbench/skills/[id]` | SKILL.md 编辑器 |

---

## 6. 后端文件清单

```
backend/packages/miles-portal/src/miles_portal/tenant/tools/
    builtin_registry.py
    handlers/
    primitives.py
    invoke/
backend/packages/miles-portal/src/miles_portal/tenant/mcp/
backend/packages/miles-portal/src/miles_portal/tenant/skills/
docker/images/mcp-runner/
```

---

## 7. 测试计划

1. invoke calculator → 200 + log
2. MCP HTTP sync → tools_cache 更新 → invoke
3. 技能包导入 → agent 绑定 → chat 可见 skill 工具
4. 钩子 block tool → invoke 失败

---

## 8. 参考

- [tools.md](../guides/tools.md)
- [mcp.md](../guides/mcp.md)
- [skill-packages.md](../guides/skill-packages.md)
- [hooks.md](../guides/hooks.md)
