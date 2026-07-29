# 设计：工程债三项 — 卫生 / OpenAPI schema CI / OTel traces

**日期：** 2026-07-29  
**状态：** 已批准（对话确认；待实现）  
**范围：** 三项按序落地；互不阻塞，可分 commit。

---

## 0. 决策摘要

| 项 | 决策 |
|----|------|
| 工程卫生 | ignore `celerybeat-schedule*`；admin 仅 npm，删除 `pnpm-lock.yaml` |
| OpenAPI | **C**：schema CI diff；**不做** codegen（二期） |
| 可观测性 | **B**：OTel traces → OTLP；默认关闭；MVP **仅 API**；不做 Sentry/metrics/前端 RUM |

---

## 1. 工程卫生

### 目标

- 避免 Celery Beat 本地调度文件污染仓库。
- 消除 admin 双包管理器歧义，与 CI（`npm ci`）及根 README 一致。

### 变更

1. `.gitignore` 增加：
   - `celerybeat-schedule.db`
   - `celerybeat-schedule*`（覆盖无后缀变体）
2. 若 `celerybeat-schedule.db` 已 tracked：`git rm --cached`（不删本地文件亦可）。
3. 删除 `ui/admin/pnpm-lock.yaml`。
4. 更新 `ui/README.md`：admin 安装改为 `npm install` / `npm ci`，去掉「admin 常用 pnpm」。
5. 根 `README.md` 若已写 npm 则仅核对；不一致则统一为 npm。

### 验收

- 新产生的 beat 调度文件不再被 `git status` 列出。
- admin 仅保留 `package-lock.json`。

---

## 2. OpenAPI schema CI

### 目标

后端契约变更时 CI 失败，迫使更新快照；**不**自动改写前端 `lib/types`。

### 落点

| 产物 | 路径（建议） |
|------|----------------|
| 快照 | `backend/openapi/openapi.snapshot.json` |
| 导出脚本 | `backend/scripts/export_openapi.py`（或 `backend/cli` 子命令） |

### 行为

1. 脚本调用 `create_app().openapi()`（ASGI 工厂，**不起 uvicorn**）。
2. 默认与快照 **规范化 JSON** 比较（`json.dumps(..., sort_keys=True, ensure_ascii=False, indent=2)` 或等价 canonical）。
3. `--write`：重写快照。
4. CI：在 `.github/workflows/lint.yml` 增加 backend 步骤，或独立 job `openapi`：
   - `pip install -e ".[dev]"`（或最小依赖能 import app）
   - `python scripts/export_openapi.py --check`
5. 失败信息提示：本地执行 `--write` 并提交快照。

### 非目标

- orval / openapi-typescript codegen
- 比对前端 `lib/types` 与 OpenAPI 的字段级一致性
- 运行真实 Postgres 才能导出（export 不得依赖外部中间件；若 `create_app` 触达 DB，则用现有测试同款 mock/env）

### 验收

- 故意改一处 schema 字段 → CI check 失败。
- `--write` 后 check 通过。

---

## 3. OpenTelemetry traces（OTLP）

### 目标

API 进程可向 OTLP endpoint 导出 HTTP/应用 traces；私有化默认关闭。

### 配置

| 环境变量 | 默认 | 说明 |
|----------|------|------|
| `OTEL_ENABLED` | `false` | 总开关 |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | 空 | 如 `http://localhost:4318`；空则 no-op（即使 enabled 也只初始化不导出或直接跳过） |
| `OTEL_SERVICE_NAME` | `milesai-api` | resource service.name |
| （可选）`OTEL_EXPORTER_OTLP_PROTOCOL` | `http/protobuf` | 与 collector 对齐 |

映射进 `app.core.config.Settings`（字段名与现有风格一致，如 `otel_enabled`）。

### 实现要点

1. **可选依赖**：`pyproject.toml` extra `[otel]`：`opentelemetry-api`、`opentelemetry-sdk`、`opentelemetry-exporter-otlp`、`opentelemetry-instrumentation-fastapi`（及所需 ASGI/httpx 若已用）。
2. **初始化**：在 `lifespan` 启动早期或 `create_app` 末尾调用 `setup_otel(settings)`；关闭时 `shutdown`。
3. **Instrumentation**：FastAPI 自动埋点；保留现有 `TraceMiddleware`（`X-Trace-Id` → ContextVar + 响应头）。
4. **关联**：将业务 `trace_id`（或请求头 `X-Trace-Id`）写入当前 span attribute（如 `miles.trace_id`），**不强制**替换 W3C `traceparent`。
5. **Worker/Beat**：本 MVP **不接**；文档注明二期。
6. **Docker**：镜像可不默认装 `[otel]`；需要时文档说明 `pip install -e ".[otel]"` 或生产镜像可选层。若团队希望默认镜像含 otel，在实现计划中二选一并写死（推荐 **extra 可选**，减小默认镜像）。

### 非目标

- Sentry / 错误上报产品
- Metrics / Prometheus 全量
- 前端 RUM
- 强制 Collector 进 `docker-compose`（文档给示例 endpoint 即可；可选 compose profile 二期）

### 验收

- `OTEL_ENABLED=false`：行为与现网一致，无导出。
- `OTEL_ENABLED=true` + 本地 collector：可见 API 请求 span。
- 未装 `[otel]` 且未启用：应用可启动（动态 import，勿硬依赖）。

---

## 4. 实施顺序与提交

1. 卫生（chore）  
2. OpenAPI 快照 + 脚本 + CI（ci/chore）  
3. OTel 配置 + instrumentation（feat）  

Commit message 简体中文 Conventional Commits。

---

## 5. 风险

| 风险 | 缓解 |
|------|------|
| `create_app()` 导出时拉起 DB | 与测试相同：仅构建 app；必要时 setenv 假配置 |
| OTel 包体积 | `[otel]` extra；默认路径不 import |
| 双 trace 体系混淆 | 文档标明：`X-Trace-Id` 业务信封 vs OTel W3C |

---

## 6. 二期（明确不做于本 spec）

- OpenAPI → TS codegen  
- Celery Worker OTel  
- Sentry / 错误产品化  
- compose 内嵌 Jaeger profile（可选后续）
