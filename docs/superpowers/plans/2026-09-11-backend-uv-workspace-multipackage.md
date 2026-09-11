# 后端多包工作区迁移 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `backend/` 从单一 `milesai` 包迁移为 10 个 uv workspace 包（`miles_common/exec/core/ai/portal/admin/openapi/server/worker/runner`），行为不变。

**Architecture:** 先在同一包内（`app/`）完成破环与减重，再建 workspace、一次性物理搬迁 + 全量 import codemod，最后改工具链（cli/scripts/Dockerfile/CI）。设计依据见 [spec](../specs/2026-09-11-backend-uv-workspace-multipackage-design.md)。

**Tech Stack:** Python 3.11+、uv 0.11.7、setuptools/hatchling、FastAPI、SQLAlchemy、Alembic、Celery、import-linter、ruff、pytest。

## Global Constraints

- **行为不变**：迁移前后由 `scripts/export_openapi.py` 生成的 schema **逐字节相同**；全量 `pytest` 通过；`/api/v1`、`/api/admin/v1`、`/api/v1/open/*` 路径不变；数据库表名不变。
- **解释器（极易踩坑，务必遵守）**：所有 Python/ruff 命令必须用 `backend/.venv/bin/python`、`backend/.venv/bin/ruff`（或表格 `$(PY)`/`uv run`）。**禁止裸用 `python`/`ruff`**——PATH 上是 miniconda（pydantic 2.12.5 / fastapi 0.128.8），与 venv（2.13.4 / 0.136.1）的 schema 渲染不同，会让 `export_openapi.py --check` **误报漂移**（实测差异 13 处：`format: binary` vs `contentMediaType`、`AgentPackage` vs `-Input/-Output`）。
- **依赖方向**（spec §2）：`miles_common`/`miles_exec` 为叶子；`miles_core → common`；`miles_ai → core`；`miles_portal → ai`；`miles_admin → portal`；`miles_openapi → portal`；`miles_server → openapi`；`miles_worker → portal`；`miles_runner → exec`。
- **硬判据**：`miles_ai ✗→ miles_portal`；`miles_openapi ✗→ miles_admin`；`miles_portal ✗→ miles_admin`；`miles_runner ✗→ core/portal/admin/openapi/ai`；`miles_core ✗→ ai`；`miles_server` 内无 views/schemas。
- **只声明真正 import 的依赖**（spec §5.1）。多声明一个包 = 白拆。
- **本计划是行为保持型重构**，因此不写"先失败的新单测"；每个任务的验证闸门是：既有 `pytest` + `ruff` + schema 逐字节比对（阶段 2 起加 `lint-imports`）。新增不变量（包分层、server 无 views）才新增真实测试代码。
- **单一提交原子性**：阶段 2 的搬迁必须一次提交完成（中途仓库不可 import），见 Task 2.2 顶部说明与 Task 2.4 Step 6。
- 提交信息遵循仓库规范：`<type>(<scope>): <简体中文简述>`。

## 验证闸门（每个任务复用）

```bash
# 一律显式用 venv 解释器（见 Global Constraints 的「解释器」条目）
PY=backend/.venv/bin/python          # 或 backend/.venv/bin/ruff
GATE_LINT='cd backend && .venv/bin/.venv/bin/ruff check . && .venv/bin/.venv/bin/ruff format --check .'
GATE_TEST='cd backend && .venv/bin/.venv/bin/python -m pytest -q'
GATE_OPENAPI='cd backend && .venv/bin/.venv/bin/python scripts/export_openapi.py --check'  # Task 3.1 后改为 .venv/bin/.venv/bin/python -m miles_server.scripts.export_openapi --check
GATE_LAYERS='cd backend && uv run lint-imports'                                  # Task 3.4 后可用
# schema 逐字节比对（比快照检查更强，迁移期间主闸门）：
# 迁移前先存档：cd backend && .venv/bin/.venv/bin/python scripts/export_openapi.py --write && cp openapi/openapi.snapshot.json ../.superpowers/sdd/openapi.ref.json
# 每任务后比对：cd backend && .venv/bin/python -c "import json,sys;from app.apps.application import create_app" ... 或直接 diff 生成结果
GATE_SCHEMA_REF='cd backend && .venv/bin/.venv/bin/python scripts/export_openapi.py --write && diff openapi/openapi.snapshot.json ../.superpowers/sdd/openapi.ref.json && echo SCHEMA_OK'
```

---

## Task 0.1: 基线快照与隔离分支

**执行者**：由主控（controller）直接执行，不派 subagent——本任务不产生代码改动，只记录基线。

**决策（已与用户确认）**：在主 checkout 直接开分支（不建 worktree）；跳过镜像体积基线与 compose 运行时冒烟，瘦身改用 `uv tree --package miles-runner` 断言。

- [ ] **Step 1: 建隔离分支**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI
git checkout -b refactor/backend-uv-workspace
git rev-parse --short HEAD        # 记为本分支 merge-base
```

- [ ] **Step 2: 记录绿色基线**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI/backend
.venv/bin/python -m pytest -q 2>&1 | tail -5
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/python scripts/export_openapi.py --check
.venv/bin/python -m pytest --collect-only -q 2>&1 | tail -3    # 记录测试用例数
sha256sum openapi/openapi.snapshot.json
```

Expected: 全部通过；把用例数、失败数（应为 0）、快照 sha256 记入下方"基线记录"。

- [ ] **Step 3: 确认分支状态**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI
git branch --show-current          # 应为 refactor/backend-uv-workspace
git status --short                 # 应为空
```

**基线记录（执行后填写）：**
- 测试用例数：____
- OpenAPI 快照 sha256：____
- **merge-base commit**：____
- runner 镜像体积：**跳过**（用户决策；改用 `uv tree --package miles-runner` 断言依赖闭包）

---

## Phase 1: 破环减重（单包内，包名不变）

> 目标：把 4 个真环在 `app/` 内部先解开（spec §3.2–§3.5）。此阶段**不动包名**，把逻辑风险与机械改名风险分开。

### Task 1.1: `session_store` 下沉 `miles_core`（修 `core → portal` 越界）

**Files:**
- Move: `backend/app/tenant/auth/services/session_store.py` → `backend/app/core/auth/session_store.py`
- Create: `backend/app/core/auth/__init__.py`
- Modify: `backend/app/core/deps.py:19,46,53`
- Modify: `backend/app/tenant/auth/services/__init__.py`（若 re-export）

**Interfaces:**
- Produces: `app.core.auth.session_store`（`register_session` / `touch_session` / `is_token_blacklisted` / `blacklist_token` / `list_sessions` / `revoke_session` / `revoke_all_sessions`）
- Consumes: `app.core.security.safe_decode_token`、`app.infra.redis.get_redis`、`app.utils.redis_keys.RedisKeys`

依据：`session_store` 只依赖 core/infra/utils，无租户业务逻辑（已核实），故可下沉。这是 spec §3 未列的 `core → portal` 越界，必须在包拆分前修掉。

- [ ] **Step 1: 建目录并搬文件**

```bash
cd backend
mkdir -p app/core/auth
git mv app/tenant/auth/services/session_store.py app/core/auth/session_store.py
printf '"""认证会话存储（Redis）：下沉自 tenant.auth，供 core.deps 与各域复用。"""\n' > app/core/auth/__init__.py
```

- [ ] **Step 2: 更新引用**

```bash
rg -rn "tenant\.auth\.services\.session_store|auth\.services import session_store|auth\.services\.session_store" app tests -g '*.py'
```

把 `app/core/deps.py` 的 `from app.tenant.auth.services import session_store` 改为 `from app.core.auth import session_store`；其余命中处（`app/tenant/auth/**`、`scripts/**`、`tests/**`）一并改为 `app.core.auth.session_store`（或 `from app.core.auth import session_store`）。

- [ ] **Step 3: 校验无残留**

```bash
rg -n "app\.tenant\.auth\.services\.session_store|auth\.services import session_store" app tests scripts -g '*.py' || echo "OK: 无残留"
```

Expected: `OK: 无残留`

- [ ] **Step 4: 跑闸门**

```bash
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/python -m pytest -q
.venv/bin/python scripts/export_openapi.py --check
```

Expected: 全绿、`OpenAPI snapshot OK`。

- [ ] **Step 5: 提交**

```bash
git add -A
git commit -F - <<'EOF'
refactor(core): session_store 下沉 core.auth

修复 core.deps 反向 import tenant.auth 的越界，为后续按包拆分
消除 core→portal 依赖。
EOF
```

---

### Task 1.2: `common` 瘦身为纯叶子 + `utils` 拆分 + 建立 `core/web`

**Files:**
- Move: `backend/app/common/pagination.py` → `backend/app/core/pagination.py`
- Move: `backend/app/common/url_security.py` → `backend/app/core/url_security.py`
- Move: `backend/app/utils/idgen.py` → `backend/app/common/idgen.py`
- Move: `backend/app/utils/redis_keys.py` → `backend/app/common/redis_keys.py`
- Move: `backend/app/utils/orm.py` → `backend/app/core/utils/orm.py`
- Move: `backend/app/utils/health_checks.py` → `backend/app/core/utils/health_checks.py`
- Move: `backend/app/common/handlers.py` → `backend/app/core/web/handlers.py`
- Create: `backend/app/core/web/__init__.py`、`backend/app/core/utils/__init__.py`

**Interfaces:**
- Produces: `app.core.pagination.paginate`、`app.core.url_security.*`、`app.common.idgen.*`、`app.common.redis_keys.RedisKeys`、`app.core.utils.orm.*`、`app.core.utils.health_checks.*`、`app.core.web.handlers.exception_handlers`
- Consumes: `app.core.soft_delete`、`app.core.config`、`app.core.logging`、`app.infra.*`

- [ ] **Step 1: 建目录**

```bash
cd backend
mkdir -p app/core/web app/core/utils
printf '"""通用 Web 管道：异常处理与 HTTP 中间件（跨域共用）。"""\n' > app/core/web/__init__.py
printf '"""core 侧工具：ORM 辅助与健康检查。"""\n' > app/core/utils/__init__.py
```

- [ ] **Step 2: 搬文件**

```bash
git mv app/common/pagination.py app/core/pagination.py
git mv app/common/url_security.py app/core/url_security.py
git mv app/utils/orm.py app/core/utils/orm.py
git mv app/utils/health_checks.py app/core/utils/health_checks.py
git mv app/common/handlers.py app/core/web/handlers.py
git mv app/utils/idgen.py app/common/idgen.py
git mv app/utils/redis_keys.py app/common/redis_keys.py
rmdir app/utils 2>/dev/null || true
```

- [ ] **Step 3: 全量改写引用**

```bash
rg -rn "app\.common\.(pagination|url_security|handlers)|app\.utils\.(idgen|redis_keys|orm|health_checks)" app tests scripts alembic -g '*.py'
```

逐条替换为：`app.common.pagination`→`app.core.pagination`；`app.common.url_security`→`app.core.url_security`；`app.common.handlers`→`app.core.web.handlers`；`app.utils.idgen`→`app.common.idgen`；`app.utils.redis_keys`→`app.common.redis_keys`；`app.utils.orm`→`app.core.utils.orm`；`app.utils.health_checks`→`app.core.utils.health_checks`。同时修正 `app/core/web/handlers.py` 内部 import 与 `tests/tenant/tools/test_url_security.py:9` 的 patch 字符串（`"app.common.url_security.get_settings"` → `"app.core.url_security.get_settings"`）。

- [ ] **Step 4: 确认 common 不再 import core**

```bash
rg -n "app\.(core|infra|integrations|rag|flow_runtime)" app/common -g '*.py' || echo "OK: common 已是叶子"
```

Expected: `OK: common 已是叶子`

- [ ] **Step 5: 跑闸门 + 提交**

```bash
.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/python -m pytest -q && .venv/bin/python scripts/export_openapi.py --check
git add -A
git commit -F - <<'EOF'
refactor(common): common 瘦身为纯叶子并拆分 utils

pagination/url_security/handlers 归 core 与 core.web，utils 按
纯函数与 ORM/infra 拆开，消除 common↔core 双向依赖。
EOF
```

---

### Task 1.3: 下沉 `core/web/middlewares` 与 `core/risk`（修 `portal → admin`）

**Files:**
- Move: `backend/app/middlewares/{__init__,trace,access_log,platform_risk}.py` → `backend/app/core/web/middlewares/`
- Move: `backend/app/admin/models/risk.py` → `backend/app/core/models/risk.py`
- Move: `backend/app/admin/app_ops/services/risk_enforce.py` → `backend/app/core/risk/enforce.py`
- Create: `backend/app/core/risk/__init__.py`
- Modify: `backend/app/admin/models/__init__.py`（re-export 保路径）
- Modify: `backend/app/admin/app_ops/services/risk.py`（改为从 core 引用）

依据：`PlatformRiskMiddleware` 属全局管道且**对 `/api/v1`（portal）限流**；其 ORM/服务在 admin 会造成 `portal → admin`（spec §3.5）。

- [ ] **Step 1: 搬中间件**

```bash
cd backend
mkdir -p app/core/web/middlewares
for f in __init__.py trace.py access_log.py platform_risk.py; do git mv app/middlewares/$f app/core/web/middlewares/$f; done
rmdir app/middlewares 2>/dev/null || true
sed -i '' 's/from app\.admin\.app_ops\.services\.risk_enforce import platform_risk_enforcer/from app.core.risk.enforce import platform_risk_enforcer/; s/from app\.admin\.models import RiskSeverity/from app.core.models.risk import RiskSeverity/' app/core/web/middlewares/platform_risk.py
sed -i '' 's/from app\.middlewares\.\(access_log\|platform_risk\|trace\)/from app.core.web.middlewares.\1/' app/core/web/middlewares/__init__.py
```

- [ ] **Step 2: 搬风控 ORM 与服务**

```bash
mkdir -p app/core/risk
git mv app/admin/models/risk.py app/core/models/risk.py
git mv app/admin/app_ops/services/risk_enforce.py app/core/risk/enforce.py
printf '"""平台风控能力（IP 黑名单 / 限流规则 / 风险事件）；下沉自 admin，供全局中间件与运营面共用。"""\n' > app/core/risk/__init__.py
```

- [ ] **Step 3: 修正内部 import 与新表名无关性**

`core/models/risk.py` 内 `from app.infra.db import Base` / `from app.models.base import ...` 保持不变（同包内路径未变，Phase 2 才改名）。
`core/risk/enforce.py` 内：
- `from app.admin.models import IpBlacklist, RateLimitRule, RiskEvent, RiskSeverity` → `from app.core.models.risk import IpBlacklist, RateLimitRule, RiskEvent, RiskSeverity`

**表名必须保持** `adm_risk_events` / `adm_ip_blacklist` / `adm_rate_limit_rules`（不要改）。

- [ ] **Step 4: admin 侧留 re-export 薄壳**

`app/admin/models/__init__.py`：

```python
"""运营后台 ORM（与 app_sys / app_ops 平级）。"""

from app.admin.models.audit import AuditLog
from app.admin.models.billing import BillLineItem, BillStatus, BillingPlan, TenantBill
from app.admin.models.sys import PlatformAdmin
# 风控 ORM 已下沉中立域，此处 re-export 保持 admin 域既有引用路径稳定
from app.core.models.risk import IpBlacklist, RateLimitRule, RiskEvent, RiskSeverity  # noqa: F401

__all__ = [
    "PlatformAdmin",
    "BillingPlan",
    "BillStatus",
    "TenantBill",
    "BillLineItem",
    "AuditLog",
    "RiskSeverity",
    "RiskEvent",
    "IpBlacklist",
    "RateLimitRule",
]
```

`app/admin/app_ops/services/risk_enforce.py` 已移走，`app/admin/app_ops/services/risk.py` 改为：

```python
from app.core.risk.enforce import platform_risk_enforcer
```

- [ ] **Step 5: 全量改写引用**

```bash
rg -rn "app\.middlewares|app\.admin\.models\.risk|app\.admin\.app_ops\.services\.risk_enforce" app tests scripts -g '*.py'
```

替换：`app.middlewares.*`→`app.core.web.middlewares.*`；`app.admin.models.risk`→`app.core.models.risk`；`app.admin.app_ops.services.risk_enforce`→`app.core.risk.enforce`。
`tests/conftest.py:36,41` 的 patch 目标字符串 `"app.middlewares.platform_risk.platform_risk_enforcer.*"` → `"app.core.web.middlewares.platform_risk.platform_risk_enforcer.*"`。

- [ ] **Step 6: 跑闸门（含风控回归）**

```bash
rg -n "app\.middlewares\b" app tests -g '*.py' || echo "OK: 无残留"
.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/python -m pytest -q && .venv/bin/python scripts/export_openapi.py --check
.venv/bin/python -m pytest tests/api -q
```

Expected: 全绿；`tests/api` 通过（覆盖 403/429 信封）。

- [ ] **Step 7: 提交**

```bash
git add -A
git commit -F - <<'EOF'
refactor(core): 风控与通用 Web 管道下沉 core

平台风控 ORM、risk_enforce 与 HTTP 中间件迁至 core，admin 侧保留
re-export；消除 portal 请求管道对 admin 的依赖。表名保持不变。
EOF
```

---

### Task 1.4: 抽 `app/exec/`（沙箱与 MCP 协议内核）

**Files:**
- Move: `backend/app/tenant/mcp/runner/spec.py` → `backend/app/exec/mcp/spec.py`
- Move: `backend/app/tenant/mcp/constants.py` → `backend/app/exec/mcp/constants.py`
- Move: `backend/app/tenant/mcp/rpc.py` → `backend/app/exec/mcp/rpc.py`
- Create: `backend/app/exec/mcp/tools.py`（从 `tenant/mcp/client.py` 取 `_normalize_tools`）
- Move: `backend/app/tenant/tools/script_validate.py` → `backend/app/exec/sandbox/validate.py`
- Move: `backend/app/runner/session.py` → `backend/app/exec/sandbox/session.py`
- Move: `backend/app/runner/script_exec.py` → `backend/app/exec/sandbox/script_exec.py`
- Create: `backend/app/exec/__init__.py`、`backend/app/exec/mcp/__init__.py`、`backend/app/exec/sandbox/__init__.py`

**Interfaces:**
- Produces: `app.exec.mcp.spec.RunSpec` / `validate_run_spec`；`app.exec.mcp.constants.MCP_PROTOCOL_VERSION`；`app.exec.mcp.rpc.parse_jsonrpc_result` / `normalize_tool_call_result`；`app.exec.mcp.tools.normalize_tools`；`app.exec.sandbox.validate.validate_script_source`；`app.exec.sandbox.session.{SessionResult,run_mcp_session}`；`app.exec.sandbox.script_exec.run_python_script`
- Consumes: `app.common.exceptions.BadRequestError`（仅此）

- [ ] **Step 1: 建目录并搬文件**

```bash
cd backend
mkdir -p app/exec/mcp app/exec/sandbox
printf '"""沙箱执行与 MCP 协议内核（叶子模块，零重依赖）。"""\n' > app/exec/__init__.py
printf '"""MCP 协议：常量、JSON-RPC 与 RunSpec 校验。"""\n' > app/exec/mcp/__init__.py
printf '"""沙箱：源码校验与受限子进程执行。"""\n' > app/exec/sandbox/__init__.py
git mv app/tenant/mcp/runner/spec.py app/exec/mcp/spec.py
git mv app/tenant/mcp/constants.py app/exec/mcp/constants.py
git mv app/tenant/mcp/rpc.py app/exec/mcp/rpc.py
git mv app/tenant/tools/script_validate.py app/exec/sandbox/validate.py
git mv app/runner/session.py app/exec/sandbox/session.py
git mv app/runner/script_exec.py app/exec/sandbox/script_exec.py
```

- [ ] **Step 2: 抽 `normalize_tools`（必须逐行等价搬运，禁止重写）**

```bash
rg -n "_normalize_tools" app/tenant/mcp/client.py app/runner/main.py
```

在 `app/exec/mcp/tools.py` 写入模块头，然后把 `app/tenant/mcp/client.py` 中 `_normalize_tools` 的**函数实现整段**（含 docstring）**原样**搬入并重命名为 `normalize_tools`：

```python
"""MCP 工具列表归一化（下沉自 tenant.mcp.client，供 Runner 复用）。"""

from __future__ import annotations

# ← 此处粘贴 client.py 中 _normalize_tools 的原始实现（docstring 与全部
#   分支：list / dict["tools"] / item.name-or-id-or-"tool" / description-or-summary /
#   inputSchema-or-input_schema / annotations / 字符串项），仅把函数名
#   _normalize_tools 改为 normalize_tools。禁止简化分支或改默认值。
```

> 该函数现有 4 类输入形状与 2 类 item 形态（dict / str），是**行为契约**；任何简化（如去掉 `id`/`summary` 回退、去掉字符串分支、忽略 `annotations`）都会造成静默回归。

然后：
- `app/tenant/mcp/client.py`：删除本地 `_normalize_tools` 定义，顶部改 `from app.exec.mcp.tools import normalize_tools`，并把 3 处调用点（约 225/229/241 行）改名。
- `app/runner/main.py`：改 import `normalize_tools`，调用点 `_normalize_tools(...)` 改名。

- [ ] **Step 3: 修正被搬文件的内部 import**

```bash
sed -i '' 's/from app\.runner\.session import/from app.exec.sandbox.session import/' app/exec/sandbox/script_exec.py
sed -i '' 's/from app\.tenant\.tools\.script_validate import/from app.exec.sandbox.validate import/' app/exec/sandbox/script_exec.py
sed -i '' 's/from app\.tenant\.mcp\.runner\.spec import/from app.exec.mcp.spec import/' app/exec/sandbox/session.py
sed -i '' 's/from app\.tenant\.mcp\.\(constants\|rpc\) import/from app.exec.mcp.\1 import/' app/runner/mcp_stdio.py
```

- [ ] **Step 4: 全量改写引用**

```bash
rg -rn "app\.tenant\.mcp\.(runner\.spec|constants|rpc|client)|app\.tenant\.tools\.script_validate|app\.runner\.(session|script_exec)" app tests -g '*.py'
```

替换：`app.tenant.mcp.runner.spec`→`app.exec.mcp.spec`；`app.tenant.mcp.constants`→`app.exec.mcp.constants`；`app.tenant.mcp.rpc`→`app.exec.mcp.rpc`；`app.tenant.mcp.client._normalize_tools`→`app.exec.mcp.tools.normalize_tools`；`app.tenant.tools.script_validate`→`app.exec.sandbox.validate`；`app.runner.session`→`app.exec.sandbox.session`；`app.runner.script_exec`→`app.exec.sandbox.script_exec`。

- [ ] **Step 5: 校验 exec 无重依赖**

```bash
rg -n "^from app\.|^import app\." app/exec -g '*.py'
```

Expected: 只出现 `app.common.*`（无 core/infra/tenant/rag）。

- [ ] **Step 6: 跑闸门（沙箱 + MCP 专项）**

```bash
.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/python -m pytest -q
.venv/bin/python -m pytest tests/mcp tests/tenant/tools -q
```

- [ ] **Step 7: 提交**

```bash
git add -A
git commit -F - <<'EOF'
refactor(exec): 抽出沙箱与 MCP 协议内核

MCP RunSpec/常量/JSON-RPC、脚本校验与子进程执行内核归入 app.exec，
消除 tenant↔runner 双向依赖，为 runner 镜像瘦身做准备。
EOF
```

---

### Task 1.5: `celery_app` 下沉 + 任务名收敛（修 `portal ↔ worker`）

**Files:**
- Create: `backend/app/core/jobs/__init__.py`、`backend/app/core/jobs/celery_app.py`、`backend/app/core/jobs/tasks.py`
- Modify: `backend/app/workers/app.py`（改为在最小 app 上补 `include`/路由/beat）
- Modify: `backend/app/tenant/generative/services/job.py`、`backend/app/tenant/tasks/services/task.py`
- Modify: `backend/app/tenant/kb/services/kb/documents.py`、`backend/app/tenant/media_assets/services/media_asset.py`

**Interfaces:**
- Produces: `app.core.jobs.celery_app.celery_app`（最小配置）；`app.core.jobs.tasks.TASK_NAMES`（`ingest_document` / `run_generative_video_job` / `run_generative_image_job` / `probe_models_health` / `run_agent_schedule` / `tick_agent_schedules`）
- Consumes: `app.core.config.get_settings`

- [ ] **Step 1: 写最小 celery_app**

`app/core/jobs/__init__.py`：

```python
"""Celery 运行时：最小 app（中立）与任务名常量。"""
```

`app/core/jobs/celery_app.py`：

```python
"""最小 Celery 应用：仅供业务侧按任务名投递，不含任务注册与调度。

任务注册（include）、队列路由、beat 调度由 worker 启动模块补齐，
以使 L1 业务代码投递任务时无需依赖 worker 包。
"""

from celery import Celery

from app.core.config import get_settings

_settings = get_settings()

celery_app = Celery(
    "milesai",
    broker=_settings.celery_broker_url,
    backend=_settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_queue="default",
    task_soft_time_limit=_settings.celery_task_soft_time_limit_sec,
    task_time_limit=_settings.celery_task_time_limit_sec,
)
```

`app/core/jobs/tasks.py`：

```python
"""Celery 任务名常量：投递方与注册方共用的唯一来源。"""

from __future__ import annotations

TASK_NAMES = {
    "ingest_document": "app.workers.tasks.ingest.ingest_document",
    "run_generative_video_job": "app.workers.tasks.generative.run_generative_video_job",
    "run_generative_image_job": "app.workers.tasks.generative.run_generative_image_job",
    "probe_models_health": "app.workers.tasks.model_health.probe_models_health",
    "run_agent_schedule": "app.workers.tasks.agent_schedule.run_agent_schedule",
    "tick_agent_schedules": "app.workers.tasks.agent_schedule.tick_agent_schedules",
}

INGEST_DOCUMENT = TASK_NAMES["ingest_document"]
RUN_GENERATIVE_VIDEO_JOB = TASK_NAMES["run_generative_video_job"]
RUN_GENERATIVE_IMAGE_JOB = TASK_NAMES["run_generative_image_job"]
```

> 任务名**保持现有字面量不变**（`app.workers.tasks.*`），因为装饰器 `name=` 已显式写死这些字符串；改字面量会牵动 `task_annotations`/`task_routes`/`beat_schedule` 与在途消息。阶段 2 的 codemod 会一致地重写字符串，届时统一变为 `miles_worker.tasks.*`。

- [ ] **Step 2: worker 启动模块补齐注册**

`app/workers/app.py` 改为：

```python
"""Celery Worker/Beat 启动模块：在最小 app 上补齐任务注册、队列路由与调度。

任务名见 app.core.jobs.tasks.TASK_NAMES。启动示例：
  celery -A app.workers.app worker -Q parse,default
"""

from app.core.config import get_settings
from app.core.jobs.celery_app import celery_app
from app.core.jobs.tasks import TASK_NAMES
from app.core.logging import setup_logging

setup_logging()
settings = get_settings()

celery_app.conf.update(
    include=["app.workers.tasks"],
    task_annotations={
        TASK_NAMES["ingest_document"]: {
            "soft_time_limit": settings.celery_ingest_soft_time_limit_sec,
            "time_limit": settings.celery_ingest_time_limit_sec,
        },
        TASK_NAMES["run_generative_video_job"]: {
            "soft_time_limit": settings.celery_generative_soft_time_limit_sec,
            "time_limit": settings.celery_generative_time_limit_sec,
        },
        TASK_NAMES["run_generative_image_job"]: {
            "soft_time_limit": settings.celery_generative_soft_time_limit_sec,
            "time_limit": settings.celery_generative_time_limit_sec,
        },
    },
    task_routes={
        "app.workers.tasks.ingest.*": {"queue": "parse"},
        "app.workers.tasks.ocr.*": {"queue": "ocr"},
        "app.workers.tasks.embed.*": {"queue": "embed"},
    },
    beat_schedule={
        "tick-agent-schedules": {"task": TASK_NAMES["tick_agent_schedules"], "schedule": 60.0},
        "probe-models-health": {"task": TASK_NAMES["probe_models_health"], "schedule": 900.0},
    },
)

__all__ = ["celery_app"]
```

- [ ] **Step 3: 业务侧改按任务名投递**

`app/tenant/generative/services/job.py`：

```python
from app.core.jobs.celery_app import celery_app
from app.core.jobs.tasks import RUN_GENERATIVE_IMAGE_JOB, RUN_GENERATIVE_VIDEO_JOB
```

把 `from app.workers.app import celery_app` 删掉；把 `run_generative_video_job.delay(...)` 之类改为：

```python
celery_app.send_task(RUN_GENERATIVE_VIDEO_JOB, args=[...])   # 参数与原 delay 调用一致
```

`app/tenant/tasks/services/task.py`、`app/tenant/kb/services/kb/documents.py`、`app/tenant/media_assets/services/media_asset.py`：

```python
from app.core.jobs.celery_app import celery_app
from app.core.jobs.tasks import INGEST_DOCUMENT
# 原 `from app.workers.tasks.ingest import ingest_document` + `.delay(...)`
celery_app.send_task(INGEST_DOCUMENT, args=[...])
```

> 参数列表必须与改动前 `.delay(...)` / `.apply_async(...)` 的实参逐一对齐（逐个调用点核对，勿改语义）。

- [ ] **Step 4: 校验 portal 不再 import worker**

```bash
rg -n "app\.workers" app/tenant app/deletion app/marketplace app/admin -g '*.py' || echo "OK: 业务侧零 worker 依赖"
```

Expected: `OK: 业务侧零 worker 依赖`

- [ ] **Step 5: 跑闸门（celery 配置 + 全量）**

```bash
.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/python -m pytest -q
.venv/bin/python -m pytest tests/infra/test_celery_config.py tests/tenant/generative tests/tenant/kb tests/tenant/tasks -q
```

- [ ] **Step 6: 提交**

```bash
git add -A
git commit -F - <<'EOF'
refactor(jobs): celery 最小 app 下沉 core 并按任务名投递

业务侧改为 send_task(任务名)，注册与调度留在 worker 启动模块，
消除 portal↔worker 双向依赖。
EOF
```

---

## Phase 2: 工作区与搬迁

### Task 2.1: 建立 uv workspace 骨架与 10 个包声明

**Files:**
- Modify: `backend/pyproject.toml`（改为 workspace 根）
- Create: `backend/packages/miles-<x>/pyproject.toml` × 10
- Create: `backend/packages/miles-<x>/src/miles_<x>/__init__.py` × 10

- [ ] **Step 1: 备份原 pyproject**

```bash
cd backend
cp pyproject.toml pyproject.toml.bak
```

- [ ] **Step 2: 写 workspace 根 pyproject**

`backend/pyproject.toml`：

```toml
[project]
name = "milesai-workspace"
version = "0.1.0"
description = "一体化AI智能编排与RAG应用平台（多包工作区根）"
requires-python = ">=3.11"

[tool.uv.workspace]
members = ["packages/*"]

[dependency-groups]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "ruff==0.15.13",
    "import-linter>=2.0",
]

[tool.ruff]
line-length = 160
target-version = "py311"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 3: 写 10 个成员 pyproject**

模板（以 portal 为例，其余按 spec §2 的依赖表替换 `dependencies`）：

`backend/packages/miles-portal/pyproject.toml`：

```toml
[project]
name = "miles-portal"
version = "0.1.0"
description = "租户 AI 平台域（/api/v1）"
requires-python = ">=3.11"
dependencies = [
    "miles-ai",
    "miles-core",
    "miles-common",
    "miles-exec",
    "fastapi>=0.115.0",
    "pydantic>=2.10.0",
    "sqlalchemy[asyncio]>=2.0.36",
    "celery>=5.4.0",
    "httpx>=0.28.0",
    # … 其余按需（仅列真正 import 到的第三方）
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/miles_portal"]

[tool.uv.sources]
miles-ai = { workspace = true }
miles-core = { workspace = true }
miles-common = { workspace = true }
miles-exec = { workspace = true }
```

各包名 / 目录 / `dependencies`（本地包部分）：

| 包目录 | name | workspace 本地依赖 |
|--------|------|-------------------|
| `miles-common` | `miles-common` | — |
| `miles-exec` | `miles-exec` | `miles-common` |
| `miles-core` | `miles-core` | `miles-common` |
| `miles-ai` | `miles-ai` | `miles-core`, `miles-common` |
| `miles-portal` | `miles-portal` | `miles-ai`, `miles-core`, `miles-common`, `miles-exec` |
| `miles-admin` | `miles-admin` | `miles-portal`, `miles-core`, `miles-common` |
| `miles-openapi` | `miles-openapi` | `miles-portal`, `miles-ai`, `miles-core`, `miles-common` |
| `miles-server` | `miles-server` | `miles-openapi`, `miles-portal`, `miles-admin`, `miles-ai`, `miles-core`, `miles-common` |
| `miles-worker` | `miles-worker` | `miles-portal`, `miles-ai`, `miles-core`, `miles-common` |
| `miles-runner` | `miles-runner` | `miles-exec`, `miles-common` |

第三方依赖从原 `backend/pyproject.toml` 的 `dependencies` / `optional-dependencies` 里**按实际 import 分配**。原文件 extras 共 5 个，落点必须全部覆盖（漏一个 = 该域可选能力装不上）：

| 原 extra | 落点包 | 内容 |
|----------|--------|------|
| `agent-stack` | `miles-ai` | `langchain-openai` / `langchain-community` / `deepagents`（integrations/deepagents 用） |
| `parse-docling` | `miles-ai` | `docling`（rag/parse/loaders 用） |
| `multimodal` | `miles-ai` | `pytesseract` / `openai-whisper`（rag 解析与 OCR/ASR 用） |
| `otel` | `miles-server` | `opentelemetry-*`（`miles_core.infra.otel` 由 lifespan 调用，故由装配包声明） |
| `dev` | workspace 根 `[dependency-groups]` | `pytest` / `pytest-asyncio` / `ruff==0.15.13` / `import-linter` |

- [ ] **Step 4: 建包目录与占位 `__init__.py`**

```bash
for p in common exec core ai portal admin openapi server worker runner; do
  mkdir -p packages/miles-$p/src/miles_${p}
  printf '"""miles-%s 包（迁移中）。"""\n' "$p" > packages/miles-$p/src/miles_${p}/__init__.py
done
```

- [ ] **Step 5: 校验工作区可解析（此时旧 app/ 仍在）**

```bash
uv lock 2>&1 | tail -5
uv sync --all-packages --group dev 2>&1 | tail -5
.venv/bin/python -c "import miles_common, miles_core, miles_ai, miles_portal, miles_admin, miles_openapi, miles_server, miles_worker, miles_runner, miles_exec; print('workspace OK')"
```

Expected: `workspace OK`

- [ ] **Step 6: 提交**

```bash
git add -A
git commit -F - <<'EOF'
build(backend): 建立 uv workspace 骨架与 10 个包声明

根 pyproject 改为 workspace，成员包各自声明依赖与 workspace 源；
旧 app/ 暂未搬迁，后续任务统一迁移。
EOF
```

---

### Task 2.2: 物理搬迁（`git mv app/* → packages/*/src/*`）

**Files:**
- Move: 见 Step 2 命令

> 本任务与 Task 2.3/2.4 必须**连续完成并一次提交**（中途仓库不可 import）。提交在 Task 2.4 Step 6。

**搬迁规则（务必区分两类，这是本任务最容易出错的地方）：**
- **剥离包装层**（新路径 = `miles_<pkg>/`，原目录内容直接成为包内容）：`common`、`exec`、`core`、`admin`、`workers`、`runner`。
- **保留包装层**（新路径 = `miles_<pkg>/<原目录名>/`）：`infra`、`models`、`rag`、`integrations`、`flow_runtime`、`tenant`、`deletion`、`marketplace`、`apps`、`scripts`。

- [ ] **Step 1: 先删占位 `__init__.py`（避免 flatten 时与搬来的 `__init__.py` 冲突）**

```bash
cd backend
for p in common exec core admin workers runner; do rm -f packages/miles-$p/src/miles_${p}/__init__.py; done
```

- [ ] **Step 2: 搬迁（保留 rename 历史）**

```bash
P=packages
# ── 剥离包装层（下一步 flatten）──
git mv app/common        $P/miles-common/src/miles_common/common
git mv app/exec          $P/miles-exec/src/miles_exec/exec
git mv app/core          $P/miles-core/src/miles_core/core
git mv app/admin         $P/miles-admin/src/miles_admin/admin
git mv app/workers       $P/miles-worker/src/miles_worker/workers
git mv app/runner        $P/miles-runner/src/miles_runner/runner
# ── 保留包装层（目录名即子包名）──
git mv app/infra         $P/miles-core/src/miles_core/infra
git mv app/models        $P/miles-core/src/miles_core/models
git mv app/rag           $P/miles-ai/src/miles_ai/rag
git mv app/integrations  $P/miles-ai/src/miles_ai/integrations
git mv app/flow_runtime  $P/miles-ai/src/miles_ai/flow_runtime
git mv app/tenant        $P/miles-portal/src/miles_portal/tenant
git mv app/deletion      $P/miles-portal/src/miles_portal/deletion
git mv app/marketplace   $P/miles-portal/src/miles_portal/marketplace
git mv app/apps          $P/miles-server/src/miles_server/apps
git mv app/main.py       $P/miles-server/src/miles_server/main.py
git mv cli.py            $P/miles-server/src/miles_server/cli.py
git mv scripts           $P/miles-server/src/miles_server/scripts
# ── 开放面：本步即迁入 miles_openapi，保证 Task 2.3 的 codemod 目标路径已存在 ──
mkdir -p $P/miles-openapi/src/miles_openapi/views
git mv app/tenant/agents/views/open_chat.py $P/miles-openapi/src/miles_openapi/views/open_chat.py
git mv app/tenant/agents/deps_api_auth.py   $P/miles-openapi/src/miles_openapi/deps_api_auth.py
```

- [ ] **Step 3: 剥离包装层**

```bash
flatten() { local pkg=$1 inner=$2; mv "$pkg/$inner"/* "$pkg/" && rmdir "$pkg/$inner"; }
for spec in common:common exec:exec core:core admin:admin workers:workers runner:runner; do
  p=${spec%%:*}; i=${spec##*:}
  flatten "$P/miles-$p/src/miles_${p}" "$i"
done
```

- [ ] **Step 4: 移除空壳与残留**

```bash
rm -rf app
rm -f pyproject.toml.bak
rm -rf milesai.egg-info
find packages -name __pycache__ -type d -prune -exec rm -rf {} +
```

- [ ] **Step 5: 校验目录形态**

```bash
ls packages
ls packages/miles-core/src/miles_core          # 期望：config.py deps.py security.py models/ infra/ web/ risk/ jobs/
ls packages/miles-ai/src/miles_ai              # 期望：rag/ integrations/ flow_runtime/
ls packages/miles-portal/src/miles_portal      # 期望：tenant/ deletion/ marketplace/
ls packages/miles-admin/src/miles_admin        # 期望：router.py models/ app_ops/ app_sys/（已剥离 admin 层）
ls packages/miles-worker/src/miles_worker      # 期望：app.py tasks/
ls packages/miles-runner/src/miles_runner      # 期望：main.py limits.py（已剥离 runner 层）
ls packages/miles-openapi/src/miles_openapi    # 期望：views/open_chat.py deps_api_auth.py
ls packages/miles-server/src/miles_server      # 期望：main.py cli.py apps/ scripts/
```

Expected: 全部命中；`miles_admin/admin/` 与 `miles_core/core/` 之类的多余层级**不应存在**。

---

### Task 2.3: 全量 import codemod

**Files:**
- Create: `backend/tools/rename_to_workspace.py`

- [ ] **Step 1: 写 codemod 脚本**

`backend/tools/rename_to_workspace.py`：

```python
#!/usr/bin/env python3
"""一次性 codemod：把 app.* 引用改写为 miles_* 包路径。

同时改写 import 语句与字符串字面量中的点分模块路径
（如 patch 目标、celery 任务名、include 列表）。

用法：
  cd backend
  .venv/bin/python tools/rename_to_workspace.py --dry-run
  .venv/bin/python tools/rename_to_workspace.py --apply
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]

# 旧前缀 → 新前缀；按长度降序生效（最长优先，避免被短前缀截断）。
RULES: list[tuple[str, str]] = [
    ("app.tenant.agents.views.open_chat", "miles_openapi.views.open_chat"),
    ("app.tenant.agents.deps_api_auth", "miles_openapi.deps_api_auth"),
    ("app.tenant.mcp.runner.spec", "miles_exec.mcp.spec"),
    ("app.tenant.mcp.constants", "miles_exec.mcp.constants"),
    ("app.tenant.mcp.rpc", "miles_exec.mcp.rpc"),
    ("app.tenant.tools.script_validate", "miles_exec.sandbox.validate"),
    ("app.admin.app_ops.services.risk_enforce", "miles_core.risk.enforce"),
    ("app.admin.models.risk", "miles_core.models.risk"),
    ("app.common.pagination", "miles_core.pagination"),
    ("app.common.url_security", "miles_core.url_security"),
    ("app.common.handlers", "miles_core.web.handlers"),
    ("app.utils.redis_keys", "miles_common.redis_keys"),
    ("app.utils.health_checks", "miles_core.utils.health_checks"),
    ("app.utils.idgen", "miles_common.idgen"),
    ("app.utils.orm", "miles_core.utils.orm"),
    ("app.workers.app", "miles_core.jobs.celery_app"),
    ("app.runner.script_exec", "miles_exec.sandbox.script_exec"),
    ("app.runner.session", "miles_exec.sandbox.session"),
    ("app.runner.limits", "miles_runner.limits"),
    ("app.runner.main", "miles_runner.main"),
    ("app.flow_runtime", "miles_ai.flow_runtime"),
    ("app.integrations", "miles_ai.integrations"),
    ("app.middlewares", "miles_core.web.middlewares"),
    ("app.marketplace", "miles_portal.marketplace"),
    ("app.deletion", "miles_portal.deletion"),
    ("app.infra", "miles_core.infra"),
    ("app.models", "miles_core.models"),
    ("app.tenant", "miles_portal.tenant"),
    ("app.admin", "miles_admin"),
    ("app.common", "miles_common"),
    ("app.core", "miles_core"),
    ("app.exec", "miles_exec"),
    ("app.rag", "miles_ai.rag"),
    ("app.apps", "miles_server.apps"),
    ("app.main", "miles_server.main"),
    ("app.workers", "miles_worker"),
    ("app.utils", "miles_core.utils"),
]

_RULES = sorted(RULES, key=lambda r: len(r[0]), reverse=True)
_MAP = dict(_RULES)
_ALT = "|".join(re.escape(old) for old, _ in _RULES)
# 模块路径前缀：前一字符不是标识符/点，后一字符不是标识符（避免 app.tenantx / xapp.tenant）
_RE = re.compile(rf"(?<![\w.]){_ALT}(?![\w])")

# 说明：
# 1) 规则按长度降序匹配，故 `app.workers.app` 先于 `app.workers` 命中，前者映射到
#    miles_core.jobs.celery_app（投资方），后者映射到 miles_worker（任务实现包）。
# 2) `app.tenant.mcp.client` 无需规则：Task 1.4 后已无引用（normalize_tools 改由
#    app.exec.mcp.tools 提供），若预演输出中出现该前缀即为遗漏，需回到 Task 1.4 修。
# 3) 同一 regex 同时作用于 import 语句与字符串字面量（patch 目标、celery 任务名、
#    include 列表），因此任务名会一致地变为 miles_worker.tasks.*。

SKIP_PARTS = {".venv", "__pycache__", "milesai.egg-info", ".ruff_cache", ".pytest_cache", "node_modules"}


def rewrite(text: str) -> str:
    """改写文本中的 app.* 模块路径（含字符串字面量）。"""
    return _RE.sub(lambda m: _MAP[m.group(0)], text)


# `scripts` 是 backend 根级包（无 app. 前缀），codemod 的 app.* 规则覆盖不到；
# 但它有 43 处 `from scripts.x import` 根引用（cli.py / scripts 内部 / tests）。
# 用「仅匹配 import 语句」的定向正则，避免误伤普通字符串里的 "scripts.xxx"。
_RE_SCRIPTS = re.compile(r"(?<![\w.])(from|import)([ \t]+)scripts(?=[.\s])")


def rewrite_scripts_imports(text: str) -> str:
    """把 ``from scripts.x import`` / ``import scripts`` 改为 ``miles_server.scripts.*``。"""
    return _RE_SCRIPTS.sub(lambda m: f"{m.group(1)}{m.group(2)}miles_server.scripts", text)


def iter_files() -> list[Path]:
    """待改写文件：backend 下全部 .py（含 tests/scripts/alembic/tools）。"""
    out: list[Path] = []
    for p in sorted(BACKEND.rglob("*.py")):
        if any(part in SKIP_PARTS for part in p.parts):
            continue
        out.append(p)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if not (args.apply or args.dry_run):
        ap.error("需要 --dry-run 或 --apply")

    changed = 0
    for path in iter_files():
        src = path.read_text(encoding="utf-8")
        new = rewrite_scripts_imports(rewrite(src))
        if new != src:
            changed += 1
            rel = path.relative_to(BACKEND)
            if args.apply:
                path.write_text(new, encoding="utf-8")
            print(f"{'改写' if args.apply else '将改写'} {rel}")
    print(f"\n共 {changed} 个文件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: 预演并人工扫读**

```bash
cd backend
.venv/bin/python tools/rename_to_workspace.py --dry-run
```

Expected: 列出全部含 `app.*` 的文件（预期 ≈700 个）。

- [ ] **Step 3: 应用**

```bash
.venv/bin/python tools/rename_to_workspace.py --apply
git diff --stat | tail -3
```

- [ ] **Step 4: 校验无残留**

```bash
rg -n "(?<![\w.])app\.(tenant|admin|core|infra|models|rag|integrations|flow_runtime|common|utils|apps|middlewares|workers|runner|deletion|marketplace|exec|main)\b" \
  --glob '!**/.venv/**' --glob '!**/__pycache__/**' --glob '!**/tools/rename_to_workspace.py' \
  packages tests scripts alembic . 2>/dev/null | head -20 || echo "OK: app.* 无残留"

# scripts 根引用（codemod 的第二趟）
rg -n "(?<![\w.])(from|import)[ \t]+scripts(?=[.\s])" packages tests alembic -g '*.py' | head -20 \
  || echo "OK: scripts.* 无残留"
rg -c "miles_server\.scripts" packages/miles-server/src/miles_server/cli.py
```

Expected: 两条均 `OK`；`cli.py` 内 `miles_server.scripts` 计数 ≥ 6。若 scripts 命中里出现 `tests/`，也一并改为 `miles_server.scripts.*`。

- [ ] **Step 5: 校验包可编译**

```bash
.venv/bin/python -m compileall -q packages && echo "compile OK"
```

---

### Task 2.4: 特殊引用与路径假设修正

**Files:**
- Move: `packages/miles-core/src/miles_core/models/registry.py` → `packages/miles-server/src/miles_server/registry.py`
- Modify: `packages/miles-server/src/miles_server/apps/migrate.py`、`.../scripts/export_openapi.py`、`.../cli.py`
- Modify: `alembic/env.py`、`alembic/versions/001_initial_schema.py`
- Modify: `tests/paths.py` 及引用模板/脚本路径的测试
- Modify: `tests/conftest.py`（patch 目标字符串）

- [ ] **Step 1: 迁移 app-wide ORM registry（关键）**

`load_all_models()` 会 import `miles_admin.admin.models` 与 `miles_portal.tenant.*.models`；若留在 `miles_core`，将造成 `miles_core → miles_admin/miles_portal` 反向依赖。

```bash
git mv packages/miles-core/src/miles_core/models/registry.py packages/miles-server/src/miles_server/registry.py
```

把 `packages/miles-server/src/miles_server/registry.py` 内 import 全部改为新路径（codemod 已处理其中的 `app.*`，但还要把 `miles_core.models.*` 的引用保持、并新增 admin/portal 域）：

```python
"""登记全部 ORM 模块，供 Alembic 与启动时加载 metadata。

位于装配层（miles_server）：需汇总各域 ORM，不得下沉到 miles_core。
"""


def load_all_models() -> None:
    """按依赖顺序导入各域 models，避免在 models/__init__ 中循环引用。"""
    import miles_core.models.platform  # noqa: F401
    import miles_core.models.kb  # noqa: F401
    import miles_core.models.flow  # noqa: F401
    import miles_core.models.model  # noqa: F401
    import miles_core.models.media  # noqa: F401
    import miles_core.models.meta  # noqa: F401
    import miles_core.models.task  # noqa: F401
    import miles_core.models.storage  # noqa: F401
    import miles_core.models.agent  # noqa: F401
    import miles_core.models.marketplace  # noqa: F401
    import miles_core.models  # noqa: F401
    import miles_admin.admin.models  # noqa: F401
    import miles_portal.tenant.compliance.models  # noqa: F401
    import miles_portal.tenant.hooks.models  # noqa: F401
    import miles_portal.tenant.prompts.models  # noqa: F401
    import miles_portal.tenant.skills.models  # noqa: F401
    import miles_portal.tenant.mcp.models  # noqa: F401
    import miles_portal.tenant.a2a.models  # noqa: F401
    import miles_portal.tenant.tools.models  # noqa: F401
    import miles_portal.tenant.audit_log.models  # noqa: F401
```

`alembic/env.py`：`from app.models.registry import load_all_models` → `from miles_server.registry import load_all_models`；`from app.core.config import get_settings` → `from miles_core.config import get_settings`；`from app.infra.db import Base` → `from miles_core.infra.db import Base`（codemod 已改，核对即可）。
`alembic/versions/001_initial_schema.py`：同步改为 `from miles_server.registry import load_all_models`。

- [ ] **Step 2: 修 backend 根定位逻辑**

`packages/miles-server/src/miles_server/apps/migrate.py`：

```python
"""API 启动时自动执行 Alembic upgrade head（种子数据不在此执行）。"""

import subprocess
import sys
from pathlib import Path


def find_backend_root() -> Path:
    """定位 backend 根（含 alembic.ini）：从 cwd 逐级上溯，找不到则回退到包外四级。"""
    for base in (Path.cwd(), Path(__file__).resolve()):
        for candidate in (base, *base.parents):
            if (candidate / "alembic.ini").is_file():
                return candidate
    # 回退：packages/miles-server/src/miles_server/apps -> backend
    return Path(__file__).resolve().parents[4]


def run_migrations() -> None:
    """在 backend 目录下执行 alembic，并显式指定 alembic.ini 路径。"""
    backend_dir = find_backend_root()
    alembic_ini = backend_dir / "alembic.ini"
    if not alembic_ini.exists():
        raise FileNotFoundError(f"未找到 Alembic 配置: {alembic_ini}")
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(alembic_ini), "upgrade", "head"],
        cwd=str(backend_dir),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(
            f"数据库迁移失败（alembic upgrade head）。请确认 PostgreSQL 已启动，且 backend/.env 中 POSTGRES_DB 与数据库实例一致。\n{detail}"
        ) from None
```

`packages/miles-server/src/miles_server/scripts/export_openapi.py`：把 `ROOT = Path(__file__).resolve().parents[1]` 与 `SNAPSHOT = ROOT / "openapi" / ...` 改为使用 `find_backend_root()`：

```python
from miles_server.apps.migrate import find_backend_root

ROOT = find_backend_root()
SNAPSHOT = ROOT / "openapi" / "openapi.snapshot.json"
```

并删除 `sys.path` 注入（工作区安装后无需）。`from app.apps.application import create_app` → `from miles_server.apps.application import create_app`（codemod 已改，核对）。

`packages/miles-server/src/miles_server/cli.py`：删除 `_BACKEND_ROOT` + `sys.path.insert` 块（工作区安装后无需），把 `"app.main:app"` → `"miles_server.main:app"`，`"app.workers.app"` → `"miles_worker.app"`（两处：worker/beat），`from scripts.db_ops import ...` → `from miles_server.scripts.db_ops import ...`，`from scripts.verify_db import main` → `from miles_server.scripts.verify_db import main`，`from scripts.backfill_media_assets import ...` → `from miles_server.scripts.backfill_media_assets import ...`。

- [ ] **Step 3: 核对 worker 路径与任务名（codemod 已改写，逐项确认）**

Task 2.2 已把 `app/workers/` **剥离包装层**，故文件位于 `packages/miles-worker/src/miles_worker/`（`app.py`、`tasks/`），模块路径为 `miles_worker.app`、`miles_worker.tasks.*`。逐项确认：

```bash
cd backend
# 1) 任务注册与队列路由前缀
rg -n "include=|task_routes|beat_schedule|@celery_app.task" packages/miles-worker/src/miles_worker packages/miles-core/src/miles_core/jobs
# 2) 应全部为 miles_worker.tasks.*，不应出现 miles_worker.workers.* 或 app.workers
rg -n "app\.workers|miles_worker\.workers" packages -g '*.py' || echo "OK: 无旧前缀"
```

修正点：
- `packages/miles-worker/src/miles_worker/app.py`：`include=["miles_worker.tasks"]`；`task_routes` 三个前缀 → `"miles_worker.tasks.ingest.*"` / `".ocr.*"` / `".embed.*"`；`beat_schedule` 的 `task` 值用 `TASK_NAMES[...]`（Task 1.5 已引入）。
- `packages/miles-worker/src/miles_worker/tasks/*.py`：`@celery_app.task(name="miles_worker.tasks...")`（codemod 已改，核对；`generative.py` 的多行装饰器也需确认 name 形参存在）。
- `packages/miles-core/src/miles_core/jobs/tasks.py`：`TASK_NAMES` 各值改为 `"miles_worker.tasks.*"` 字面量（与装饰器 `name=` 严格一致）。

- [ ] **Step 3b: 校验 worker 启动入口可被 Celery 定位**

```bash
cd backend
uv run python -c "from miles_worker.app import celery_app; print(sorted(celery_app.conf.include))"
```

Expected: `['miles_worker.tasks']`

- [ ] **Step 4: 修测试与文档中的路径引用**

`tests/paths.py` 增补：

```python
"""测试用路径常量（子目录内勿用 ``Path(__file__).parents[1]`` 猜 backend 根）。"""

from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PACKAGES = BACKEND_ROOT / "packages"
MILES_AI = PACKAGES / "miles-ai" / "src" / "miles_ai"
MILES_SERVER = PACKAGES / "miles-server" / "src" / "miles_server"
```

更新引用（`rg -n "BACKEND_ROOT" tests`）：
- `tests/flow/test_langgraph_compiler.py`：`BACKEND_ROOT / "app/flow_runtime/templates/rag_flow.json"` → `MILES_AI / "flow_runtime/templates/rag_flow.json"`（同文件两处）
- `tests/flow/test_flow_templates.py`、`tests/flow/test_relevance_grade_flow.py`：同上改为 `MILES_AI / "flow_runtime/templates/..."`
- `tests/infra/test_model_catalog_seed.py`：`BACKEND_ROOT / "scripts" / "seed" / "model_catalog.py"` → `MILES_SERVER / "scripts" / "seed" / "model_catalog.py"`

- [ ] **Step 5: 重写守卫测试为包分层断言**

`tests/test_l3_neutral_imports.py` 改为（保留多路径探测，防止误报）：

```python
"""包分层守卫（补充 import-linter）：miles_server 不含 views、L3 不得依赖 portal。

主门禁是根目录 .importlinter 的 layers/forbidden 契约；本测试为源码级兜底，
沿用原守卫的"源码扫描"思路，路径已适配多包布局。
"""

from __future__ import annotations

from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1]
_PKG = _BACKEND_DIR / "packages"


def _iter_py(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts) if root.exists() else []


def test_l3_packages_do_not_import_portal():
    """miles_ai（原 integrations/flow_runtime/rag）不得出现 miles_portal 引用。"""
    forbidden = ("miles_portal", "from miles_portal import", "import miles_portal")
    offenders: list[str] = []
    for pkg in ("miles-ai",):
        for path in _iter_py(_PKG / pkg / "src"):
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if any(frag in line for frag in forbidden):
                    offenders.append(f"{path.relative_to(_BACKEND_DIR)}:{lineno}: {line.strip()}")
    assert not offenders, "miles_ai 出现 miles_portal 引用：\n" + "\n".join(offenders)


def test_server_package_has_no_views_or_schemas():
    """装配包不得含域端点：packages/miles-server 下不得出现 views/ 目录或 router 定义。"""
    server_src = _PKG / "miles-server" / "src"
    assert not list(server_src.rglob("views")), "miles_server 不应包含 views/ 目录"
    hits = [p for p in _iter_py(server_src) if "APIRouter(" in p.read_text(encoding="utf-8")]
    assert not hits, f"miles_server 不应定义 APIRouter：{hits}"
```

- [ ] **Step 6: 提交（与 2.2/2.3 合并为一次原子提交）**

```bash
git add -A
git commit -F - <<'EOF'
refactor(backend): 迁移为 uv workspace 多包布局

app.* 全量改写为 miles_* 包路径并物理搬迁，修正 backend 根定位、
ORM registry 归属（移至装配层）与测试/资源路径引用。
EOF
```

---

### Task 2.5: 域自持 API 层与 `register_*` 装配

**Files:**
- Create: `packages/miles-portal/src/miles_portal/registration.py`
- Create: `packages/miles-admin/src/miles_admin/registration.py`
- Create: `packages/miles-openapi/src/miles_openapi/__init__.py`、`registration.py`、`views/open_chat.py`、`deps_api_auth.py`
- Modify: `packages/miles-server/src/miles_server/apps/application.py`、`apps/routers.py`

**Interfaces:**
- Produces: `miles_portal.registration.register_portal(app)`、`miles_admin.registration.register_admin(app)`、`miles_openapi.registration.register_open(app)`
- Consumes: `miles_core.web.register_http_middlewares`、`miles_core.web.handlers.exception_handlers`

- [ ] **Step 1: 创建 openapi 包子模块与注册函数**

`open_chat.py` 与 `deps_api_auth.py` 已在 Task 2.2 迁入 `packages/miles-openapi/src/miles_openapi/`，此处补 `__init__.py` 并修正内部 import：

```bash
cd backend
printf '"""对外 API 面（/api/v1/open/*）：开放接口视图与 X-API-Key 鉴权。"""\n' > packages/miles-openapi/src/miles_openapi/__init__.py
```

`views/__init__.py`：

```python
"""对外开放接口视图。"""
```

`open_chat.py` 内 `from miles_portal.tenant.agents.deps_api_auth import require_agent_api_key` → `from miles_openapi.deps_api_auth import require_agent_api_key`（该文件已同迁 openapi 包）。其余对 portal 服务/仓储的引用保持不变（鉴权实现仍在 portal，openapi 只承载视图与依赖）。

`packages/miles-openapi/src/miles_openapi/registration.py`：

```python
"""对外 API 面（/api/v1/open/*）注册。路径保持不变，仅调整代码归属。"""

from __future__ import annotations

from fastapi import FastAPI

from miles_openapi.views import open_chat


def register_open(app: FastAPI) -> None:
    """挂载对外开放接口（X-API-Key 鉴权），不引入 admin 依赖。"""
    app.include_router(open_chat.router, prefix="/api/v1/open", tags=["open-agents"])
```

- [ ] **Step 2: 从 portal/router.py 摘除 open 路由**

`packages/miles-portal/src/miles_portal/tenant/router.py`：删除 `include_router(agents_open_chat.router, prefix="/open", ...)` 一行及其 import，交由 `register_open` 挂载（URL 前缀合计仍为 `/api/v1/open`，`api_router` 的 prefix 是 `/api/v1`）。

- [ ] **Step 3: 加 `register_portal` / `register_admin`**

`packages/miles-portal/src/miles_portal/registration.py`：

```python
"""租户域 API 注册：路由与域内依赖。"""

from __future__ import annotations

from fastapi import FastAPI

from miles_portal.tenant.router import api_router


def register_portal(app: FastAPI) -> None:
    """挂载租户端 API（/api/v1，前缀见 tenant.router）。"""
    app.include_router(api_router)
```

`packages/miles-admin/src/miles_admin/registration.py`：

```python
"""运营后台 API 注册：路由与域内依赖。"""

from __future__ import annotations

from fastapi import FastAPI

from miles_admin.router import admin_router


def register_admin(app: FastAPI) -> None:
    """挂载运营端 API（/api/admin/v1）。"""
    app.include_router(admin_router)
```

- [ ] **Step 4: 装配根改为调用 register_*，删除 routers.py**

`packages/miles-server/src/miles_server/apps/application.py`：

```python
"""FastAPI 应用工厂：CORS、链路追踪、路由挂载与启动期迁移 / LangGraph checkpoint。"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from miles_admin.registration import register_admin
from miles_core.config import get_settings
from miles_core.logging import setup_logging
from miles_core.web import register_http_middlewares
from miles_core.web.handlers import exception_handlers
from miles_openapi.registration import register_open
from miles_portal.registration import register_portal
from miles_server.apps.migrate import run_migrations


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期钩子：启动时初始化日志 / OTel、执行 schema 迁移并建 LangGraph checkpointer，关闭时逆序释放。"""
    from miles_ai.integrations.langgraph.checkpointer import (
        init_langgraph_checkpointer,
        shutdown_langgraph_checkpointer,
    )
    from miles_core.infra.otel import setup_otel, shutdown_otel

    setup_logging()
    setup_otel(get_settings(), app=app)
    run_migrations()
    app.state.langgraph_checkpoint = await init_langgraph_checkpointer()
    yield
    await shutdown_langgraph_checkpointer()
    shutdown_otel()


def create_app() -> FastAPI:
    """构造 FastAPI 应用：装配 CORS、HTTP 中间件、统一异常处理并挂载 open / portal / admin 路由。"""
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        description=settings.APP_DESCRIPTION,
        openapi_url="/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        swagger_ui_oauth2_redirect_url="/docs/oauth2-redirect",
        exception_handlers=exception_handlers,
        # 勿将 settings.debug 传给 FastAPI：True 时 Starlette 返回明文 traceback，
        # 会绕过 miles_core.web.handlers 的统一 {code, message, data, trace_id} 信封。
        debug=False,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r".*",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Trace-Id"],
    )
    register_http_middlewares(app)

    register_open(app)
    register_portal(app)
    register_admin(app)
    return app
```

删除 `packages/miles-server/src/miles_server/apps/routers.py`。

- [ ] **Step 5: 校验路由与快照**

```bash
cd backend
.venv/bin/python -m compileall -q packages && echo "compile OK"
.venv/bin/python -m miles_server.scripts.export_openapi --check
```

Expected: `OpenAPI snapshot OK`（**关键闸门**：若漂移说明路由/前缀有变）。

- [ ] **Step 6: 校验 server 无 views**

```bash
find packages/miles-server/src -name views -o -name schemas | grep . && echo "FAIL" || echo "OK: server 无 views/schemas"
.venv/bin/python -m pytest tests/test_l3_neutral_imports.py -q
```

- [ ] **Step 7: 提交**

```bash
git add -A
git commit -F - <<'EOF'
refactor(api): 域自持 API 层与装配根分离

portal/admin/openapi 各自暴露 register_*，装配根仅负责组合与通用管道，
开放面迁入 miles_openapi 且 URL 路径不变。
EOF
```

---

## Phase 3: 工具链与入口

### Task 3.1: `cli`/`scripts` 入口与 console script

**Files:**
- Modify: `packages/miles-server/pyproject.toml`
- Modify: `Makefile`

- [ ] **Step 1: 声明 console script 与依赖**

`packages/miles-server/pyproject.toml` 增加：

```toml
[project.scripts]
milesai = "miles_server.cli:main"
```

并把 `alembic`、`psycopg2-binary`、`click`、`uvicorn[standard]`、`python-multipart`、`python-jose[cryptography]`、`bcrypt`、`email-validator`、`croniter` 等运行入口所需依赖补入 `dependencies`（按实际 import 补齐）。

- [ ] **Step 2: 修 CLI 三处硬编码（否则运行即报错）**

`packages/miles-server/src/miles_server/cli.py`：

1. **`click.version_option` 的包名**：`package_name="milesai"` 在改包后已不是发行版名，会取不到版本。改为：

```python
@click.version_option(package_name="miles-server", prog_name="milesai")
```

2. **删除 `_BACKEND_ROOT` / `sys.path.insert` 块**（工作区安装后无需，且 `parents[1]` 已指向错误位置）。

3. **`scripts.*` 根引用**（共 6 处：`db_ops` ×4、`verify_db`、`backfill_media_assets`）→ `miles_server.scripts.*`：

```bash
rg -n "(from|import)[ \t]+scripts(?=[.\s])" packages/miles-server/src/miles_server/cli.py
```

若仍有命中，逐个改为 `from miles_server.scripts.<mod> import ...`（Task 2.3 的 codemod 应已处理，此处为核对兜底）。

- [ ] **Step 3: 验证 CLI**

```bash
cd backend
uv sync --all-packages --group dev
uv run milesai --help
uv run python -m miles_server.cli --help
```

Expected: 打印命令帮助（serve/worker/beat/migrate/init-db/seed/verify-db/backfill-media-assets）。

- [ ] **Step 3: 改造 Makefile**

替换 `install-backend`、`openapi-check`、`openapi-write` 与各 `cli.py` 调用：

```make
install-backend: ## 安装后端工作区依赖（uv sync）
	cd $(BACKEND) && uv sync --all-packages --group dev

init-db: ## 迁移 + 全量种子（SEED 可覆盖范围）
	cd $(BACKEND) && $(PY) -m miles_server.cli init-db

migrate: ## 仅执行 Alembic 迁移（alembic upgrade head）
	cd $(BACKEND) && $(PY) -m miles_server.cli migrate

seed: ## 写入指定范围种子（默认 all）
	cd $(BACKEND) && $(PY) -m miles_server.cli seed $(SEED)

verify-db: ## 校验核心表是否就绪
	cd $(BACKEND) && $(PY) -m miles_server.cli verify-db

serve: ## 启动 API（debug 时默认热重载）
	cd $(BACKEND) && $(PY) -m miles_server.cli serve

worker: ## 启动 Celery Worker
	cd $(BACKEND) && $(PY) -m miles_server.cli worker

beat: ## 启动 Celery Beat（智能体定时任务）
	cd $(BACKEND) && $(PY) -m miles_server.cli beat

openapi-check: ## 校验 OpenAPI 快照无漂移
	cd $(BACKEND) && $(PY) -m miles_server.scripts.export_openapi --check

openapi-write: ## 重写 OpenAPI 快照（改路由/Schema 后执行并提交）
	cd $(BACKEND) && $(PY) -m miles_server.scripts.export_openapi --write
```

- [ ] **Step 4: 跑闸门**

```bash
cd backend && .venv/bin/python -m pytest -q && .venv/bin/python -m miles_server.scripts.export_openapi --check
cd .. && make openapi-check
```

- [ ] **Step 5: 提交**

```bash
git add -A
git commit -F - <<'EOF'
build(make): 后端改为 uv workspace 安装并提供 milesai 入口

install-backend 走 uv sync，cli 与脚本改由 miles_server 承接，
Makefile 的迁移/种子/OpenAPI 目标同步更新。
EOF
```

---

### Task 3.2: `miles_runner` 自带 `RunnerSettings`（去 core 依赖）

**Files:**
- Create: `packages/miles-runner/src/miles_runner/settings.py`
- Modify: `packages/miles-runner/src/miles_runner/runner/main.py`
- Modify: `packages/miles-runner/pyproject.toml`（移除 `miles-core` 依赖，若曾声明）

**Interfaces:**
- Produces: `miles_runner.settings.RunnerSettings`（`mcp_runner_token` / `mcp_runner_max_concurrent_per_tenant` / `mcp_runner_command_whitelist_set`）
- Consumes: `pydantic_settings.BaseSettings`

- [ ] **Step 1: 写 RunnerSettings**

`packages/miles-runner/src/miles_runner/settings.py`：

```python
"""Runner 独立配置：只读 MCP_RUNNER_*，避免沙箱依赖 miles_core 的整套 settings。"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class RunnerSettings(BaseSettings):
    """Runner 运行配置（环境变量优先，前缀 MCP_RUNNER_*）。"""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mcp_runner_token: str = ""
    mcp_runner_max_concurrent_per_tenant: int = 3
    mcp_runner_command_whitelist: str = ""

    @property
    def mcp_runner_command_whitelist_set(self) -> set[str]:
        """命令白名单集合（逗号分隔，忽略空白）。"""
        return {item.strip() for item in self.mcp_runner_command_whitelist.split(",") if item.strip()}


@lru_cache
def get_runner_settings() -> RunnerSettings:
    """进程级缓存的 Runner 配置。"""
    return RunnerSettings()
```

- [ ] **Step 2: 改造 runner main**

`packages/miles-runner/src/miles_runner/runner/main.py`：
- 删除 `from miles_core.config import get_settings`，改 `from miles_runner.settings import get_runner_settings`
- `settings = get_runner_settings()`
- 其余 `settings.mcp_runner_*` 字段名保持不变（与 core 读同一批环境变量）

- [ ] **Step 3: 校验 runner 依赖闭包最小**

```bash
cd backend
uv sync --package miles-runner
uv tree --package miles-runner
```

Expected: 依赖闭包**不含** langchain / langgraph / litellm / weaviate / pymilvus / torch / sqlalchemy / celery。

```bash
uv run --package miles-runner python -c "import miles_runner.main; print('runner imports OK')"
```

- [ ] **Step 4: 提交**

```bash
git add -A
git commit -F - <<'EOF'
refactor(runner): 沙箱自带 RunnerSettings

仅读 MCP_RUNNER_* 环境变量，去掉对 miles_core 的依赖，
使 runner 镜像依赖闭包含最小化。
EOF
```

---

### Task 3.3: Dockerfile ×3 与 compose 按包安装

**Files:**
- Modify: `Dockerfile.api`、`Dockerfile.worker`、`Dockerfile.mcp-runner`、`docker-compose.yml`

**统一方案**：先用 `uv export` 把该入口包的**第三方**依赖导出为固定版本的 requirements（`--no-emit-workspace` 排除本地包），安装后再以 `--no-deps` 逐个安装本地包。这样既走 lock 保证可复现，又让各镜像只装所需成员包。

- [ ] **Step 1: 重写 Dockerfile.api**

```dockerfile
FROM registry.cn-shenzhen.aliyuncs.com/kye_secure/python:3.11.9-uv-ffmpeg

WORKDIR /app

# 仅复制 workspace 元数据以命中依赖层缓存
COPY backend/pyproject.toml /app/backend/pyproject.toml
COPY backend/uv.lock /app/backend/uv.lock
COPY backend/packages/miles-common/pyproject.toml  /app/backend/packages/miles-common/pyproject.toml
COPY backend/packages/miles-exec/pyproject.toml    /app/backend/packages/miles-exec/pyproject.toml
COPY backend/packages/miles-core/pyproject.toml    /app/backend/packages/miles-core/pyproject.toml
COPY backend/packages/miles-ai/pyproject.toml      /app/backend/packages/miles-ai/pyproject.toml
COPY backend/packages/miles-portal/pyproject.toml  /app/backend/packages/miles-portal/pyproject.toml
COPY backend/packages/miles-admin/pyproject.toml   /app/backend/packages/miles-admin/pyproject.toml
COPY backend/packages/miles-openapi/pyproject.toml /app/backend/packages/miles-openapi/pyproject.toml
COPY backend/packages/miles-server/pyproject.toml  /app/backend/packages/miles-server/pyproject.toml

RUN cd /app/backend \
 && uv export --frozen --no-dev --no-emit-workspace --package miles-server -o /tmp/req.txt \
 && uv pip install --system -r /tmp/req.txt \
      -i https://mirrors.aliyun.com/pypi/simple --trusted-host mirrors.aliyun.com

COPY backend /app/backend

# 本地成员包：api 需要 server/openapi/portal/admin/ai/core/exec/common（不含 worker/runner）
RUN uv pip install --system --no-deps \
      "/app/backend/packages/miles-common" \
      "/app/backend/packages/miles-exec" \
      "/app/backend/packages/miles-core" \
      "/app/backend/packages/miles-ai" \
      "/app/backend/packages/miles-portal" \
      "/app/backend/packages/miles-admin" \
      "/app/backend/packages/miles-openapi" \
      "/app/backend/packages/miles-server"

WORKDIR /app/backend
EXPOSE 8000
CMD ["uvicorn", "miles_server.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: 重写 Dockerfile.worker**

与 Step 1 同构，替换 `--package miles-worker`，本地包只装 worker 依赖闭包（`worker/portal/ai/core/exec/common`，不含 admin/openapi/runner）：

```dockerfile
RUN cd /app/backend \
 && uv export --frozen --no-dev --no-emit-workspace --package miles-worker -o /tmp/req.txt \
 && uv pip install --system -r /tmp/req.txt \
      -i https://mirrors.aliyun.com/pypi/simple --trusted-host mirrors.aliyun.com

COPY backend /app/backend

RUN uv pip install --system --no-deps \
      "/app/backend/packages/miles-common" \
      "/app/backend/packages/miles-exec" \
      "/app/backend/packages/miles-core" \
      "/app/backend/packages/miles-ai" \
      "/app/backend/packages/miles-portal" \
      "/app/backend/packages/miles-worker"

WORKDIR /app/backend
CMD ["celery", "-A", "miles_worker.app", "worker", "-l", "info", "-Q", "default,parse,ocr,asr,embed"]
```

（COPY 的 pyproject 清单同上，另加 `miles-worker/pyproject.toml`。）

- [ ] **Step 3: 重写 Dockerfile.mcp-runner**（只装 exec/common/runner）

```dockerfile
RUN cd /app/backend \
 && uv export --frozen --no-dev --no-emit-workspace --package miles-runner -o /tmp/req.txt \
 && uv pip install --system -r /tmp/req.txt \
      -i https://mirrors.aliyun.com/pypi/simple --trusted-host mirrors.aliyun.com

COPY backend /app/backend

RUN uv pip install --system --no-deps \
      "/app/backend/packages/miles-common" \
      "/app/backend/packages/miles-exec" \
      "/app/backend/packages/miles-runner"

WORKDIR /app/backend
RUN useradd -m -u 10001 runner && chown -R runner:runner /app /tmp
USER runner
EXPOSE 8090
CMD ["uvicorn", "miles_runner.main:app", "--host", "0.0.0.0", "--port", "8090"]
```

> 该镜像的 requirements 只含 `miles-runner` 的第三方依赖（fastapi/pydantic/pydantic-settings 等），**不含** langchain / langgraph / litellm / weaviate / pymilvus / torch / sqlalchemy / celery——这正是 spec §3 的安全收益，由 Task 4.1 Step 6 断言。

- [ ] **Step 4: 更新 compose 命令**

`docker-compose.yml`：
- `command: celery -A app.workers.app worker ...` → `celery -A miles_worker.app worker ...`
- `command: celery -A app.workers.app beat ...` → `celery -A miles_worker.app beat ...`
- api 服务健康检查保持 `/api/v1/health` 不变；dev 卷挂载 `./backend:/app/backend:ro` 保留。

- [ ] **Step 5: 构建并冒烟**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI
docker build -f Dockerfile.api -t milesai-api:ws . 2>&1 | tail -5
docker build -f Dockerfile.mcp-runner -t milesai-mcp-runner:ws . 2>&1 | tail -5
```

Expected: 构建成功。

```bash
docker run --rm milesai-mcp-runner:ws python -c "import miles_runner.main; print('runner OK')"
docker run --rm milesai-api:ws python -c "import miles_server.main; print('api OK')"
```

Expected: `runner OK` / `api OK`。镜像体积基线已按用户决策跳过，瘦身证据由 Task 3.2 Step 3 与 Task 4.1 Step 6 的 `uv tree` 断言提供。

- [ ] **Step 6: 提交**

```bash
git add -A
git commit -F - <<'EOF'
build(docker): 镜像改为按包安装并瘦身 runner

API/Worker 分别安装 miles-server / miles-worker，runner 只装
miles-runner，沙箱镜像不再包含 AI 栈依赖。
EOF
```

---

### Task 3.4: CI 切 uv + `import-linter` 分层契约 + Makefile 门禁

**Files:**
- Create: `.importlinter`
- Modify: `.github/workflows/lint.yml`、`Makefile`

- [ ] **Step 1: 写 import-linter 契约**

`.importlinter`（放 `backend/.importlinter`）：

```ini
[importlinter]
root_packages =
    miles_common
    miles_exec
    miles_core
    miles_ai
    miles_portal
    miles_admin
    miles_openapi
    miles_server
    miles_worker
    miles_runner

[importlinter:contract:layers]
name = 包分层方向（上层可 import 下层）
type = layers
layers =
    miles_server | miles_worker | miles_runner
    miles_openapi | miles_admin
    miles_portal
    miles_ai
    miles_core
    miles_exec | miles_common

[importlinter:contract:no-ai-to-portal]
name = L3/L2 不得依赖租户域
type = forbidden
source_modules = miles_ai
forbidden_modules = miles_portal

[importlinter:contract:openapi-no-admin]
name = 开放面不得依赖运营面
type = forbidden
source_modules = miles_openapi
forbidden_modules = miles_admin

[importlinter:contract:portal-no-admin]
name = 租户域不得依赖运营面
type = forbidden
source_modules = miles_portal
forbidden_modules = miles_admin

[importlinter:contract:runner-minimal]
name = 沙箱仅依赖 exec/common
type = forbidden
source_modules = miles_runner
forbidden_modules =
    miles_core
    miles_ai
    miles_portal
    miles_admin
    miles_openapi

[importlinter:contract:core-no-ai]
name = 基础设施/模型层不得依赖 AI 编排层
type = forbidden
source_modules = miles_core
forbidden_modules = miles_ai
```

- [ ] **Step 2: 本地跑契约**

```bash
cd backend
uv run lint-imports
```

Expected: 6 个契约全部 `PASSED`（若失败，输出会指出具体 import 行，回到对应 Task 修）。

- [ ] **Step 3: CI 改造**

`.github/workflows/lint.yml` → `backend` job：

```yaml
      - uses: astral-sh/setup-uv@v5
      - name: Install backend (uv workspace)
        run: uv sync --all-packages --group dev
      - name: Ruff format check
        run: uv run ruff format --check .
      - name: Ruff lint
        run: uv run ruff check .
      - name: Package layering guard（import-linter）
        run: uv run lint-imports
      - name: OpenAPI snapshot check
        run: uv run python -m miles_server.scripts.export_openapi --check
      - name: Backend tests
        run: uv run python -m pytest -q
```

（移除原 `pip install -e ".[dev]"`、`python -m pytest tests/test_l3_neutral_imports.py` 独立步。）

- [ ] **Step 4: Makefile 加分层门禁**

```make
layers-check: ## 校验包分层契约（import-linter）
	cd $(BACKEND) && uv run lint-imports

check: lint-backend format-check-backend layers-check openapi-check test-backend ## 复刻 CI 后端 job 的质量门禁
```

- [ ] **Step 5: 跑全量门禁**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI
make check
```

Expected: 全绿。

- [ ] **Step 6: 提交**

```bash
git add -A
git commit -F - <<'EOF'
ci(backend): 切换 uv workspace 并接入分层契约门禁

CI 与 Makefile 改为 uv sync / uv run，新增 import-linter
layers+forbidden 契约固化包依赖方向。
EOF
```

---

### Task 3.5: 文档更新

**Files:**
- Modify: `docs/architecture/layering.md`、`docs/architecture/engine-di-convergence.md`
- Modify: `backend/README.md`、`README.md`、`docker/README.md`
- Modify: 其余引用 `app.*` 路径的 docs（`docs/architecture/technical-design.md`、`docs/guides/*.md`、`docs/features/*.md`）

- [ ] **Step 1: 批量替换文档中的模块路径**

```bash
rg -l "(?<![\w.])app\.(tenant|admin|core|infra|models|rag|integrations|flow_runtime|common|utils|apps|middlewares|workers|runner|deletion|marketplace|exec)\b" docs backend/README.md README.md docker/README.md
```

逐文件按 spec §4 映射表替换（docs 无 Python 语义，直接按映射替换即可）。

- [ ] **Step 2: `layering.md` 增补"包边界"与"API 层归属"两节**

在 §2 后插入（内容取自 spec §2 与 §2.2）：10 包表、依赖 DAG、硬判据、①域 API 层 / ②通用 Web 管道（`miles_core.web`）/ ③装配根（`miles_server`）三层次归属表。

- [ ] **Step 3: `backend/README.md` 更新安装与命令**

- 安装：`uv sync --all-packages --group dev`
- 运行：`uv run milesai serve|worker|beat|init-db|seed|verify-db`
- 测试/门禁：`make check`（含 `layers-check`）
- 目录结构：`backend/packages/miles-*`

- [ ] **Step 4: 文档残留校验**

```bash
rg -n "(?<![\w.])app\.(tenant|admin|core|infra|models|rag|integrations|flow_runtime|common|apps|middlewares|workers|runner)\b" docs backend/README.md README.md docker/README.md | grep -v "superpowers/" || echo "OK: 文档无残留"
```

Expected: `OK: 文档无残留`（`docs/superpowers/**` 历史 spec/plan 保留原文，不追改）。

- [ ] **Step 5: 提交**

```bash
git add -A
git commit -F - <<'EOF'
docs(architecture): 更新为多包布局与包边界约定

layering 增补包依赖 DAG、硬判据与 API 层归属（域自持 + core.web
通用管道 + miles_server 装配根），同步 README 安装与运行命令。
EOF
```

---

## Phase 4: 终验

### Task 4.1: 全量验证与收尾

- [ ] **Step 1: 全量质量门禁**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI
make check
cd backend && uv run lint-imports
```

Expected: 全绿。

- [ ] **Step 2: OpenAPI 快照零漂移（硬性）**

```bash
cd backend
uv run python -m miles_server.scripts.export_openapi --check
sha256sum openapi/openapi.snapshot.json    # 与 Task 0.1 基线一致
```

Expected: `OpenAPI snapshot OK`；sha256 与基线一致。

- [ ] **Step 3: 三镜像构建与 import 冒烟**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI
make build-all
docker run --rm milesai-api:latest python -c "import miles_server.main; print('api OK')"
docker run --rm milesai-worker:latest python -c "import miles_worker.app; print('worker OK')"
docker run --rm milesai-mcp-runner:latest python -c "import miles_runner.main; print('runner OK')"
```

Expected: 三个 `* OK`。（镜像体积对比按用户决策跳过。）

- [ ] **Step 4: 应用装配冒烟（本地 ASGI，无需基础设施）**

compose 运行时冒烟按用户决策**跳过**（需外部 PG/Redis/MinIO/Milvus 与 `.env`，延后至人工在具备基础设施的环境执行）。改用本地 ASGI 装配冒烟，等价验证"装配根可构造、路由已挂载"：

```bash
cd backend
uv run python - <<'PY'
from miles_server.apps.application import create_app
app = create_app()
paths = sorted(app.openapi()["paths"])
for must in ("/api/v1/health", "/api/v1/open/agents/{agent_id}/chat"):
    assert must in paths, f"缺路由: {must}\n{paths[:20]}"
admin = [p for p in paths if p.startswith("/api/admin/v1")]
assert admin, "缺 /api/admin/v1 路由"
print(f"routes OK: total={len(paths)} admin={len(admin)}")
PY
```

Expected: `routes OK: total=<N> admin=<M>`（N/M 与迁移前一致；`test_api_e2e.py` 已覆盖同一 `create_app()` 的请求级行为）。

- [ ] **Step 5: 风控与开放面回归**

```bash
cd backend
uv run python -m pytest tests/api tests/tenant/agents/test_api_access.py tests/tenant/agents/test_agent_api_keys.py -q
```

Expected: 通过（覆盖 403/429 信封与 `/api/v1/open/*` 的 X-API-Key 鉴权）。

- [ ] **Step 6: runner 依赖闭包断言（瘦身证据）**

```bash
cd backend
uv tree --package miles-runner | rg -i "langchain|langgraph|litellm|weaviate|pymilvus|torch|sqlalchemy|celery" && echo "FAIL: 含重依赖" || echo "OK: 依赖闭包最小"
```

Expected: `OK: 依赖闭包最小`（这是沙箱瘦身与安全收益的主证据；镜像体积基线按用户决策跳过）。

- [ ] **Step 7: 最终提交与合并准备**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI
git add -A
git commit -F - <<'EOF'
chore(backend): 多包工作区迁移完成

全量门禁、OpenAPI 快照、三镜像冒烟与风控回归通过。
EOF
git log --oneline main..HEAD
```

**终验记录（执行后填写）：**
- 测试用例数：____（基线 ____）
- `lint-imports`：6 契约 PASSED
- OpenAPI sha256：____（与基线一致）
- runner 依赖闭包：`uv tree` 无重依赖（体积基线与 compose 冒烟按用户决策跳过）
- 延后人工执行：`docker compose up -d --build` 运行时冒烟（需外部基础设施与 `.env`）

---

## Self-Review

**1. Spec 覆盖核对**

| spec 章节 | 覆盖任务 |
|-----------|----------|
| §2 包图/依赖/硬判据 | 2.1（声明）、2.2（搬迁）、3.4（契约） |
| §2.1 各包结构 | 2.2、2.5 |
| §2.2 API 层归属 | 2.5、3.5 |
| §3.1 包内环（rag↔integrations, core↔infra） | 2.2（同包即消） |
| §3.2 portal↔runner | 1.4、3.2 |
| §3.3 portal↔worker | 1.5、2.4 |
| §3.4 common↔core | 1.1、1.2 |
| §3.5 portal→admin（风控/管道） | 1.3 |
| §4 迁移映射表 | 2.3（codemod 内嵌）、2.4（特殊） |
| §4 对外 API 归属 | 2.5 |
| §5.1 workspace 机制 | 2.1 |
| §5.2 CI/Docker/cli/alembic/tests/docs | 3.1、3.3、3.4、3.5 |
| §5.3 边界守卫 | 2.4（守卫测试）、3.4（import-linter） |
| §6 四阶段迁移 | Phase 0–4 整体 |
| §7 验收标准 | 4.1 逐条 |
| §8 风险缓解 | 1.4（exec 先抽取）、2.4（路径）、3.2（settings）、4.1（回归） |
| §11 miles_integration（本次不做） | 不在本计划，spec 已单列 |

**2. 占位符扫描**：无 TBD/TODO；所有代码步骤均给出可执行代码或命令；`Task 2.2` 的 `flatten` 为真实 shell 函数。

**3. 类型与命名一致性**：
- `register_portal` / `register_admin` / `register_open` 在 2.5 定义并在 `application.py` 调用，命名一致。
- `TASK_NAMES` 键名（`ingest_document` 等）在 1.5 定义、`workers/app.py` 消费，一致。
- `find_backend_root()` 在 2.4 定义，被 `migrate.py` 与 `export_openapi.py` 共用，命名一致。
- `RunnerSettings.mcp_runner_command_whitelist_set` 与 runner `main.py` 原用法一致。
- `tests/paths.py` 的 `PACKAGES` / `MILES_AI` / `MILES_SERVER` 在 2.4 定义并被 3 处测试引用，一致。

**4. 已识别风险（执行时留意）**：
- Task 2.2 的搬迁分两类（**剥离** vs **保留**包装层），是本次最易错处：`flatten` 仅对 `common/exec/core/admin/workers/runner` 执行；`infra/models/rag/integrations/flow_runtime/tenant/deletion/marketplace/apps/scripts` 必须保留目录名。Step 5 的目录形态校验是硬闸门，务必逐条比对。
- Task 2.2 的 `flatten` 依赖 Step 1 先删占位 `__init__.py`（否则 `mv` 会因同名冲突失败）；若 Step 1 遗漏，重跑 Step 1 后再执行 Step 3。
- `open_chat.py` / `deps_api_auth.py` 在 **Task 2.2** 就迁入 `miles_openapi`（而非 2.5），是为保证 Task 2.3 的 codemod 目标路径已存在——若放在 2.5，2.4 的提交点会处于"import 指向不存在的模块"的破损态。
- Task 3.3 采用 `uv export --no-emit-workspace` + `--no-deps` 逐个安装本地包：若 `uv export` 在仅有 pyproject/lock 而无源码时失败，回退为 `COPY backend` 之后执行 `uv sync --package <pkg> --frozen --no-dev`，三处统一。
- Task 3.1 的第三方依赖按包分配需逐个核对 import，避免漏声明（漏声明会在 `uv sync --package <pkg>` 或镜像 `import` 时暴露）。
