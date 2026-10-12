# 离线 / 私有化部署手册

**状态：** 已实现  
**关联：** [deployment.md](./deployment.md) · [database-setup.md](./database-setup.md) · [../../docker/README.md](../../docker/README.md) · [model-providers.md](../guides/model-providers.md)

本文说明**无公网或受限网络**环境下的镜像准备、契约导出与运行检查清单。日常在线部署仍以 [deployment.md](./deployment.md) 为准。

---

## 1. OpenAPI 契约离线导出

运行中的 `GET /openapi.json` / `/docs` 需要 API 进程；离线交付或内网评审可**不起服务**直接生成契约：

```bash
# 仓库快照（CI 与 make openapi-check 比对）
make openapi-write
# 等价：cd backend && python -m miles_server.scripts.export_openapi --write
# 产物：backend/openapi/openapi.snapshot.json

# 导出到任意路径（离线包 / 发给对接方；不改仓库快照）
cd backend && python -m miles_server.scripts.export_openapi --out /tmp/milesai-openapi.json
```

| 用途 | 命令 |
|------|------|
| 防 API 漂移（开发/CI） | `make openapi-check` |
| 更新仓库契约并提交 | `make openapi-write` |
| 离线分发单文件 | `--out PATH` |

快照含租户 `/api/v1`、运营 `/api/admin/v1` 与开放面 `/api/v1/open/*`（同一 FastAPI 应用）。

---

## 2. 镜像与内网 Registry

1. 在可联网环境构建并保存镜像（示例）：

```bash
make build-all TAG=vX.Y.Z
# 或按需：make build-api / build-worker / build-mcp-runner
docker save -o milesai-images-vX.Y.Z.tar \
  ${REGISTRY}/milesai-api:vX.Y.Z \
  ${REGISTRY}/milesai-worker:vX.Y.Z \
  ${REGISTRY}/milesai-mcp-runner:vX.Y.Z
```

2. 内网 `docker load -i …` 后推送到私有 registry，或直接 `docker tag` + Compose 改镜像名。
3. 中间件镜像（Postgres / Redis / MinIO / Milvus 等）同样预拉或走内网源；见 `docker-compose.infra.yml`。

Compose 中将 `image:` 指向内网地址；**不要**依赖构建期访问 Docker Hub / npm / PyPI（应用镜像应在联网侧已 `uv sync` / 预装 MCP 包）。

---

## 3. 配置清单（离线相关）

| 项 | 建议 |
|----|------|
| `.env` | 由联网侧模板拷贝；`POSTGRES_*` / `REDIS_*` / `MINIO_*` / `VECTOR_*` 指向内网 |
| 模型 | 平台内置 Key 在运营后台配置，或租户 BYOK；本地 Ollama / 内网 LiteLLM 兼容端点见 [model-providers.md](../guides/model-providers.md) |
| `OUTBOUND_ALLOW_PRIVATE_HOSTS` | 生产收紧为 `false` 时，确认 MCP HTTP 与技能 Git 不依赖内网例外 |
| `MCP_RUNNER_*` | 启用 STDIO 时 Runner 与 API 同网；npx 默认包白名单，拉包需 `network_mode=allow` 或镜像预装 |
| 前端 | `npm run build` 在联网侧完成，静态产物上传内网 OSS / Nginx；`NEXT_PUBLIC_*_API_URL` 指向内网 API |

---

## 4. 首次启动顺序

```bash
# 1. 中间件
docker compose -f docker-compose.infra.yml up -d

# 2. 应用（镜像已 load）
docker compose up -d

# 3. 迁移 + 种子（在可执行 milesai 的环境）
cd backend && milesai init-db
# 或：make init-db
```

验证：

- `GET /api/v1/health`
- 运营登录与内置模型目录
- 可选：对照已导出的 `openapi.snapshot.json` 与运行中 `/openapi.json`（大版本升级时）

---

## 5. 交付物建议包

| 内容 | 说明 |
|------|------|
| 镜像 tar 或 registry 清单 | api / worker / mcp-runner + infra |
| `openapi` JSON | `--out` 或仓库 `openapi.snapshot.json` |
| `.env.example` + 内网改写说明 | 不含真实密钥 |
| 本文 + [deployment.md](./deployment.md) | 运维手册 |
| 可选：模型目录导入 JSON | 运营 `POST /model-catalog/import`，见 [model-providers.md](../guides/model-providers.md) §9 |

---

## 6. 相关命令速查

| 命令 | 说明 |
|------|------|
| `make openapi-check` / `openapi-write` | 契约校验 / 写快照 |
| `python -m miles_server.scripts.export_openapi --out …` | 离线导出 |
| `make build-all` / `push-all` | 镜像构建推送 |
| `make init-db` | 迁移 + 种子 |
| `make infra-up` / `make up` | 中间件 / 应用栈 |
