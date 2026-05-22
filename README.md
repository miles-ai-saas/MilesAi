# AiEngine

企业级私有化 **AI 编排与 RAG 应用平台**（多模态）：多租户工作台、知识库、可视化流程、智能体（平台内协同 + A2A 互联）、合规与工具、应用市场。

| 端 | 技术 | 默认端口 |
|----|------|----------|
| 租户 AI 工作台 | Next.js 14 | 3000 |
| 平台运营后台 | Next.js 14 | 3001 |
| API / Worker | FastAPI + Celery | 8000 / Flower 5555 |
| 存储 | PostgreSQL · Redis · MinIO · Weaviate | 见 [docker/README.md](docker/README.md) |

**文档**：设计与专题说明见 **[docs/README.md](docs/README.md)**（需求、技术方案、流程、智能体、数据库等）。

---

## 快速启动（Docker）

Compose 拆分为 **中间件** 与 **应用**，详见 [docker/README.md](docker/README.md)。

```bash
cp .env.example .env
cd docker

# 一键全栈
docker compose -f docker-compose.middleware.yml -f docker-compose.yml up -d --build

# 或分步：先中间件，再应用
docker compose -f docker-compose.middleware.yml up -d
docker compose up -d --build
```

| 服务 | 地址 |
|------|------|
| API | http://localhost:8000 |
| OpenAPI | http://localhost:8000/docs |
| 租户工作台 | http://localhost:3000 |
| 运营后台 | http://localhost:3001 |
| Flower | http://localhost:5555 |

**默认账号**（首次启动种子）：

| 端 | 账号 | 密码 |
|----|------|------|
| 租户工作台 | `admin` | `admin123` |
| 运营后台 | `platform` | `admin123` |

---

## 本地开发

### 仅后端

```bash
cd docker && docker compose -f docker-compose.middleware.yml up -d   # 或本机 PG/Redis

cp backend/.env.example backend/.env   # POSTGRES_HOST=localhost
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

建库与迁移细节：[docs/database-setup.md](docs/database-setup.md)。

### 前端工作台

```bash
cd frontend && cp .env.local.example .env.local && npm install && npm run dev
# http://localhost:3000

cd admin_frontend && cp .env.local.example .env.local && npm install && npm run dev
# http://localhost:3001
```

### 登录示例

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

---

## 项目结构

```
AiEngine/
├── backend/                 # FastAPI
│   ├── app/
│   │   ├── api/v1/          # 薄路由
│   │   ├── app_tenant/      # 租户业务（agents、kb、flows、marketplace…）
│   │   ├── app_tenant/a2a/  # A2A Peer / 宿主调用
│   │   ├── ai_stack/        # LangChain、LangGraph、DeepAgents
│   │   ├── flow_runtime/    # 流程节点 + LangGraph 编译执行
│   │   └── models/
│   └── alembic/
├── frontend/                # 租户工作台
├── admin_frontend/          # 运营后台
├── docker/
└── docs/                    # → docs/README.md
```

**分层**：`api/` 路由 → `services/` 业务 → `repositories/` 数据访问 → `core/` 基础设施（详见 [docs/technical-design.md](docs/technical-design.md) §4）。

---

## 工作台导航（租户端）

| 模块 | 路径 | 说明 |
|------|------|------|
| 概览 | `/workbench/dashboard` | 入口与快捷链接 |
| 智能体 | `/workbench/agents` | 平台内智能体（`custom`） |
| 对话工作台 | `/workbench/agents/chat` | 单智能体调试与会话 |
| A2A 互联 | `/workbench/agents` → A2A Tab | 外部登记、互联宿主 |
| 知识库 | `/workbench/kb` | 多模态文档入库与检索 |
| 流程编排 | `/workbench/flows` | React Flow 画布 |
| 工具 / MCP / 技能包 | `/workbench/tools` 等 | P3 能力扩展 |
| 合规 / 钩子 | `/workbench/compliance` 等 | 敏感词与 Webhook |
| 应用市场 | `/workbench/marketplace` | 打包、审核、安装 |

智能体产品语义（内部协同 vs A2A）：[docs/a2a.md](docs/a2a.md)。

---

## 实施阶段

| 阶段 | 状态 | 交付概要 |
|------|------|----------|
| P0 基础设施 | ✅ | Compose、JWT+RBAC、租户、Celery |
| P1 RAG 核心 | ✅ | 知识库、入库流水线、检索 |
| P2 编排与智能体 | ✅ | `flow_runtime`、画布、智能体对话 |
| P3 安全与工具 | ✅ | 敏感词、钩子、MCP、技能包、工具目录 |
| P4 应用市场 | ✅ | 审核上架、评分排序 |
| P5 运维增强 | ⬜ | 监控报表、任务中心深化 |
| P6 AI 栈增强 | ✅ | LangChain / LangGraph / DeepAgents 已接入，见 [docs/ai-stack.md](docs/ai-stack.md) |

---

## 常用文档

| 主题 | 文档 |
|------|------|
| 文档索引 | [docs/README.md](docs/README.md) |
| 架构总纲 | [docs/technical-design.md](docs/technical-design.md) |
| 数据库 | [docs/database-setup.md](docs/database-setup.md) |
| 流程编排 | [docs/flows.md](docs/flows.md) |
| 平台内智能体 | [docs/platform-agents.md](docs/platform-agents.md) |
| A2A 互联 | [docs/a2a.md](docs/a2a.md) |
| AI 栈 | [docs/ai-stack.md](docs/ai-stack.md) |
| 后端说明 | [backend/README.md](backend/README.md) |

REST 接口以运行中的 **OpenAPI**（`/docs`）为准。

---

## 可选能力

**多模态 Worker**（OCR / 转写）：

```bash
cd backend && pip install -e ".[multimodal]"
# macOS: brew install tesseract tesseract-lang
```

**智能体 AI 栈**（LangGraph / DeepAgents）：

```bash
cd backend && pip install -e ".[agent-stack]"
```

**E2E 脚本**：`scripts/p2-e2e.sh`（需 API 已启动）。
