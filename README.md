# MilesAi

企业级私有化 **AI 编排与 RAG 应用平台**（多模态）：多租户工作台、知识库、可视化流程、智能体（平台内协同 + A2A 互联）、合规与工具、应用市场。

| 端 | 技术 | 默认端口 |
|----|------|----------|
| 租户 AI 工作台 | Next.js 14 | 3000 |
| 平台运营后台 | Next.js 14 | 3001 |
| API / Worker / Beat | FastAPI + Celery | 8000 / Flower 5555 |
| 存储 | PostgreSQL · Redis · MinIO · Milvus（默认）· Weaviate（可选） | 见 [docker/README.md](docker/README.md) |

**文档**：设计与专题说明见 **[docs/README.md](docs/README.md)**（需求、技术方案、**前端设计规范**、流程、智能体、数据库等）。

---

## 快速启动（Docker）

Compose 拆分为 **中间件** 与 **应用**，详见 [docker/README.md](docker/README.md)。

```bash
cp .env.example .env
cd docker

# 一键全栈
docker compose -f docker-compose.infra.yml -f docker-compose.yml up -d --build

# 初始化数据库（迁移 + 种子）
cd ../backend && python cli.py init-db
```

应用栈含 `api`、`worker`、`beat`（智能体定时任务）、`mcp-runner`、`web`、`admin-web`、`flower`。也可分步：先 `docker compose -f docker-compose.infra.yml up -d`，再 `docker compose up -d --build`。

| 服务 | 地址 |
|------|------|
| API | http://localhost:8000 |
| OpenAPI | http://localhost:8000/docs |
| 租户工作台 | http://localhost:3000 |
| 运营后台 | http://localhost:3001 |
| Flower | http://localhost:5555 |

**默认账号**（需先执行数据库初始化脚本写入种子，见下方）：

| 端 | 账号 | 密码 |
|----|------|------|
| 租户工作台 | `admin` | `admin123` |
| 运营后台 | `platform` | `admin123` |

---

## Docker 镜像构建与推送

镜像默认推送到 `registry.cn-shenzhen.aliyuncs.com/kye_secure`。构建前修改 `docker-compose.yml` 中的 `image` 为你自己的仓库地址。

以下命令**均在项目根目录**执行（`-f` 指定 Dockerfile，上下文为 `.`）：

| 服务 | 镜像 | 构建命令 |
|------|------|----------|
| API | `milesai-api` | `docker buildx build --platform linux/amd64 --progress=plain -t <仓库>/milesai-api:latest -f Dockerfile.api . --push` |
| Worker / Beat | `milesai-worker` | `docker buildx build --platform linux/amd64 --progress=plain -t <仓库>/milesai-worker:latest -f Dockerfile.worker . --push` |
| MCP Runner | `milesai-mcp-runner` | `docker buildx build --platform linux/amd64 --progress=plain -t <仓库>/milesai-mcp-runner:latest -f Dockerfile.mcp-runner . --push` |

前端（web / admin-web）已通过 `npm run build` 产出静态文件部署到 OSS，无需构建 Docker 镜像。

**注意**：构建上下文 `.` 必须是项目根目录，Dockerfile 通过 `-f Dockerfile.<服务名>` 指定。`COPY` 路径相对于项目根目录，不需要关心 Dockerfile 的位置。

**`--platform linux/amd64`**：生产环境服务器通常为 x86_64 架构。在 Apple Silicon（arm64）Mac 上构建时不指定平台会产出 arm64 镜像，部署到 amd64 服务器将无法启动。所有构建命令均已包含此参数。

### 示例

```bash
# 单次构建并推送（需已登录 registry）
REGISTRY=registry.cn-shenzhen.aliyuncs.com/kye_secure

docker buildx build --platform linux/amd64 --progress=plain -t $REGISTRY/milesai-api:latest -f Dockerfile.api . --push
docker buildx build --platform linux/amd64 --progress=plain -t $REGISTRY/milesai-worker:latest -f Dockerfile.worker . --push
docker buildx build --platform linux/amd64 --progress=plain -t $REGISTRY/milesai-mcp-runner:latest -f Dockerfile.mcp-runner . --push
```

前端部署到 OSS，不走 Docker 镜像。

### 使用 BuildKit 缓存加速 CI

添加 `--cache-from` / `--cache-to` 可利用远程缓存（首次构建后，后续仅重编变更层）：

```bash
docker buildx build --platform linux/amd64 --progress=plain \
  -t registry.cn-shenzhen.aliyuncs.com/kye_secure/milesai-api:latest \
  -f Dockerfile.api . \
  --push \
  --cache-from registry.cn-shenzhen.aliyuncs.com/kye_secure/milesai-api:flow-docker-build-cache \
  --cache-to registry.cn-shenzhen.aliyuncs.com/kye_secure/milesai-api:flow-docker-build-cache
```

---

## 本地开发

### 仅后端

```bash
cd docker && docker compose -f docker-compose.infra.yml up -d   # 或本机 PG/Redis

cp backend/.env.example backend/.env   # POSTGRES_HOST=localhost
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python cli.py init-db              # 迁移 + 种子（API 启动不会自动写种子）
python cli.py serve                # 启动 API（debug 时默认热重载）
# 另开终端：
python cli.py worker               # Celery Worker（入库 / 生成 / 定时执行）
python cli.py beat                 # Celery Beat（智能体 Cron；Docker 全栈已含 beat 服务）
```

建库、迁移与种子：[docs/operations/database-setup.md](docs/operations/database-setup.md)。项目根：`./scripts/milesai.sh serve`、`./scripts/init-db.sh`。

### 前端工作台

```bash
cd ui/workbench && cp .env.local.example .env.local && npm install && npm run dev
# http://localhost:3000

cd ui/admin && cp .env.local.example .env.local && npm install && npm run dev
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
MilesAi/
├── backend/                 # FastAPI
│   ├── app/
│   │   ├── tenant/          # 租户 API（kb、agents、flows…）
│   │   ├── rag/             # L2：parse / chunk / index / retrieve / generate / pipeline
│   │   ├── integrations/  # L3：LangChain、LangGraph、DeepAgents
│   │   ├── infra/           # DB、Redis、对象存储、向量库客户端
│   │   ├── flow_runtime/    # 画布节点 registry
│   │   └── models/
│   └── alembic/
├── ui/                      # 前端应用
│   ├── workbench/           # 租户工作台
│   └── admin/               # 运营后台
├── docker/
└── docs/                    # → docs/README.md（product / features / architecture / guides / operations）
```

**分层**：`tenant/*/views` → `services` → `app/rag`（RAG）/ `app/integrations`（模型与图）→ `app/infra`（详见 [docs/architecture/layering.md](docs/architecture/layering.md)）。

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
| 工具 / MCP / 技能包 | `/workbench/tools` 等 | 工具目录、MCP、技能包 |
| 任务中心 | `/workbench/tasks` | 入库任务 + 生成任务 |
| 监控 | `/workbench/monitor` | 统计、趋势、Webhook 告警 |
| 合规 / 钩子 | `/workbench/compliance` 等 | 敏感词与 Webhook |
| 应用市场 | `/workbench/marketplace` | 打包、审核、安装 |

智能体产品语义（内部协同 vs A2A）：[docs/guides/a2a.md](docs/guides/a2a.md)。

---

## 实施阶段

| 阶段 | 状态 | 交付概要 |
|------|------|----------|
| P0 基础设施 | ✅ | Compose、JWT+RBAC、租户、Celery |
| P1 RAG 核心 | ✅ | 知识库、入库流水线、检索 |
| P2 编排与智能体 | ✅ | `flow_runtime`、画布、智能体对话 |
| P3 安全与工具 | ✅ | 敏感词、钩子、MCP、技能包、工具目录 |
| P4 应用市场 | ✅ | 审核上架、评分排序 |
| P5 运维增强 | ✅ | 任务中心、监控/infra 面板、Beat、批量任务；导出类见 [backlog](docs/product/backlog.md) 🔜 |
| P6 AI 栈增强 | ✅ | LangChain / LangGraph / DeepAgents 已接入，见 [docs/guides/ai-stack.md](docs/guides/ai-stack.md) |

---

## 常用文档

| 主题 | 文档 |
|------|------|
| 文档索引 | [docs/README.md](docs/README.md) |
| **功能规格（As-Is）** | [docs/features/](docs/features/)（见 [docs/README.md](docs/README.md) §功能节点） |
| 立项需求 | [docs/product/prd.md](docs/product/prd.md) |
| PRD 差距 backlog | [docs/product/backlog.md](docs/product/backlog.md) |
| 架构总纲 | [docs/architecture/technical-design.md](docs/architecture/technical-design.md) |
| 前端设计 | [docs/frontend/design.md](docs/frontend/design.md) |
| 数据库 | [docs/operations/database-setup.md](docs/operations/database-setup.md) |
| 部署与运行 | [docs/operations/deployment.md](docs/operations/deployment.md) |
| 流程编排 | [docs/guides/flows.md](docs/guides/flows.md) |
| 平台内智能体 | [docs/guides/platform-agents.md](docs/guides/platform-agents.md) |
| A2A 互联 | [docs/guides/a2a.md](docs/guides/a2a.md) |
| AI 栈 | [docs/guides/ai-stack.md](docs/guides/ai-stack.md) |
| 模型供应商 | [docs/guides/model-providers.md](docs/guides/model-providers.md) |
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
