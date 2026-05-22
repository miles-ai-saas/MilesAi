# Docker Compose 说明

Compose 已拆分为 **基础设施（infra）** 与 **应用** 两个文件，通过共享网络 `milesai-net` 通信。

## 文件

| 文件 | 服务 | 说明 |
|------|------|------|
| `docker-compose.infra.yml` | pgvector、redis、minio、etcd、milvus、weaviate | 数据与基础设施 |
| `docker-compose.yml` | api, worker, web, admin-web, flower | 业务应用 |

## 环境变量

在项目根目录准备 `.env`（可由 `.env.example` 复制）：

```bash
cp ../.env.example ../.env
```

在 `docker` 目录执行 compose 时会自动读取 `../.env`。

## 启动顺序

### 1. 仅中间件（本地跑后端 / 前端时常用）

```bash
cd docker
docker compose -f docker-compose.infra.yml up -d
```

`backend/.env` 使用 `POSTGRES_HOST=localhost` 等宿主机端口。

### 2. 仅应用（需中间件已运行）

```bash
cd docker
docker compose -f docker-compose.infra.yml up -d   # 若未启动
docker compose up -d --build
```

### 3. 一键全栈（推荐）

```bash
cd docker
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

- 中间件创建网络：`milesai-net`
- 应用栈加入同一外部网络后，容器内可通过服务名访问：`postgres`、`redis`、`minio`、`etcd`、`milvus`、`weaviate`
- 宿主机访问仍用映射端口：`5432`、`6379`、`9000`、`8080`、`19530`、`19531`（Milvus 指标）等

### Weaviate 版本（默认向量库）

Compose 使用 **Weaviate 1.27.26**（`weaviate-client` 4.x 要求服务端 **≥ 1.27.0**）。若仍报 `Weaviate version 1.24.x is not supported`：

```bash
cd docker
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
| `WEB_PORT` | 3000 | 租户 AI 工作台 |
| `ADMIN_WEB_PORT` | 3001 | 平台运营后台 |
| `FLOWER_PORT` | 5555 | Celery Flower |

## 数据库

PostgreSQL（pgvector 镜像）由 infra 自动建库（`POSTGRES_DB`），首次启动执行 `deploy/scripts/init_db.sql` 启用 `vector` 扩展。表结构与种子需手动执行（API 启动仅跑迁移，不写种子）：

```bash
cd ../backend && python cli.py init-db
# 或：python cli.py migrate && python cli.py init-db --seed-only
```

详见 [docs/operations/database-setup.md](../docs/operations/database-setup.md)。

## Celery Worker（知识库入库）

| 项 | 说明 |
|----|------|
| 容器 | `milesai-worker`（`docker-compose.yml` → `worker`） |
| 命令 | `celery -A app.workers.app worker -Q default,parse,ocr,asr,embed` |
| 主任务 | `ingest_document`：下载对象 → `app.rag.pipeline.run_ingest_pipeline` |
| 与 API | **须能访问** PostgreSQL、Redis、MinIO、向量库（`VECTOR_STORE_BACKEND` 与 `.env` 一致） |

队列名 `parse` / `ocr` / `asr` / `embed` 为历史划分，当前入库逻辑集中在 `ingest_document`；消费 `embed`（及 `default`）即可跑通知识库。

### RAG 可选依赖（Worker 镜像）

默认 `docker/images/worker/Dockerfile` 仅 `pip install -e /app/backend`（**pypdf + 文本 + 图/音占位**）。需要下列能力时，在镜像构建阶段安装 extras（**API 与 Worker 应保持一致**）：

| Extra | 安装 | 能力 |
|-------|------|------|
| `parse-docling` | `pip install -e "/app/backend[parse-docling]"` | `PARSE_PDF_BACKEND=docling`，PDF/Office 版式 |
| `multimodal` | `pip install -e "/app/backend[multimodal]"` | 图 OCR（pytesseract）、音 Whisper 转写 |

示例（修改 `docker/images/worker/Dockerfile` 中 pip 行后 `--build`）：

```dockerfile
RUN pip install --no-cache-dir -e "/app/backend[parse-docling,multimodal]"
```

`.env` 解析相关变量见 `backend/.env.example`（`PARSE_PDF_BACKEND`、`PARSE_DOCLING_FALLBACK_PYPDF`）。

**实现说明**（非 PRD 全量）：[docs/guides/knowledge-base.md](../docs/guides/knowledge-base.md)、[docs/architecture/layering.md](../docs/architecture/layering.md)。
