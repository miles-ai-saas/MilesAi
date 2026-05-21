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
| Flower | http://localhost:5555 |
| MinIO Console | http://localhost:9001 |
| Weaviate | http://localhost:8080 |

默认管理员（首次启动自动种子）：`admin` / `admin123`

## 数据库创建

PostgreSQL 负责业务表；**建库 + 迁表**说明见 **[docs/数据库初始化.md](docs/数据库初始化.md)**。

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
│   │   ├── services/     # 业务逻辑层
│   │   └── models/       # ORM 模型
│   └── alembic/
├── docker/
├── docs/
└── frontend/         # Next.js（P1 后）
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
- [x] P2 编排与智能体：流程版本、内置/Langflow 运行时、智能体对话
- [ ] P3 安全与工具
- [ ] P4 应用市场
- [ ] P5 运维增强

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

RAG 流程模板：`backend/app/langflow/templates/rag_flow.json`

节点扩展：在 `app/langflow/nodes/registry.py` 注册新 handler 即可。

## 前端画布 + P2 联调

`@langflow/flow-builder` 暂未发布到 npm，前端使用 **React Flow**（`@xyflow/react`），`graph_json` 与后端 Builtin 运行时兼容。

```bash
# 终端 1：中间件 + 应用
cd docker
docker compose -f docker-compose.middleware.yml up -d
docker compose up -d api worker

# 终端 2：前端
cd frontend
cp .env.local.example .env.local
npm install
npm run dev
# 打开 http://localhost:3000 → 登录 admin/admin123 → 流程编排 → 新建 RAG 流程 → 保存/发布/调试

# 可选：命令行 E2E
chmod +x scripts/p2-e2e.sh && ./scripts/p2-e2e.sh
```

| 页面 | 路径 | 功能 |
|------|------|------|
| 登录 | `/login` | JWT |
| 流程列表/画布 | `/flows`, `/flows/{id}/edit` | 拖拽编排、保存、发布、调试 run |
| 智能体联调 | `/agents` | 创建智能体、对话测试 |
| 知识库 | `/kb` | 列表与新建 |

详见 [docs/技术方案.md](docs/技术方案.md)。
