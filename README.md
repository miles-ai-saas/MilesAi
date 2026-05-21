# AiEngine

一体化 AI 智能编排与 RAG 应用平台（多模态企业版）

## 快速启动（Docker）

Compose 已拆分为 **中间件** 与 **应用** 两份配置，详见 [docker/README.md](docker/README.md)。

```bash
cp .env.example .env
cd docker

# 方式一：一键全栈
docker compose -f docker-compose.middleware.yml -f docker-compose.yml up -d --build

# 方式二：分步启动
docker compose -f docker-compose.middleware.yml up -d   # Postgres / Redis / MinIO / Weaviate
docker compose up -d --build                            # API / Worker / Web / Flower
```

仅本地跑后端时：只起中间件 + `cp backend/.env.example backend/.env`（`POSTGRES_HOST=localhost`）。

服务地址：

| 服务 | 地址 |
|------|------|
| API | http://localhost:8000 |
| API 文档 | http://localhost:8000/docs |
| 租户 AI 工作台 | http://localhost:3000 |
| 平台运营后台 | http://localhost:3001 |
| Flower | http://localhost:5555 |
| MinIO Console | http://localhost:9001 |
| Weaviate | http://localhost:8080 |

默认账号（首次启动自动种子）：

- 租户工作台：`admin` / `admin123`
- 平台运营后台：`platform` / `admin123`（`/api/admin/v1`）

## 数据库创建

PostgreSQL 负责业务表；**建库 + 迁表**说明见 **[docs/数据库初始化.md](docs/数据库初始化.md)**。流程编排命名与实现见 **[docs/flow-runtime.md](docs/flow-runtime.md)**。

| 场景 | 建库 | 建表 |
|------|------|------|
| Docker 中间件 | `docker compose -f docker-compose.middleware.yml up -d` 自动建库 | 启动 API 时自动迁移，或 `cd backend && alembic upgrade head` |
| 本机 PostgreSQL | 手动 `CREATE DATABASE aiengine` | `cd backend && alembic upgrade head` |

## 本地开发（仅后端）

需本地运行 PostgreSQL 与 Redis，或仅启动中间件：`cd docker && docker compose -f docker-compose.middleware.yml up -d`。

```bash
cp backend/.env.example backend/.env
# 编辑 backend/.env：POSTGRES_HOST=localhost REDIS_HOST=localhost

cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head    # 初始化表结构
uvicorn app.main:app --reload --port 8000
```

## 登录示例

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

## 项目结构

```
AiEngine/
├── backend/
│   ├── app/
│   │   ├── api/v1/       # 薄路由，仅参数解析与调用 Service
│   │   ├── core/         # 公共核心（异常、响应、分页、仓储、认证、租户）
│   │   ├── repositories/ # 数据访问层
│   │   ├── app_tenant/   # 租户业务（flows、agents、kb…）
│   │   ├── flow_runtime/ # 流程 DAG 执行引擎（非 Langflow 产品）
│   │   └── models/       # 核心 ORM
│   └── alembic/
├── docker/
├── docs/
├── frontend/         # 租户 AI 工作台（:3000）
└── admin_frontend/   # 平台运营后台（:3001）
```

### 分层约定

| 层 | 职责 | 禁止 |
|----|------|------|
| `api/` | 路由、依赖注入、调用 Service | 不写 SQL、不写业务判断 |
| `services/` | 业务编排、权限与租户校验 | 不直接构造 HTTP 响应 |
| `repositories/` | CRUD、分页、唯一性检查 | 不含租户/权限规则 |
| `core/` | 跨模块公共函数与基础设施 | 不依赖具体业务模块 |

## 实施阶段

- [x] P0 基础设施：Compose、JWT+RBAC、租户/用户 API、健康检查、Celery 骨架
- [x] P1 RAG 核心：知识库 CRUD、文档上传、Celery 入库、向量检索
- [x] P2 编排与智能体：流程版本、`flow_runtime` 内置运行时、智能体对话
- [x] P2 多模态知识库：图片/音频上传、OCR/转写（可选依赖降级）
- [x] P2 应用市场：广场安装、租户打包上架（P4 起改为审核后上架）
- [x] P3 安全与工具：敏感词/拦截日志/检测试、钩子、工具目录与调用、MCP、技能包、流程/智能体合规
- [x] P4 应用市场：上架审核（待审/通过/驳回）、安装后评分、广场按评分排序
- [ ] P5 运维增强
- [ ] P6 智能体增强：LangChain / LangGraph / DeepAgents（见 [docs/agent-enhancement-langchain-stack.md](docs/agent-enhancement-langchain-stack.md)）

## 智能体与流程 API（P2）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/flows` | 创建流程 |
| PUT | `/api/v1/flows/{id}/graph` | 保存画布 JSON |
| POST | `/api/v1/flows/{id}/publish` | 发布 |
| POST | `/api/v1/flows/{id}/run` | 调试运行 |
| POST | `/api/v1/agents` | 创建智能体（绑定 `kb_ids`、可选 `published_flow_id`） |
| POST | `/api/v1/agents/{id}/chat` | 对话 |
| POST | `/api/v1/models` | 配置大模型（OpenAI 兼容） |

流程编排详见 **[docs/flow-runtime.md](docs/flow-runtime.md)**；LangChain 底座见 **[docs/langchain-integration.md](docs/langchain-integration.md)**。

- RAG 模板：`backend/app/flow_runtime/templates/rag_flow.json`
- 节点扩展：`app/flow_runtime/nodes/registry.py`

## 前端画布（P2）

编排画布使用 **React Flow**（`@xyflow/react`），`graph_json` 由后端 **LangGraph** 编译执行（`flow_runtime` 节点 registry）。

```bash
# 终端 1：中间件 + 应用
cd docker
docker compose -f docker-compose.middleware.yml up -d
docker compose up -d api worker

# 终端 2：租户工作台
cd frontend
cp .env.local.example .env.local
npm install
npm run dev
# http://localhost:3000 → admin/admin123

# 终端 3（可选）：运营后台
cd admin_frontend
cp .env.local.example .env.local
npm install
npm run dev
# http://localhost:3001 → platform/admin123

# 可选：命令行 E2E
chmod +x scripts/p2-e2e.sh && ./scripts/p2-e2e.sh
```

| 页面 | 路径 | 功能 |
|------|------|------|
| 登录 | `/login` | JWT |
| 流程列表/画布 | `/flows`, `/flows/{id}/edit` | 拖拽编排、保存、发布、调试 run |
| 智能体联调 | `/agents` | 创建智能体、对话测试 |
| 知识库 | `/kb` | 列表与新建；详情支持 TXT/PDF/图片/音频 |
| 应用市场 | `/workbench/marketplace` | 安装、打包上架、提交审核、评分、审核 Tab |

### 多模态入库（可选 Worker 依赖）

```bash
cd backend && pip install -e ".[multimodal]"   # pytesseract + openai-whisper
# 图片 OCR 还需系统安装 tesseract（macOS: brew install tesseract tesseract-lang）
```

未安装时仍可上传图片/音频，解析结果为可检索的占位说明文本。

### P3 合规 / MCP / 技能包

| 能力 | 路径 | 说明 |
|------|------|------|
| 敏感词 | `/compliance/words` | CRUD、启用/停用 |
| 检测试 | `POST /compliance/scan` | 试跑敏感词并写日志 |
| 拦截日志 | `/compliance/logs` | 智能体对话等命中记录 |
| MCP | `/mcp` | 注册、JSON-RPC `tools/list` 同步、删除 |
| 技能包 | `/skill-packages` | 工具名 + 提示词片段 |
| 智能体 | `config.skill_package_id` / `config.mcp_service_ids` | 对话时注入系统提示 |
| 工具目录 | `GET /tools/catalog` | 内置 + 自定义 HTTP + MCP 工具 |
| 工具调用 | `POST /tools/{name}/invoke` | calculator / http / knowledge_search 等 |
| 流程调试 | `POST /flows/{id}/run` | 同样走敏感词与 flow 钩子 |
| 钩子 | `/hooks` | HTTP Webhook，绑定 global/agent/flow |

工作台页面：`/workbench/compliance`、`/workbench/hooks`、`/workbench/tools`、`/workbench/mcp`、`/workbench/skills`

### 应用市场 API（P2 + P4）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/marketplace/apps/from-resources` | 从 KB/流程/智能体打包草稿 |
| POST | `/api/v1/marketplace/apps/{id}/publish` | 提交审核（`pending_review`） |
| GET | `/api/v1/marketplace/apps/pending` | 待审核列表（`marketplace:review`） |
| POST | `/api/v1/marketplace/apps/{id}/approve` | 通过并上架 |
| POST | `/api/v1/marketplace/apps/{id}/reject` | 驳回（body: `note`） |
| GET | `/api/v1/marketplace/apps?sort=installs\|rating` | 广场列表 |
| GET/POST | `/api/v1/marketplace/apps/{id}/ratings` | 评价列表 / 提交评分（需已安装） |
| DELETE | `/api/v1/marketplace/apps/{id}/ratings/mine` | 删除自己的评分 |
| GET | `/api/v1/marketplace/apps/mine` | 我的上架（含草稿/待审/驳回） |

已有库补充权限：`cd backend && python scripts/add_permissions.py`

详见 [docs/技术方案.md](docs/技术方案.md)。
