# Docker Compose 说明

Compose 已拆分为 **中间件** 与 **应用** 两个文件，通过共享网络 `milesai-net` 通信。

## 文件

| 文件 | 服务 | 说明 |
|------|------|------|
| `docker-compose.middleware.yml` | postgres, redis, minio, weaviate；可选 `milvus`（profile） | 数据与基础设施 |
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
docker compose -f docker-compose.middleware.yml up -d
```

`backend/.env` 使用 `POSTGRES_HOST=localhost` 等宿主机端口。

### 2. 仅应用（需中间件已运行）

```bash
cd docker
docker compose -f docker-compose.middleware.yml up -d   # 若未启动
docker compose up -d --build
```

### 3. 一键全栈（推荐）

```bash
cd docker
docker compose -f docker-compose.middleware.yml -f docker-compose.yml up -d --build
```

### 4. 停止

```bash
# 停应用
docker compose down

# 停中间件（保留数据卷）
docker compose -f docker-compose.middleware.yml down

# 停中间件并删除数据卷（慎用）
docker compose -f docker-compose.middleware.yml down -v
```

## 网络与服务发现

- 中间件创建网络：`milesai-net`
- 应用栈加入同一外部网络后，容器内可通过服务名访问：`postgres`、`redis`、`minio`、`weaviate`（或 `milvus`）
- 宿主机访问仍用映射端口：`5432`、`6379`、`9000`、`8080`、`19530`（Milvus）等

### 使用 Milvus 作为向量库

```bash
cd docker
docker compose -f docker-compose.middleware.yml --profile milvus up -d
```

`.env` 中设置：

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
| `MILVUS_PORT` | 19530 | Milvus gRPC/HTTP |
| `API_PORT` | 8000 | FastAPI |
| `WEB_PORT` | 3000 | 租户 AI 工作台 |
| `ADMIN_WEB_PORT` | 3001 | 平台运营后台 |
| `FLOWER_PORT` | 5555 | Celery Flower |

## 数据库

PostgreSQL 由中间件自动建库（`POSTGRES_DB`）。表结构与种子需手动执行（API 启动仅跑迁移，不写种子）：

```bash
cd ../backend && python cli.py init-db
# 或：python cli.py migrate && python cli.py init-db --seed-only
```

详见 [docs/operations/database-setup.md](../docs/operations/database-setup.md)。
