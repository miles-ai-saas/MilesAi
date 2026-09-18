# 技能包技术方案

**功能规格：** [features/tools-mcp-skills.md](../features/tools-mcp-skills.md) §技能包

技能包（Skill Package）在 MilesAI 中用于管理 **Cursor 风格的 `SKILL.md` 技能目录**：元数据入库、文件落盘、分类筛选、ZIP 导入导出，并在智能体对话时通过 `config.skill_ids`（列表，兼容旧 `config.skill_package_id`）将技能说明注入系统提示（System Prompt）。

与 **MCP**（远程工具服务）互补：技能包侧重「提示词/流程说明」类知识；MCP 侧重可调用远程工具。二者可同时绑定在同一智能体上。

## 1. 能力范围

| 能力 | 状态 | 说明 |
|------|------|------|
| 列表与分类 Tab | ✅ | `sys_categories`，`domain=skill` |
| 创建空白技能包 | ✅ | 生成默认 `SKILL.md`，跳转编辑器 |
| 在线编辑 `SKILL.md` | ✅ | 文件树 + 读写 API |
| 本地目录导入 | ✅ | 服务端可访问路径扫描 |
| ZIP 导入 | ✅ | 须含 `skills/` 目录，≤100MB |
| Git 克隆导入 | ✅ | `git clone --depth 1`，优先 `skills/` 子目录 |
| 智能体绑定注入 | ✅ | 多技能：`config.skill_ids` 列表（兼容旧 `skill_package_id`），逐包注入 Prompt |
| references / scripts 索引 | ✅ | `config.layout` 索引注入 Prompt；按需 `skill_read_reference` |
| 技能脚本沙箱执行 | ✅ | `skill_run_script`（需 `MCP_RUNNER_ENABLED`） |
| 导出 ZIP | ✅ | `GET /skill-packages/{id}/export`，归档顶层 `skills/{slug}/`，可再导入 |
| 兼容旧版「工具勾选 + 片段」 | ✅ | `POST /skill-packages` 仍保留 |

## 2. SKILL.md 规范

每个技能对应**一个目录**，根目录下必须包含 **`SKILL.md`**（文件名全大写）。

### 2.1 Frontmatter

文件开头为 YAML frontmatter（`---` 分隔），至少包含：

| 键 | 必填 | 说明 |
|----|------|------|
| `name` | 是 | 展示名称；导入/保存时同步到 DB `name` |
| `description` | 否 | 简短描述；同步到 DB `description` |

示例：

```markdown
---
name: doGetCurrentTime
description: 通过技能你可以获取当前时间
---

## 使用说明

在需要当前时间时，按以下步骤……
```

### 2.2 解析实现

- 模块：`backend/packages/miles-portal/src/miles_portal/tenant/skills/skill_md.py`
- `parse_skill_md`：提取 frontmatter 与正文（行级 `key: value`，无 PyYAML 依赖）
- `build_skill_md`：创建空白包时生成模板
- 保存 `SKILL.md` 时：`SkillService.write_file_content` 调用 `sync_meta_from_skill_md` 回写 DB

### 2.3 目录布局（Progressive Disclosure）

对齐 Agent Skills 约定，推荐目录：

```
{slug}/
  SKILL.md           # 精简正文，默认全文注入 Prompt
  references/        # 长文档、API 手册等（仅索引注入，按需读取）
  scripts/           # 可执行 Python 脚本（仅索引注入，按需沙箱执行）
  assets/            # 可选静态资源（图片等，索引展示）
```

| 目录 | Prompt 策略 | 运行时 |
|------|-------------|--------|
| `SKILL.md` | 全文注入 | — |
| `references/` | 路径 + 首行摘要索引 | 内置工具 `skill_read_reference` |
| `scripts/` | 路径索引 | 内置工具 `skill_run_script`（`run(params)`） |
| `assets/` | 路径索引 | `skill_read_reference`（文本类） |

- 索引构建：`backend/packages/miles-portal/src/miles_portal/tenant/skills/skill_layout.py` → 写入 `SkillPackage.config.layout`
- 刷新时机：保存文件、空白创建、导入后自动 reindex
- 空白创建：`POST /skill-packages/blank` 会生成 `references/guide.md` 与 `scripts/example_validate.py` 示例

### 2.4 附属文件

目录内可放置任意文本文件。编辑器通过文件 API 读写；路径禁止 `..` 穿越（`storage.write_file` / `read_file` 做 resolve 校验）。

## 3. 数据模型

### 3.1 表 `skl_skill_packages`

模型：`backend/packages/miles-portal/src/miles_portal/tenant/skills/models.py`  
迁移：表结构由 ORM 定义，唯一 Alembic 文件 `alembic/versions/001_initial_schema.py`（`create_all`）。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID | 主键 |
| `tenant_id` | UUID | 租户隔离 |
| `category_id` | UUID? | 逻辑外键 → `sys_categories`（`domain=skill`） |
| `slug` | string(128) | **租户内唯一**；对应磁盘子目录名 |
| `name` | string(128) | 展示名（通常来自 frontmatter） |
| `description` | text? | 描述 |
| `source_type` | string(32) | `manual` \| `local` \| `zip` \| `git` |
| `storage_path` | string(512)? | 存储相对标识，默认等于 `slug` |
| `tool_names` | JSONB | 遗留字段：工具名列表（可选） |
| `prompt_snippet` | text? | 遗留字段；无 `SKILL.md` 时注入回退 |
| `config` | JSONB | 扩展配置；`config.layout` 存 references/scripts 索引 |
| `is_active` | bool | 停用后不注入智能体 |
| `created_at` / `updated_at` / `deleted_at` | timestamptz | 软删 |

约束：

- `uk_skl_skill_packages_tenant_slug`：`(tenant_id, slug)` 唯一
- `idx_skl_skill_packages_tenant_name`：`(tenant_id, name)` 普通索引（非唯一）

### 3.2 分类 `sys_categories`

| 项 | 值 |
|----|-----|
| `CategoryDomain.SKILL` | `"skill"` |
| 权限 | `skill:read` / `skill:write`（分类 API 与技能包 API 共用分类域权限映射） |
| 默认种子 | 未分类、通用、本地导入、Git导入（`scripts/seed/categories.py`） |

分类 API：`GET/POST/PATCH/DELETE /api/v1/categories?domain=skill`  
详见统一分类设计（智能体/提示词同表不同 `domain`）。

## 4. 文件存储

### 4.1 目录布局

```
{skills_data_root}/
  {tenant_id}/
    {slug}/
      SKILL.md
      references/
      scripts/
      assets/   # 可选
```

| 配置项 | 环境变量 | 默认值 |
|--------|----------|--------|
| 根目录 | `SKILLS_DATA_ROOT` | `.data/skills`（相对 **backend** 目录） |

实现：

- `backend/packages/miles-portal/src/miles_portal/tenant/skills/storage.py` — 磁盘读写、扫描、导入路径
- `backend/packages/miles-portal/src/miles_portal/tenant/skills/skill_layout.py` — 布局索引、资源读取、Prompt 块
- `backend/packages/miles-portal/src/miles_portal/tenant/skills/runtime.py` — `skill_read_reference` / `skill_run_script` 执行

- `skills_data_root()`：解析绝对/相对路径并 `mkdir`
- `skill_package_dir(tenant_id, slug)`：单技能根路径
- 删除技能包 / 清空租户：同步 `shutil.rmtree`（`purge_tenant_data` 调用 `remove_tenant_skills`）

### 4.2 Slug 规则

- 导入：目录名经 `skill_slug_from_folder` 规范化（保留 `[a-zA-Z0-9_-]`）
- 手动创建：由 `name` 经同样规则生成；冲突返回 `409`「技能标识已存在」

## 5. HTTP API

前缀：`/api/v1/skill-packages`（租户 JWT + `skill:read` / `skill:write`）  
路由：`backend/packages/miles-portal/src/miles_portal/tenant/skills/views/skills.py`

### 5.1 CRUD 与列表

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/skill-packages?page=&size=&category_id=` | 分页列表；`category_id` 可选筛选 |
| GET | `/skill-packages/{id}` | 详情（含 `category_name`） |
| POST | `/skill-packages` | 遗留创建（可带 `tool_names`、`prompt_snippet`） |
| POST | `/skill-packages/blank` | **推荐**：空白包 + 初始 `SKILL.md` |
| PATCH | `/skill-packages/{id}` | 更新元数据 / 启停 |
| DELETE | `/skill-packages/{id}` | 软删 + 删除磁盘目录 |

**`POST /blank` 请求体**

```json
{
  "name": "测试1",
  "description": "可选描述",
  "category_id": "uuid-of-category"
}
```

**`SkillPackageOut` 主要字段**：`id`, `slug`, `name`, `description`, `category_id`, `category_name`, `source_type`, `is_active`, `created_at`, `updated_at`

### 5.2 文件工作区

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/{id}/files` | 目录树 `SkillFileNode[]` |
| GET | `/{id}/file?path=SKILL.md` | 读文件内容 |
| PUT | `/{id}/file` | 写文件；body: `{ "path", "content" }` |
| DELETE | `/{id}/file?path=` | 删除文件（不可删 `SKILL.md`） |
| POST | `/{id}/reindex` | 扫描磁盘重建 `config.layout` 索引 |

保存 `SKILL.md` 时自动同步 DB 的 `name`、`description`，并将全文写入 `prompt_snippet` 字段（便于检索/回退）。

### 5.3 批量导入

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/import/local` | JSON 体见下 |
| POST | `/import/git` | JSON 体见下 |
| POST | `/import/zip?category_id=&overwrite_existing=` | `multipart/form-data`，字段 `file` |

**本地 / Git 请求体**

```json
{
  "category_id": "uuid",
  "local_path": ".data/skills",
  "overwrite_existing": false
}
```

```json
{
  "category_id": "uuid",
  "repo_url": "https://github.com/user/repo.git",
  "overwrite_existing": false
}
```

**`SkillImportResult`**

```json
{
  "imported": 2,
  "skipped": 1,
  "errors": ["bad_dir: 缺少 SKILL.md"]
}
```

| 字段 | 含义 |
|------|------|
| `overwrite_existing=true` | 同名 `slug` 已存在则**覆盖**磁盘与 DB 元数据 |
| `overwrite_existing=false` | 同名则**跳过**（`skipped++`） |

### 5.4 导入目录约定

#### 本地目录

1. 解析 `local_path`：绝对路径，或相对 **backend** 目录。
2. 对目标目录执行 `discover_skill_dirs`：
   - 若根目录有 `SKILL.md` → 视根为单个技能；
   - 否则扫描**一级子目录**，子目录内须有 `SKILL.md`。

#### ZIP

1. 仅 `.zip`，上传大小 ≤ **100MB**。
2. 归档规模在**解压前**校验（按中央目录声明值）：解压后总体积 ≤ **500MB**、
   条目数 ≤ **10000**。超限返回 `400` 且不落地任何文件 —— 上传上限只约束压缩后
   大小，文本类技能包压缩比可达数十倍。
3. 损坏或非 zip 归档返回 `400`（`BadZipFile` 已转为业务错误，不再 500）。
4. 解压后**必须**存在 `skills/` 目录。
5. 对 `skills/` 执行与本地相同的 `discover_skill_dirs`。

路径穿越（`../`、绝对路径）与符号链接成员由标准库 `zipfile` 自行净化，未额外加固。

目录结构示例：

```
your-skills.zip
└── skills/
    ├── cust_query/
    │   └── SKILL.md
    └── doGetCurrentTime/
        └── SKILL.md
```

#### 导出 ZIP

`GET /skill-packages/{id}/export`（权限 `skill:read`）返回归档，顶层为
`skills/{slug}/`，与 §5.4 ZIP 的「须含 `skills/`」前置约定对称 —— 故导出物可直接
用 `POST /skill-packages/import/zip` 再导入。打包时跳过 `__pycache__`、点开头文件
与 `.pyc/.pyo`（运行残留，带出去只会在再导入时污染技能内容）。

前端入口：技能编辑器左栏「导出为 ZIP」。

#### Git

1. `git clone --depth 1 <repo_url>`（需运行环境安装 `git`）。
2. 若仓库存在 `skills/` 目录 → 从该目录扫描；否则从**仓库根**扫描。
3. 超时 300s；失败返回 `400` 及 stderr 摘要。
4. 地址**仅允许 `http(s)`**：经 `validate_outbound_url` 校验，`file://` / `ssh://` /
   `git://` 与 scp 风格（`git@host:org/repo.git`）一律拒绝 —— `git clone` 会识别这些
   scheme，放行即构成本地文件读取面。内网 / link-local 地址的拦截由
   `OUTBOUND_ALLOW_PRIVATE_HOSTS` 控制，该项默认 `true`（即默认放行内网）；公开部署应置
   `false` 以收紧（与 `guides/mcp.md` 同一开关，见 `architecture/mcp-sandbox.md`）。

## 6. 运行时：智能体注入

```
Agent.config.skill_ids[]            # 旧版单值 config.skill_package_id 仍兼容
  → build_skill_mcp_prompt_block (agents/services/context.py)
  → 逐个读取 SkillPackage（租户、未软删、is_active；失效项跳过）
  → read_skill_md(tenant_id, slug) 优先
  → 否则 prompt_snippet
  → 追加 config.layout 索引块（references / scripts）
  → 可选追加 tool_names 行
  → 与 MCP 块拼接进 system prompt
```

绑定技能包且 `enable_tool_calling` 时，tool_agent 额外挂载：

| 工具 | 说明 |
|------|------|
| `skill_read_reference` | 读取 `references/`、`assets/` 文本 |
| `skill_run_script` | 沙箱执行 `scripts/*.py`（需确认 + MCP Runner） |

技能包从智能体绑定集合解析，LLM 通常无需传技能 ID：绑定唯一时直接选用；绑定多个时须传
`skill_slug` 消歧（参数在工具 schema 上；不传会报错并列出可选 slug，不会静默取第一个）。

绑定入口：工作台智能体表单「技能包（可多选）」（`ui/workbench/features/agents/components/AgentFormSteps/AgentFormStepCapabilitiesSection.tsx`），写入 `config.skill_ids`。

注入块示例：

```text
【技能包 · doGetCurrentTime】
技能包 slug: doGetCurrentTime
---
name: doGetCurrentTime
description: ...
---
（正文）
```

## 7. 前端

| 路由 | 说明 |
|------|------|
| `/workbench/skills` | 分类 Tab、添加卡片、技能卡片、导入弹窗 |
| `/workbench/skills/[id]` | 分组文件树、layout 索引摘要、新建 references/scripts、刷新索引 |

主要文件：

| 路径 | 职责 |
|------|------|
| `ui/workbench/app/workbench/skills/page.tsx` | 列表与导入入口 |
| `ui/workbench/app/workbench/skills/[id]/page.tsx` | 编辑器 |
| `ui/workbench/features/skills/components/SkillImportDialogs.tsx` | 本地 / ZIP / Git 弹窗 |
| `ui/workbench/features/skills/hooks/use-skill-editor-page.ts` | 编辑器 VM（读写文件、导出 ZIP） |
| `ui/workbench/lib/api.ts` | `listSkillPackages`、`importSkill*`、`putSkillFile` 等 |
| `ui/workbench/components/category/useCategoryTabs.tsx` | `domain="skill"` |

## 8. 代码结构（后端）

```
backend/packages/miles-portal/src/miles_portal/tenant/skills/
├── models.py              # ORM
├── skill_md.py            # SKILL.md 解析/生成
├── skill_layout.py        # references/scripts 索引与 Prompt 块
├── runtime.py             # skill_read_reference / skill_run_script
├── storage.py             # 磁盘读写、扫描、导入路径
├── schemas/skill.py       # Pydantic
├── services/
│   ├── skill.py           # CRUD、文件、空白创建
│   └── import_service.py  # local / zip / git
└── views/skills.py        # HTTP 路由
```

关联：

| 模块 | 路径 |
|------|------|
| 分类域扩展 | `backend/packages/miles-core/src/miles_core/models/meta/category.py`（`CategoryDomain.SKILL`） |
| 分类清空引用 | `tenant/categories/services/category.py` |
| 租户硬删 | `app/deletion/tenant.py` |
| 种子 | `scripts/seed/categories.py` |

## 9. 运维与初始化

```bash
cd backend
milesai migrate          # alembic upgrade head（001）
milesai seed categories  # 写入 skill 域默认分类
milesai seed skills      # 示例技能包（SKILL.md + references/ + scripts/，可重复执行补全缺失文件）
```

生产建议：

- 将 `SKILLS_DATA_ROOT` 挂载为持久卷（与 API 容器同机或共享存储）。
- Git 导入需镜像内安装 `git`；出站网络需能访问目标仓库。
- 本地导入路径必须在 API 进程可读范围内（容器部署时注意 volume 映射）。

单元测试：

- `backend/tests/test_skill_md.py` — frontmatter 解析
- `backend/tests/test_skill_layout.py` — 布局索引与资源读取
- `backend/tests/test_skill_runtime_integration.py` — Prompt 索引块与 skill 工具挂载

## 10. 与 MCP / 工具目录的关系

| 机制 | 用途 | 智能体配置键 |
|------|------|----------------|
| 技能包 | `SKILL.md` 说明注入（可多包） | `skill_ids`（旧 `skill_package_id`） |
| MCP 服务 | 远程 `tools/list` / `tools/call` | `mcp_service_ids` |
| 内置/自定义工具 | 平台工具目录与 invoke | `tool_names` 等（技能包 `tool_names` 为遗留展示） |

详见 [mcp.md](./mcp.md)、[platform-agents.md](./platform-agents.md)。

## 11. 已知限制与后续

| 项 | 说明 |
|----|------|
| Git SSH | **已不支持**：地址仅允许 `http(s)`（见 §5「Git」）。私有仓库请用带 token 的 https 地址 |
| Git Deploy Key | 未内置，故无法以 ssh 方式拉取私有仓库 |
| ZIP 解压体积 | 上传上限 100MB；解压后总体积上限 500MB、条目数上限 10000，均在解压前校验（§4 ZIP） |
| Git 域名解析 | `validate_outbound_url` 不解析域名，故「域名解析到内网」不在拦截内（与 HTTP 工具同限） |
| 本地路径安全 | 当前允许配置任意可读路径，生产可加白名单（仅允许 `skills_data_root` 下） |
| Streamable Skill 协议 | 已支持 references/scripts 子集；frontmatter 扩展字段待补 |

REST 字段以运行中 OpenAPI（`/docs`）为准。
