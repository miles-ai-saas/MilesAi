# Docker Compose 说明

基础设施（`docker-compose.infra.yml`）与业务应用（`docker-compose.yml`）为**独立部署单元**，通常不在同一台服务器上。
本地开发时可通过端口映射互访；生产环境请通过 `.env` 配置外部地址。

## 文件

| 文件 | 服务 | 说明 |
|------|------|------|
| `docker-compose.infra.yml` | pgvector、redis、minio、etcd、milvus、weaviate、flower | 数据与基础设施 |
| `docker-compose.yml` | api, worker, beat, mcp-runner | 业务应用（前端已部署 OSS） |

## 环境变量

在项目根目录准备 `.env`（可由 `.env.example` 复制）：

```bash
cp .env.example .env
```

## 启动顺序

Compose 文件位于项目根目录，所有命令均在项目根目录执行。

### 1. 仅中间件（本地跑后端 / 前端时常用）

```bash
docker compose -f docker-compose.infra.yml up -d
```

`backend/.env` 使用 `POSTGRES_HOST=localhost` 等宿主机端口。

### 2. 仅应用（需中间件已运行）

```bash
docker compose -f docker-compose.infra.yml up -d   # 若未启动
docker compose up -d --build

# 开发模式：挂载本地 backend/ 实现热重载
docker compose --profile dev up -d --build
```

### 3. 一键全栈（推荐）

```bash
docker compose -f docker-compose.infra.yml -f docker-compose.yml up -d --build
```

### 4. 停止

```bash
# 停应用
docker compose down

# 停中间件（保留数据卷）
docker compose -f docker-compose.infra.yml down

# 停中间件并删除数据卷（慎用）
docker compose -f docker-compose.infra.yml down -v
```

## 网络与服务发现

基础设施与应用**不在同一 Docker 网络**内。两者通过宿主机映射端口通信：

- 应用通过 `.env` 中的 `POSTGRES_HOST` / `REDIS_HOST` 等变量连接基础设施
- 本地开发时通常设为 `localhost`，生产部署时改为实际 IP 或域名

常用端口映射：

| 服务 | 端口 |
|------|------|
| PostgreSQL | 5432 |
| Redis | 6379 |
| MinIO API | 9000 |
| MinIO Console | 9001 |
| Milvus | 19530 |
| Weaviate | 8080 |
| API | 8000 |
| MCP Runner | 8090 |

### Weaviate 版本（默认向量库）

Compose 使用 **Weaviate 1.27.26**（`weaviate-client` 4.x 要求服务端 **≥ 1.27.0**）。若仍报 `Weaviate version 1.24.x is not supported`：

```bash
docker compose -f docker-compose.infra.yml pull weaviate
docker compose -f docker-compose.infra.yml up -d weaviate
```

大版本升级后若 schema 不兼容，可删除卷重建（会清空向量数据，文档需在平台重试入库）：

```bash
docker compose -f docker-compose.infra.yml down
docker volume rm milesai-weaviate-data   # 慎用
docker compose -f docker-compose.infra.yml up -d weaviate
```

### 使用 Milvus 作为向量库

Milvus 随 `docker-compose.infra.yml` 默认启动（依赖 `etcd` + `minio`）。`.env` 中设置：

```env
VECTOR_STORE_BACKEND=milvus
MILVUS_URI=http://milvus:19530   # 容器内；本地直连用 http://localhost:19530
```

## 端口（可通过 .env 覆盖）

| 变量 | 默认 | 服务 |
|------|------|------|
| `POSTGRES_PORT` | 5432 | PostgreSQL |
| `REDIS_PORT` | 6379 | Redis |
| `OBJECT_STORAGE_PORT` | 9000 | 对象存储 API（Compose 中 MinIO 服务） |
| `OBJECT_STORAGE_CONSOLE_PORT` | 9001 | MinIO Console |
| `WEAVIATE_PORT` | 8080 | Weaviate |
| `MILVUS_PORT` | 19530 | Milvus gRPC |
| `MILVUS_METRICS_PORT` | 19531 | Milvus 指标/健康检查（宿主机） |
| `API_PORT` | 8000 | FastAPI |
| `FLOWER_PORT` | 5555 | Celery Flower |

> 前端端口见 `ui/workbench` / `ui/admin` 本地开发，生产已部署到 OSS。

## 数据库

PostgreSQL（pgvector 镜像）由 infra 自动建库（`POSTGRES_DB`），首次启动执行 `docker/deploy/scripts/init_db.sql` 启用 `vector` 扩展。表结构与种子需手动执行（API 启动仅跑迁移，不写种子）：

```bash
cd backend && uv run milesai init-db
# 或：uv run milesai migrate && uv run milesai init-db --seed-only
```

详见 [docs/operations/database-setup.md](../docs/operations/database-setup.md)。

## Celery Worker（知识库入库）

| 项 | 说明 |
|----|------|
| 容器 | `milesai-worker`（`docker-compose.yml` → `worker`） |
| 命令 | `celery -A miles_worker.app worker -Q default,parse,ocr,asr,embed` |
| 主任务 | `ingest_document`：下载对象 → `miles_ai.rag.pipeline.run_ingest_pipeline` |
| 与 API | **须能访问** PostgreSQL、Redis、MinIO、向量库（`VECTOR_STORE_BACKEND` 与 `.env` 一致） |

队列名 `parse` / `ocr` / `asr` / `embed` 为历史划分，当前入库逻辑集中在 `ingest_document`；消费 `embed`（及 `default`）即可跑通知识库。

### RAG / 多模态依赖（Worker 镜像）

`Dockerfile.worker` 按 `miles-worker` 的依赖闭包安装：先 `uv export --package miles-worker` + `uv pip install -r`，再以 editable 安装本地成员包（`miles-common` / `miles-exec` / `miles-core` / `miles-ai` / `miles-portal` / `miles-worker`）。解析与多模态依赖（`pypdf`、`docling`、`pytesseract`、`openai-whisper`）已在 `miles-ai` 中无条件声明，无需 extras；**API 与 Worker 的依赖应保持一致**。

`.env` 解析相关变量见 `backend/.env.example`（`PARSE_PDF_BACKEND`、`PARSE_DOCLING_FALLBACK_PYPDF`）。

## Celery Beat（智能体定时任务）

| 项 | 说明 |
|----|------|
| 容器 | `milesai-beat`（`docker-compose.yml` → `beat`） |
| 命令 | `celery -A miles_worker.app beat -l info` |
| 镜像 | 与 `worker` 相同（`docker/images/worker/Dockerfile`） |
| 任务 | 每分钟 `tick_agent_schedules`，到期 schedule 投递 `run_agent_schedule` |

本地仅中间件开发时：`cd backend && uv run milesai beat`（与 worker 并列进程）。

**实现说明**（非 PRD 全量）：[docs/guides/knowledge-base.md](../docs/guides/knowledge-base.md)、[docs/architecture/layering.md](../docs/architecture/layering.md)。
