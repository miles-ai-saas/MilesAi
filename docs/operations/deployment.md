# 部署与运行

**状态：** 已实现  
**关联：** [database-setup.md](./database-setup.md) · [../../docker/README.md](../../docker/README.md) · [technical-design.md §14](../architecture/technical-design.md#14-部署)

---

## 1. 部署拓扑

```text
┌─ docker-compose.infra.yml（独立部署单元）─────────────┐
│  postgres (pgvector) · redis · minio · etcd            │
│  milvus · weaviate · flower                            │
└───────────────────────────┬────────────────────────────┘
                            │ 经外部地址/端口互访（.env 配置）
┌─ docker-compose.yml（独立部署单元）───────────────────┐
│  api · worker · beat · mcp-runner                      │
└────────────────────────────────────────────────────────┘
```

前端（`ui/workbench`、`ui/admin`）**不随 Compose 部署**：本地 `npm run dev`，生产由 `npm run build` 产出静态文件托管到 OSS。

| 组件 | 端口（默认） | 说明 |
|------|-------------|------|
| 租户工作台 | 3000 | `ui/workbench` 本地 dev；生产为 OSS 静态资源 |
| 运营后台 | 3001 | `ui/admin` 本地 dev；生产为 OSS 静态资源 |
| FastAPI | 8000 | `api` |
| Flower | 5555 | `flower`（在 infra Compose 中） |
| PostgreSQL | 5432 | |
| Redis | 6379 | broker db1 / result db2 |
| MinIO | 9000 / 9001 | API / Console |
| Milvus | 19530 | Compose **应用栈默认**向量库 |
| Weaviate | 8080 | infra 可选，改 `.env` 切换 |

---

## 2. 快速启动

### 2.1 全栈 Docker（推荐）

```bash
cp .env.example .env
docker compose -f docker-compose.infra.yml -f docker-compose.yml up -d --build
cd backend && python cli.py init-db
```

### 2.2 仅中间件 + 本地开发

```bash
docker compose -f docker-compose.infra.yml up -d
cd backend
cp .env.example .env   # POSTGRES_HOST=localhost
python cli.py migrate && python cli.py init-db
python cli.py serve    # API :8000
python cli.py worker   # 另开终端
python cli.py beat     # 定时任务，可选
```

前端：ui/workbench/、`ui/admin/` 各自 `npm run dev`。

### 2.3 Makefile 快捷入口

项目根 `Makefile` 已封装上述步骤（`make help` 查看全部）：

```bash
make env            # .env.example → .env
make infra-up       # 仅中间件
make up             # 构建并启动应用栈（api/worker/beat/mcp-runner）
make up-dev         # 应用栈 + 挂载 ./backend 热重载
make init-db        # 迁移 + 全量种子
make serve          # 本地启动 API（不经 Docker）
```

镜像构建与推送：`make push-api` / `make push-worker` / `make push-mcp-runner`（可覆盖 `REGISTRY=`、`TAG=`、`PLATFORM=`）。

---

## 3. 关键环境变量

| 类别 | 变量 | 说明 |
|------|------|------|
| 向量库 | `VECTOR_STORE_BACKEND` | Compose 应用默认 `milvus`；本地可 `weaviate` |
| | `MILVUS_URI` / `WEAVIATE_*` | 与 backend 一致 |
| Celery | `CELERY_BROKER_URL` | 通常 `redis://…/1` |
| MCP | `MCP_RUNNER_ENABLED` | Docker 默认 true |
| | `MCP_RUNNER_URL` | 容器内 `http://mcp-runner:8090` |
| 前端 | `NEXT_PUBLIC_API_URL` | 租户 API |
| | `NEXT_PUBLIC_ADMIN_API_URL` | 运营 API `/api/admin/v1` |

完整列表见 `backend/.env.example`、`docs/architecture/technical-design.md` §15。

---

## 4. Celery 进程

| 进程 | Compose 服务 / 命令 | 队列 / 任务 |
|------|---------------------|-------------|
| Worker | `worker` · `python cli.py worker` | `default,parse,ocr,asr,embed` |
| Beat | `beat` · `python cli.py beat` | 每 60s `tick_agent_schedules` |

Worker 任务：`ingest_document`、`run_generative_*_job`、`run_agent_schedule`。  
详见 [features/task-center.md](../features/task-center.md)、[features/agent-schedules.md](../features/agent-schedules.md)。

**生产建议：** Worker、Beat 与 API 使用相同 `.env` 与向量库配置；本地仅中间件开发时需手动起 Beat。

---

## 5. Worker 可选依赖

| Extra | 能力 |
|-------|------|
| `[parse-docling]` | PDF/Office 版式解析 |
| `[multimodal]` | 图 OCR、音 Whisper |

Docker：修改 `docker/images/worker/Dockerfile` 中 `pip install -e ".[…]"` 后重建。  
见 [docker/README.md § Celery Worker](../../docker/README.md#celery-worker知识库入库)。

---

## 6. 健康检查

| 端点 | 说明 |
|------|------|
| `GET /api/v1/health` | 租户 API |
| Flower `:5555` | 任务队列 |
| MinIO Console `:9001` | 对象存储 |

---

## 7. 离线 / 私有化注意

- 镜像需预拉或使用内网 registry；模型 API Key 由租户工作台配置（BYOK）。
- 向量化模型、对话模型可走 LiteLLM 兼容端点或本地 Ollama（见 [model-providers.md](../guides/model-providers.md)）。
- **离线 OpenAPI 导出 / 完整离线手册**：尚未单独文档化（technical-design §16 ⬜）。

---

## 8. 相关文档

- [database-setup.md](./database-setup.md) — 迁移与种子
- [features/admin-ops.md](../features/admin-ops.md) — 运营后台
- [docker/README.md](../../docker/README.md) — Compose 细节
