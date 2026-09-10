# 工程债三项 Implementation Plan

> **归档：** 实施 checklist（2026-07-29）。**现网门禁：** `.github/workflows/lint.yml`（OpenAPI 快照 `backend/openapi/openapi.snapshot.json`、`scripts/export_openapi.py --check`）；OTel 见 `backend/app/infra/otel.py`（`pyproject.toml` 可选 extra `otel`）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地工程卫生、OpenAPI schema CI、API 侧 OTel traces（默认关闭）。

**Architecture:** 三项独立可测：gitignore/lockfile → `create_app().openapi()` 快照门禁 → optional `[otel]` + lifespan 初始化 OTLP。

**Tech Stack:** GitHub Actions、FastAPI OpenAPI、OpenTelemetry Python SDK + OTLP exporter + FastAPI instrumentation。

**Spec:** [docs/superpowers/specs/2026-07-29-eng-debt-hygiene-openapi-otel-design.md](../specs/2026-07-29-eng-debt-hygiene-openapi-otel-design.md)

## Global Constraints

- Commit message 简体中文 Conventional Commits。
- OpenAPI：**只做 schema CI**，不做 TS codegen。
- OTel：默认 `OTEL_ENABLED=false`；MVP **仅 API**；依赖放 `[otel]` extra；未安装 extra 时启用须优雅失败或明确提示。
- 不引入 Sentry / metrics / 前端 RUM。
- 保留现有 `X-Trace-Id` TraceMiddleware。

---

## File Structure

| 路径 | 职责 |
|------|------|
| `.gitignore` | celerybeat 忽略 |
| `ui/admin/pnpm-lock.yaml` | 删除 |
| `ui/README.md` | npm 统一说明 |
| `backend/scripts/export_openapi.py` | 导出/校验快照 |
| `backend/openapi/openapi.snapshot.json` | 契约快照 |
| `.github/workflows/lint.yml` | openapi check 步骤 |
| `backend/pyproject.toml` | `[otel]` extra |
| `backend/app/core/config.py` | otel_* settings |
| `backend/app/infra/otel.py`（新建） | setup/shutdown |
| `backend/app/apps/application.py` | lifespan 调用 |
| `.env.example` / `backend/.env.example` | 文档化变量 |

---

### Task 1: 工程卫生

**Files:**
- Modify: `.gitignore`
- Delete: `ui/admin/pnpm-lock.yaml`
- Modify: `ui/README.md`
- Possibly: `git rm --cached celerybeat-schedule.db`

- [ ] **Step 1: 更新 `.gitignore`**

在现有 `celerybeat-schedule.db.worktrees/` 旁增加：

```gitignore
celerybeat-schedule.db
celerybeat-schedule*
```

- [ ] **Step 2: 取消跟踪 beat 文件（若 tracked）**

```bash
git rm --cached celerybeat-schedule.db 2>/dev/null || true
```

- [ ] **Step 3: 删除 admin pnpm lock，改 README**

```bash
git rm ui/admin/pnpm-lock.yaml
```

`ui/README.md` 安装段改为：

```bash
cd ui/workbench && npm install
cd ui/admin && npm install
```

去掉「admin 常用 pnpm」表述。

- [ ] **Step 4: Commit**

```bash
git add .gitignore ui/README.md
git commit -m "$(cat <<'EOF'
chore: 忽略 celerybeat 调度文件并统一 admin 为 npm

删除 pnpm-lock，与 CI npm ci 一致。
EOF
)"
```

---

### Task 2: OpenAPI 快照脚本 + CI

**Files:**
- Create: `backend/scripts/export_openapi.py`
- Create: `backend/openapi/openapi.snapshot.json`
- Create: `backend/openapi/.gitkeep`（若需目录；有快照则可省略）
- Modify: `.github/workflows/lint.yml`
- Test: 本地 `--check` 通过；改 schema 则失败（手工或单测可选）

**Interfaces:**

```text
python scripts/export_openapi.py          # 默认 --check
python scripts/export_openapi.py --check
python scripts/export_openapi.py --write
```

- [ ] **Step 1: 实现导出脚本**

在 `backend/` 下运行。核心逻辑：

```python
"""导出/校验 FastAPI OpenAPI 快照（无需起 uvicorn）。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "openapi" / "openapi.snapshot.json"


def dump_schema() -> str:
    # 确保可 import：sys.path 含 backend 或从 backend 目录执行
    from app.apps.application import create_app

    schema = create_app().openapi()
    return json.dumps(schema, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def main() -> int:
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group()
    g.add_argument("--check", action="store_true", default=True)
    g.add_argument("--write", action="store_true")
    args = p.parse_args()
    text = dump_schema()
    if args.write:
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_text(text, encoding="utf-8")
        print(f"wrote {SNAPSHOT}")
        return 0
    if not SNAPSHOT.exists():
        print(f"missing snapshot: {SNAPSHOT}; run with --write", file=sys.stderr)
        return 1
    current = SNAPSHOT.read_text(encoding="utf-8")
    if current != text:
        print("OpenAPI snapshot drift. Run: python scripts/export_openapi.py --write", file=sys.stderr)
        return 1
    print("OpenAPI snapshot OK")
    return 0


if __name__ == "__main__":
    # 修复 argparse：--write 时应关闭默认 check
    raise SystemExit(main())
```

注意：修正 argparse，使仅 `--write` 时写入；默认或 `--check` 时校验。若 `create_app()` 需 env，脚本开头 `os.environ.setdefault` 最小假配置（对齐 tests/conftest 所需项，查 `.env.example`）。

- [ ] **Step 2: 生成本地快照**

```bash
cd backend && python scripts/export_openapi.py --write
python scripts/export_openapi.py --check
```

Expected: OK

- [ ] **Step 3: CI 步骤**

在 `lint.yml` 的 `backend` job（或新 job）增加：安装项目后：

```yaml
      - name: Install backend
        run: pip install -e ".[dev]"
      - name: OpenAPI snapshot check
        run: python scripts/export_openapi.py --check
```

（若现有 job 只装 ruff，需改为可 import app 的安装；注意耗时，可接受。）

- [ ] **Step 4: Commit**

```bash
git commit -m "$(cat <<'EOF'
ci(backend): 增加 OpenAPI 快照校验防止契约漂移

导出 create_app().openapi()，与仓库快照比对。
EOF
)"
```

---

### Task 3: OTel traces（API）

**Files:**
- Modify: `backend/pyproject.toml` — `[project.optional-dependencies] otel = [...]`
- Modify: `backend/app/core/config.py` — `otel_enabled`, `otel_exporter_otlp_endpoint`, `otel_service_name`
- Create: `backend/app/infra/otel.py`
- Modify: `backend/app/apps/application.py` — lifespan setup/shutdown
- Modify: `.env.example` 与 `backend/.env.example`（若存在）
- Test: `tests/infra/test_otel_setup.py` — disabled 时 no-op；enabled 无 endpoint 时不炸

**Interfaces:**

```python
# app/infra/otel.py
def setup_otel(settings) -> None: ...
def shutdown_otel() -> None: ...
```

- [ ] **Step 1: 失败测试 — disabled 可调用**

```python
def test_setup_otel_disabled_is_noop(monkeypatch):
    from app.infra import otel
    settings = MagicMock(otel_enabled=False, otel_exporter_otlp_endpoint="", otel_service_name="milesai-api")
    otel.setup_otel(settings)  # 不抛
    otel.shutdown_otel()
```

- [ ] **Step 2: 实现 `otel.py`**

逻辑：
1. `if not settings.otel_enabled: return`
2. `try: import opentelemetry... except ImportError: log warning; return`
3. 若 endpoint 空：log 并 return（或设 ConsoleExporter 仅 debug——**spec 要求 no-op，不要 Console**）
4. TracerProvider + Resource(service.name=...) + OTLPSpanExporter + BatchSpanProcessor
5. `FastAPIInstrumentor.instrument_app(app)` — **需要 app 引用**：故 `setup_otel(settings, app=app)` 签名带 app
6. lifespan：`setup_otel(settings, app)`；yield 后 `shutdown_otel()`

将 `miles.trace_id`：可用 Starlette 中间件或 instrumentation request hook 从 `request.state.trace_id` 写入 span（可选最小实现：文档说明二期 hook；MVP 至少导出 HTTP spans）。

**MVP 最低要求：** enabled+endpoint+已装 `[otel]` → FastAPI 请求产生 span 并导出。业务 `X-Trace-Id` attribute **尽量做**；若实现成本高可记 follow-up，但 plan 优先实现简单 hook：

```python
def _client_request_hook(span, scope):
    # 从 scope headers 读 x-trace-id
    ...
```

- [ ] **Step 3: Settings + env 示例**

```python
otel_enabled: bool = False
otel_exporter_otlp_endpoint: str = ""
otel_service_name: str = "milesai-api"
```

- [ ] **Step 4: pyproject otel extra**

```toml
otel = [
  "opentelemetry-api>=1.28.0",
  "opentelemetry-sdk>=1.28.0",
  "opentelemetry-exporter-otlp>=1.28.0",
  "opentelemetry-instrumentation-fastapi>=0.49b0",
]
```

版本以安装时解析为准，可钉合理下限。

- [ ] **Step 5: pytest + commit**

```bash
cd backend && python -m pytest tests/infra/test_otel_setup.py -q
```

```bash
git commit -m "$(cat <<'EOF'
feat(infra): API 支持可选 OpenTelemetry OTLP 导出

默认关闭；需安装 [otel] extra 并配置 endpoint。
EOF
)"
```

---

### Task 4: 文档短注（可并入 Task 2/3）

**Files:**
- Modify: `backend/README.md` 或 `docs/operations/` 短节（若无 operations 条目则在 backend README 增加「OpenAPI 快照」「OTel」两小节）

- [ ] **Step 1:** 写明 `--check`/`--write`、`pip install -e ".[otel]"`、环境变量
- [ ] **Step 2:** Commit（若有独立改动）

```bash
git commit -m "$(cat <<'EOF'
docs: 补充 OpenAPI 快照与 OTel 开关说明
EOF
)"
```

---

## Spec coverage

| Spec | Task |
|------|------|
| celerybeat ignore + rm cached | 1 |
| 删 pnpm-lock + README npm | 1 |
| export script + snapshot + CI | 2 |
| otel settings + extra + setup | 3 |
| 仅 API、默认关、无 Sentry | 3 |
| 操作文档 | 4 |

## Placeholder scan

无 TBD；OTLP protocol 默认 http/protobuf；Worker 明确不做。
