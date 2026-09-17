# API 声明层与 ORM 解耦 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `views/`、`schemas/` 不再 import 任何承载 SQLAlchemy 实体的模块，并由 `.importlinter` 新增第 7 条契约硬禁这条依赖，同时保证 `openapi/openapi.snapshot.json` 逐字节不变。

**Architecture:** 三步走。(1) 把嵌在 ORM 包内的 2 个纯 DTO 模块下沉到 `miles_common/schemas/`，旧路径转 re-export 壳，故 L2/L3 消费者零改动。(2) 为 21 个持久化枚举在 API 侧建立**独立声明**（逐字复制成员名/顺序/值/类 docstring，**不**转 re-export），再把 27 个文件的 import 指向新声明。(3) 加 `.importlinter` 契约与枚举平价测试把它锁死。

**Tech Stack:** Python 3.11、FastAPI + Pydantic v2、SQLAlchemy 2 + asyncpg、import-linter、Ruff、pytest、uv workspace。

**Spec:** `docs/superpowers/specs/2026-09-17-api-layer-orm-decoupling-design.md`（下称「设计」；§ 引用均指该文件）

## Global Constraints

- **工作区**：仓库根 `git worktree add .worktrees/api-layer-orm-decoupling -b feat/api-layer-orm-decoupling`（自 `main` 切出）。**禁止直接在 `main` 上改**。所有命令在 `backend/` 下执行，除非另注。
- **ORM 侧零改动**：`packages/miles-core/src/miles_core/models/**` 只允许 `agent/chat_io.py` 与 `marketplace/dto.py` 两个文件改成 re-export 壳。枚举定义、列类型、`values_callable`、`alembic/` 目录一律不动。
- **API 侧枚举声明必须与 ORM 侧逐字一致**：基类、成员名、成员顺序、成员值、类 docstring 全等。前四项决定 Pydantic 生成的 `enum` 数组（按定义顺序）；类 docstring 会被 Pydantic 渲染进 schema 的 `description`——漏抄会漂移 `openapi.snapshot.json`（Task 3 实测），故 ORM 侧**有**类 docstring 的枚举必须逐字照抄，ORM 侧**没有**的不许添加。统一用 `import enum` + `class X(enum.StrEnum)` 风格（与 ORM 侧同形）。
- **OpenAPI 快照逐字节不变**：`git diff --stat` 对 `backend/openapi/openapi.snapshot.json` 必须为空。
- **门禁命令**（五道全绿才算完成；下文简称 FMT / CHECK / LINT / SNAP / TEST）：
  - FMT = `uv run --all-packages --group dev ruff format --check .`
  - CHECK = `uv run --all-packages --group dev ruff check .`
  - LINT = `uv run --all-packages --group dev lint-imports`
  - SNAP = `uv run --all-packages --group dev python -m miles_server.scripts.export_openapi --check`（期望输出 `OpenAPI snapshot OK`）
  - TEST = `uv run --all-packages --group dev python -m pytest -q`
  - **注意**：必须走 `uv run ... python -m pytest`。直接 `python -m pytest` 会 `ModuleNotFoundError: No module named 'miles_core'`；裸 `pytest` 控制台脚本在本仓有既存缺陷（收集期报错），与本设计无关，不要试图修它。
  - **实测基线**：`1122 passed`（2026-09-17）。
- **re-export 壳必须带 `__all__`**：Ruff 的 F401 是文件级判断，非 `__init__.py` 的 re-export 模块不写 `__all__` 会报未使用导入。
- **提交信息用简体中文**，Conventional Commits（`<type>(<scope>): <简述>`），用 HEREDOC 传递。
- **违规面探测器**：贯穿全程用同一个 AST 脚本（建在 `/tmp/scan_orm_sites.py`，**不提交**）。终态须 `TOTAL=0`。它必须同时覆盖三种写法，否则会出现「探测器说 0、`lint-imports` 说 BROKEN」的假绿：`from X import Y`、裸 `import X`、以及相对 import（`from ..models import X`，实测当前 views/schemas 下零相对 import，但契约解析得了就该测得到）：

```python
# /tmp/scan_orm_sites.py —— 复现设计 §3.1 的违规面（在 backend/ 下运行）
import ast
import pathlib


def _forbidden(mod: str) -> bool:
    if mod.startswith(("miles_core.models", "miles_admin.models")):
        return True
    parts = mod.split(".")
    return len(parts) >= 4 and parts[0] == "miles_portal" and parts[1] == "tenant" and parts[3] == "models"


def _absolute(path: pathlib.Path, node: ast.ImportFrom) -> str | None:
    """把 ImportFrom 解析成绝对模块名（含相对 import）。"""
    if not node.level:
        return node.module
    src = next(p for p in path.parents if p.name == "src")
    pkg = list(path.relative_to(src).with_suffix("").parts[:-1])  # 本文件所属包
    base = pkg[: len(pkg) - (node.level - 1)]
    if node.module:
        base += node.module.split(".")
    return ".".join(base)


total = 0
for pkg in ("miles-portal", "miles-admin", "miles-openapi"):
    for f in sorted(pathlib.Path(f"packages/{pkg}/src").rglob("*.py")):
        if not any(p in ("views", "schemas") for p in f.parts):
            continue
        for node in ast.walk(ast.parse(f.read_text())):
            targets: list[str] = []
            if isinstance(node, ast.ImportFrom):
                resolved = _absolute(f, node)
                if resolved:
                    targets.append(resolved)
            elif isinstance(node, ast.Import):
                targets.extend(a.name for a in node.names)
            for target in targets:
                if _forbidden(target):
                    print(f"{f}:{node.lineno}: {target}")
                    total += 1
print(f"TOTAL={total}")
```

起点实测：`TOTAL=28`（27 个文件）。**注意**：这是导航工具，权威判据始终是 `lint-imports`（Task 5 Step 2）。

---

### Task 1: 下沉 2 个 DTO 模块到 `miles_common`

**Files:**
- Create: `backend/packages/miles-common/src/miles_common/schemas/chat_io.py`
- Create: `backend/packages/miles-common/src/miles_common/schemas/marketplace.py`
- Create: `backend/tests/models/test_api_enum_parity.py`（本任务先只含 2 对 marketplace 枚举）
- Modify: `backend/packages/miles-core/src/miles_core/models/agent/chat_io.py`（→ re-export 壳）
- Modify: `backend/packages/miles-core/src/miles_core/models/marketplace/dto.py`（→ re-export 壳）
- Modify: `backend/packages/miles-portal/src/miles_portal/tenant/agents/schemas/agent.py`（docstring + import 路径）
- Modify: `backend/packages/miles-portal/src/miles_portal/tenant/marketplace/schemas/marketplace.py`（docstring + import 路径）
- Modify: `backend/packages/miles-admin/src/miles_admin/app_ops/views/marketplace_review.py:15`（import 路径）
- Modify: `backend/tests/tenant/agents/test_agent_chat_io_shim.py`（补断言）

**Interfaces:**
- Produces: `miles_common.schemas.chat_io`（`ChatArtifact`/`ChatMediaIn`/`ChatRequest`/`ChatResponse`/`PendingToolCall`）、`miles_common.schemas.marketplace`（17 个 DTO + `MarketplaceAppStatus`/`MarketplaceAppVisibility` 两个 API 侧独立枚举）。两模块均为后续任务与平价测试的 import 目标。
- Consumes: 无（本任务不依赖其他任务）。

**背景（实施者必读）：** 为什么必须再下沉一层——`.importlinter` 第 7 条契约按**聚合包**层级禁止（设计 §3.3 第 2、5 条），而 `miles_core.models.agent`、`miles_core.models.marketplace` 是 ORM 聚合包，整包禁令会连带禁止包内的纯 DTO。故 DTO 必须搬出 `miles_core.models`。

- [ ] **Step 0: 建 worktree**

```bash
cd /Users/xiezhigang/Projects/miles/MilesAI
git worktree add .worktrees/api-layer-orm-decoupling -b feat/api-layer-orm-decoupling
cd .worktrees/api-layer-orm-decoupling/backend
uv run --all-packages --group dev python -m pytest -q   # 期望 1122 passed
```

- [ ] **Step 0b: 建违规面探测器（不提交）**

按 Global Constraints 的「违规面探测器」把脚本写到 `/tmp/scan_orm_sites.py`，然后确认起点：

```bash
uv run --all-packages --group dev python /tmp/scan_orm_sites.py
```
Expected: 列出 28 行 import 并以 `TOTAL=28` 结尾。若数字不符，**停下**——说明探测器本身写错了，先修探测器。

- [ ] **Step 1: 写失败测试（平价测试骨架 + 2 对 marketplace 枚举）**

创建 `backend/tests/models/test_api_enum_parity.py`：

> **实现以仓库文件为准，不在此内嵌副本**：该测试已落地为
> `backend/tests/models/test_api_enum_parity.py`，骨架在 Task 2/3 中扩充到「21 对枚举 + 4 个不变量」。
> 内嵌副本会随判据演进腐化（本段曾因判据从正则改为 AST 而与实现不符），故只记判据要点：
>
> - **五项全等**：基类、成员名、成员顺序、成员值、类 docstring —— 由 `_mismatch_report` 按此
>   顺序短路。类 docstring 在列，因为 Pydantic 会把 enum 类 docstring 渲染成 schema 的
>   `description`（漏抄会静默漂移 `openapi.snapshot.json`）。
> - **「禁止 `is` 比较枚举成员」用 AST 判据**（`_enum_class_of` / `_identity_comparisons`），
>   **不是**文本正则：覆盖 `Name.MEMBER`、`alias.Class.MEMBER`、`pkg.mod.Class.MEMBER` 三种写法
>   （后两种是迁移后 `from ...schemas import enums as X` 的风格，正则版要求 `operand.value` 是
>   `ast.Name` 会漏检），且注释/docstring 里的说明性提及不误伤。
> - 另有**名称级白名单守卫**：`views/` / `schemas/` 只能从各域 `schemas/enums.py` 引入这 21 个
>   枚举名，补 `api-layer-no-orm` 契约因 `allow_indirect_imports = True` 拦不住的一跳借用。

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run --all-packages --group dev python -m pytest tests/models/test_api_enum_parity.py -q
```
Expected: FAIL — 收集期 `ModuleNotFoundError: No module named 'miles_common.schemas.marketplace'`。这证明「新声明尚未存在」被测试覆盖到。

- [ ] **Step 3: 创建 `miles_common/schemas/chat_io.py`**

把 `packages/miles-core/src/miles_core/models/agent/chat_io.py` 的**全文逐字复制**为 `packages/miles-common/src/miles_common/schemas/chat_io.py`，然后**只**替换模块 docstring（第 1–8 行）为：

```python
"""智能体对话 IO 契约（中立域，L1/L3 共用）。

``ChatRequest``/``ChatResponse`` 与 ``ChatArtifact``/``PendingToolCall``/``ChatMediaIn``
为对话入口/响应与工具产出物的纯 pydantic 契约，供 L1（``tenant.agents.schemas.agent``
re-export）与 L3 ``integrations/langchain/tool_agent`` 共用。

定义自 ``tenant/agents/schemas/agent.py`` 经 ``miles_core.models.agent.chat_io`` 二次下沉
至此：API 声明层不得依赖 ORM 包（``.importlinter`` 契约 ``api-layer-no-orm``），而
``miles_core.models.agent`` 是 ORM 聚合包，整包禁令会连带禁止包内的纯 DTO。旧路径转
re-export 壳保持既有 import 稳定。
"""
```

其余（`from __future__ import annotations`、`uuid`、`pydantic`、`miles_common.schemas.media` 的 import，以及 5 个类的定义）**一字不改**。

- [ ] **Step 4: 创建 `miles_common/schemas/marketplace.py`**

把 `packages/miles-core/src/miles_core/models/marketplace/dto.py`（226 行）的**全文逐字复制**为 `packages/miles-common/src/miles_common/schemas/marketplace.py`，然后做**且仅做**以下两处改动：

(a) 替换模块 docstring（原第 1–6 行）为：

```python
"""应用市场 API DTO 与 API 侧枚举（admin 审核面与 tenant 市场面共用的中立模型）。

实现原居 ``tenant.marketplace.schemas.marketplace``，经 ``miles_core.models.marketplace.dto``
二次下沉至此（原因见 ``miles_common.schemas.chat_io``：``miles_core.models`` 是 ORM 聚合包，
整包被 ``.importlinter`` 契约 ``api-layer-no-orm`` 禁止）。依赖仅 pydantic/uuid/datetime +
中立模型，不含业务逻辑。

``MarketplaceAppStatus`` / ``MarketplaceAppVisibility`` 在此**独立声明**（不再从
``miles_core.models.marketplace.models`` re-export），与 ORM 侧逐字同形，一致性由
``tests/models/test_api_enum_parity.py`` 守卫。
"""
```

(b) 删除 `from miles_core.models.marketplace.models import MarketplaceAppStatus, MarketplaceAppVisibility` 这一行（若它因换行占多行，删整段），并在其原位置（`from miles_common.schemas.tag import TagRefOut` 之后、第一个 DTO 之前）插入：

```python
class MarketplaceAppStatus(enum.StrEnum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    PUBLISHED = "published"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class MarketplaceAppVisibility(enum.StrEnum):
    PUBLIC = "public"
    TENANT_ONLY = "tenant_only"
```

并在 import 段补 `import enum`（置于 `from datetime import datetime` 之前，与仓内「标准库 → 三方 → 本仓」分组一致）。

**成员名/顺序/值/类 docstring 必须与上表逐字相同**（类 docstring 仅 ORM 侧有的才抄，见 Task 2 Step 3 的说明）——这是本任务最容易出错的地方，Step 8 的平价测试会拦住。

- [ ] **Step 5: 把旧 `chat_io.py` 改成 re-export 壳**

`packages/miles-core/src/miles_core/models/agent/chat_io.py` 全文替换为：

```python
"""智能体对话 IO 契约的兼容壳（真实定义已下沉 ``miles_common.schemas.chat_io``）。

保留本路径与 ``__all__`` 以维持既有 import 稳定（``miles_ai`` 3 处、测试 3 处均指向此处；
portal 声明层 ``agents/schemas/agent.py`` 已直接指向 ``miles_common``，不经本壳）。
新代码请直接 import ``miles_common.schemas.chat_io``。

为何再下沉一层：本模块位于 ``miles_core.models.agent`` 包内，而该包整包被
``.importlinter`` 契约 ``api-layer-no-orm`` 禁止（按聚合包层级拦截，连带禁止包内纯 DTO）。
"""

from miles_common.schemas.chat_io import (
    ChatArtifact,
    ChatMediaIn,
    ChatRequest,
    ChatResponse,
    PendingToolCall,
)

__all__ = [
    "ChatArtifact",
    "ChatMediaIn",
    "ChatRequest",
    "ChatResponse",
    "PendingToolCall",
]
```

- [ ] **Step 6: 把旧 `dto.py` 改成 re-export 壳**

`packages/miles-core/src/miles_core/models/marketplace/dto.py` 全文替换为（`__all__` 必须与下方 17 个名字完全一致）：

```python
r"""应用市场 API DTO 的兼容壳（真实定义已下沉 ``miles_common.schemas.marketplace``）。

保留本路径与 ``__all__`` 以维持既有 import 稳定（admin services 1 处仍走本路径）。
新代码请直接 import ``miles_common.schemas.marketplace``。

**已知且经查证无消费者的表面变化**：原模块经 `from .models import ...` 顺带导出了
``MarketplaceAppStatus`` / ``MarketplaceAppVisibility``，本壳不再导出这两个 ORM 枚举
（它们已改为在 ``miles_common.schemas.marketplace`` 独立声明）。消费者为零已核实：
``rg -n 'marketplace\.dto import .*(Status|Visibility)'`` 无输出。DTO 定义模块不得反向
依赖 ORM 包。
"""

from miles_common.schemas.marketplace import (
    AppCategoryOut,
    AppInstallOut,
    AppInstallResult,
    AppRatingCreate,
    AppRatingOut,
    AppReviewBody,
    AppRollbackPreview,
    AppRollbackResult,
    AppUpgradePreview,
    AppUpgradeResult,
    MarketplaceAppCreate,
    MarketplaceAppCreateFromResources,
    MarketplaceAppDetail,
    MarketplaceAppOut,
    MarketplaceAppUpdate,
    UpgradeFieldChange,
    UpgradeResourceDiff,
)

__all__ = [
    "AppCategoryOut",
    "AppInstallOut",
    "AppInstallResult",
    "AppRatingCreate",
    "AppRatingOut",
    "AppReviewBody",
    "AppRollbackPreview",
    "AppRollbackResult",
    "AppUpgradePreview",
    "AppUpgradeResult",
    "MarketplaceAppCreate",
    "MarketplaceAppCreateFromResources",
    "MarketplaceAppDetail",
    "MarketplaceAppOut",
    "MarketplaceAppUpdate",
    "UpgradeFieldChange",
    "UpgradeResourceDiff",
]
```

- [ ] **Step 7: 迁移 3 处 `views/`/`schemas/` 消费者**

| 文件 | 旧 | 新 |
|---|---|---|
| `packages/miles-portal/src/miles_portal/tenant/agents/schemas/agent.py:15`（多行 import） | `from miles_core.models.agent.chat_io import (...)` | `from miles_common.schemas.chat_io import (...)` |
| `packages/miles-portal/src/miles_portal/tenant/marketplace/schemas/marketplace.py:9`（多行 import） | `from miles_core.models.marketplace.dto import (...)` | `from miles_common.schemas.marketplace import (...)` |
| `packages/miles-admin/src/miles_admin/app_ops/views/marketplace_review.py:15` | `from miles_core.models.marketplace.dto import AppReviewBody` | `from miles_common.schemas.marketplace import AppReviewBody` |

改 `agents/schemas/agent.py` 时**保留**该 import 行尾的 `# noqa: F401 — re-export（Chat* 五类）` 注释（Ruff 的 F401 是文件级判断，该注解承载 re-export 意图说明，勿删）。

同时改两处 docstring（否则文档指向已废弃路径）：

- `agents/schemas/agent.py` 第 6 行：`对话 IO 契约（Chat* 五类）定义已下沉 ``miles_core.models.agent.chat_io``，本处 re-export 保持 L1 import 路径。` → `对话 IO 契约（Chat* 五类）定义已下沉 ``miles_common.schemas.chat_io``（经 ``miles_core.models.agent.chat_io`` re-export 壳），本处 re-export 保持 L1 import 路径。`
- `marketplace/schemas/marketplace.py` 第 1–5 行整段 docstring 替换为：

```python
"""市场 API DTO 的 L1 兼容入口。

实现已下沉中立域 ``miles_common.schemas.marketplace``（admin 审核面与 tenant 市场面共用）；
本模块仅 re-export，保持既有 ``miles_portal.tenant.marketplace.schemas.marketplace`` import 稳定。
"""
```

- [ ] **Step 8: 补 shim 断言并跑测试**

`backend/tests/tenant/agents/test_agent_chat_io_shim.py`：在 import 段补
`from miles_common.schemas import chat_io as common_chat_io`，并在 `test_chat_io_shim_exports_same_objects` 末尾补一行断言，把「源头已到 `miles_common`」也锁住：

```python
    assert ChatRequest is common_chat_io.ChatRequest
```

运行：

```bash
uv run --all-packages --group dev python -m pytest tests/models/test_api_enum_parity.py tests/tenant/agents/test_agent_chat_io_shim.py -q
```
Expected: PASS。

- [ ] **Step 9: 五项验证 + 提交**

```bash
uv run --all-packages --group dev ruff check --fix . && uv run --all-packages --group dev ruff format .
uv run --all-packages --group dev python /tmp/scan_orm_sites.py   # 期望 TOTAL=25（28-3，DTO 三处已迁）
uv run --all-packages --group dev lint-imports                    # 期望 Contracts: 6 kept
uv run --all-packages --group dev python -m miles_server.scripts.export_openapi --check   # 期望 OpenAPI snapshot OK
git diff HEAD --stat -- openapi/openapi.snapshot.json             # 期望空输出
uv run --all-packages --group dev python -m pytest -q             # 期望 1127 passed
```

> `1127 = 1122 + 5`：本任务新增 5 个用例——`test_api_enum_is_an_independent_declaration` 2 例、`test_api_enum_matches_orm_verbatim` 2 例、`test_no_identity_comparison_on_enum_members` 1 例。数字对不上就停下核对，别改测试凑数。

```bash
git add -A
git commit -F - <<'EOF'
refactor(api): 下沉 chat_io 与 marketplace DTO 到 miles_common

为让 API 声明层不再依赖 ORM 包，嵌在 ORM 聚合包内的两个纯 DTO 模块必须先搬出
miles_core.models：契约按聚合包层级拦截（实测只列叶子会漏网），整包禁令会连带
禁止包内 DTO。

旧路径转 re-export 壳，miles_ai 与 admin services 的 import 零改动。marketplace
的 DTO 壳不再顺带导出两个 ORM 枚举（已查证消费者为零），枚举改在 miles_common
独立声明，由平价测试守卫。
EOF
```

---

### Task 2: 19 个 API 侧枚举声明 + 平价表补全

**Files:**
- Create: `backend/packages/miles-common/src/miles_common/schemas/api_enums.py`
- Create: `backend/packages/miles-portal/src/miles_portal/tenant/{a2a,agents,categories,compliance,flows,generative,hooks,kb,mcp,tasks,tools}/schemas/enums.py`（11 个）
- Create: `backend/packages/miles-admin/src/miles_admin/app_ops/schemas/enums.py`
- Modify: `backend/tests/models/test_api_enum_parity.py`（CASES 补到 21 对 + 完整性测试）

**Interfaces:**
- Produces: 13 个新模块，共 19 个 `enum.StrEnum` 类（详见下表）。Task 3 / Task 4 会把这些模块作为 import 目标。
- Consumes: Task 1 的 `miles_common.schemas.marketplace`（平价表要引用它的 2 个枚举）。

**本任务零引用变更**：只新增声明，不动任何现有 import。故 `TOTAL` 仍为 25。

- [ ] **Step 1: 写失败测试（CASES 补到 21 对 + 完整性守卫）**

在 `backend/tests/models/test_api_enum_parity.py` 的 import 段补：

```python
from miles_admin.app_ops.schemas import enums as admin_enums
from miles_admin.models import billing as orm_admin_billing
from miles_common.schemas import api_enums as common_enums
from miles_core.models import risk as orm_risk
from miles_core.models.agent import agent as orm_agent
from miles_core.models.compliance import constants as orm_compliance
from miles_core.models.flow import flow as orm_flow
from miles_core.models.kb import knowledge_base as orm_kb
from miles_core.models.meta import category as orm_category
from miles_core.models.model import catalog as orm_catalog
from miles_core.models.model import generative_job as orm_generative_job
from miles_core.models.platform import tenant as orm_tenant
from miles_core.models.task import task_record as orm_task_record
from miles_portal.tenant.a2a import models as orm_a2a
from miles_portal.tenant.a2a.schemas import enums as a2a_enums
from miles_portal.tenant.agents.schemas import enums as agents_enums
from miles_portal.tenant.categories.schemas import enums as categories_enums
from miles_portal.tenant.compliance.schemas import enums as compliance_enums
from miles_portal.tenant.flows.schemas import enums as flows_enums
from miles_portal.tenant.generative.schemas import enums as generative_enums
from miles_portal.tenant.hooks import models as orm_hooks
from miles_portal.tenant.hooks.schemas import enums as hooks_enums
from miles_portal.tenant.kb.schemas import enums as kb_enums
from miles_portal.tenant.mcp import models as orm_mcp
from miles_portal.tenant.mcp.schemas import enums as mcp_enums
from miles_portal.tenant.tasks.schemas import enums as tasks_enums
from miles_portal.tenant.tools import models as orm_tools
from miles_portal.tenant.tools.schemas import enums as tools_enums
```

把 `CASES` 替换为完整的 21 项（顺序按枚举名升序，便于比对）：

```python
CASES: list[tuple[str, type[enum.Enum], type[enum.Enum]]] = [
    ("A2aPeerStatus", a2a_enums.A2aPeerStatus, orm_a2a.A2aPeerStatus),
    ("AgentStatus", agents_enums.AgentStatus, orm_agent.AgentStatus),
    ("AgentType", agents_enums.AgentType, orm_agent.AgentType),
    ("BillStatus", admin_enums.BillStatus, orm_admin_billing.BillStatus),
    ("CategoryDomain", categories_enums.CategoryDomain, orm_category.CategoryDomain),
    ("DocumentStatus", kb_enums.DocumentStatus, orm_kb.DocumentStatus),
    ("FlowStatus", flows_enums.FlowStatus, orm_flow.FlowStatus),
    ("GenerativeJobStatus", generative_enums.GenerativeJobStatus, orm_generative_job.GenerativeJobStatus),
    ("HookScope", hooks_enums.HookScope, orm_hooks.HookScope),
    ("HookTrigger", hooks_enums.HookTrigger, orm_hooks.HookTrigger),
    ("HookType", hooks_enums.HookType, orm_hooks.HookType),
    ("MarketplaceAppStatus", common_marketplace.MarketplaceAppStatus, orm_marketplace.MarketplaceAppStatus),
    ("MarketplaceAppVisibility", common_marketplace.MarketplaceAppVisibility, orm_marketplace.MarketplaceAppVisibility),
    ("McpStatus", mcp_enums.McpStatus, orm_mcp.McpStatus),
    ("ModelCapabilityType", common_enums.ModelCapabilityType, orm_catalog.ModelCapabilityType),
    ("ModelVendor", common_enums.ModelVendor, orm_catalog.ModelVendor),
    ("RiskSeverity", admin_enums.RiskSeverity, orm_risk.RiskSeverity),
    ("SensitiveAction", compliance_enums.SensitiveAction, orm_compliance.SensitiveAction),
    ("TaskStatus", tasks_enums.TaskStatus, orm_task_record.TaskStatus),
    ("TenantStatus", common_enums.TenantStatus, orm_tenant.TenantStatus),
    ("ToolType", tools_enums.ToolType, orm_tools.ToolType),
]
```

并在文件末尾追加：

```python
def test_parity_table_covers_exactly_21_enums():
    """防有人删表项「修好」测试：表必须恰好 21 项且无重名。"""
    assert len(CASES) == 21, f"平价表应恰有 21 项，实际 {len(CASES)}"
    assert len({name for name, _, _ in CASES}) == 21
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run --all-packages --group dev python -m pytest tests/models/test_api_enum_parity.py -q
```
Expected: FAIL — 收集期 `ModuleNotFoundError`（19 个新模块尚不存在）。

- [ ] **Step 3: 创建 13 个枚举声明文件**

每个文件的**类体逐字照抄**下表（成员名、顺序、值三项都必须一致，外加 ORM 侧的类 docstring，见下方说明）。每个文件的模块 docstring 统一用：

```python
"""<域> API 侧枚举声明。

与 ORM 侧 ``<ORM 模块>`` 逐字同形（成员名/顺序/值/类 docstring），因 API 声明层不得依赖 ORM 模块
（``.importlinter`` 契约 ``api-layer-no-orm``）而独立声明；两侧一致性由
``tests/models/test_api_enum_parity.py`` 守卫。
"""
```

import 段统一为 `import enum`（其后空两行再接第一个类）。

> **类 docstring（最易漏的一项）**：Pydantic 会把 enum 类 docstring 渲染成 schema 的 `description`，
> 故 ORM 侧**有**类 docstring 的枚举必须逐字照抄，ORM 侧**没有**的不许凭空添加 —— 两者都会让
> `openapi.snapshot.json` 漂移。21 个枚举中恰好 5 个有：`CategoryDomain`、`DocumentStatus`、
> `HookTrigger`、`McpStatus`、`SensitiveAction`。Task 3 实测：漏抄这 5 条会让
> `export_openapi --check` 报 drift（差值恰是 5 行 `"description"`）。

| # | 新文件（`packages/` 下） | ORM 定义处（docstring 里引用） | 类体 |
|---|---|---|---|
| 1 | `miles-common/src/miles_common/schemas/api_enums.py` | `miles_core.models.platform.tenant`、`miles_core.models.model.catalog` | 见下方「api_enums」 |
| 2 | `miles-portal/src/miles_portal/tenant/a2a/schemas/enums.py` | `miles_portal.tenant.a2a.models` | `A2aPeerStatus`（4） |
| 3 | `miles-portal/src/miles_portal/tenant/agents/schemas/enums.py` | `miles_core.models.agent.agent` | `AgentStatus`（2）、`AgentType`（2） |
| 4 | `miles-portal/src/miles_portal/tenant/categories/schemas/enums.py` | `miles_core.models.meta.category` | `CategoryDomain`（4） |
| 5 | `miles-portal/src/miles_portal/tenant/compliance/schemas/enums.py` | `miles_core.models.compliance.constants` | `SensitiveAction`（2） |
| 6 | `miles-portal/src/miles_portal/tenant/flows/schemas/enums.py` | `miles_core.models.flow.flow` | `FlowStatus`（2） |
| 7 | `miles-portal/src/miles_portal/tenant/generative/schemas/enums.py` | `miles_core.models.model.generative_job` | `GenerativeJobStatus`（5） |
| 8 | `miles-portal/src/miles_portal/tenant/hooks/schemas/enums.py` | `miles_portal.tenant.hooks.models` | `HookType`（2）、`HookTrigger`（7）、`HookScope`（5） |
| 9 | `miles-portal/src/miles_portal/tenant/kb/schemas/enums.py` | `miles_core.models.kb.knowledge_base` | `DocumentStatus`（6） |
| 10 | `miles-portal/src/miles_portal/tenant/mcp/schemas/enums.py` | `miles_portal.tenant.mcp.models` | `McpStatus`（3） |
| 11 | `miles-portal/src/miles_portal/tenant/tasks/schemas/enums.py` | `miles_core.models.task.task_record` | `TaskStatus`（5） |
| 12 | `miles-portal/src/miles_portal/tenant/tools/schemas/enums.py` | `miles_portal.tenant.tools.models` | `ToolType`（2） |
| 13 | `miles-admin/src/miles_admin/app_ops/schemas/enums.py` | `miles_admin.models.billing`、`miles_core.models.risk` | `RiskSeverity`（4）、`BillStatus`（4） |

「api_enums」内容（文件 1 的三个类，顺序固定为 `TenantStatus` → `ModelVendor` → `ModelCapabilityType`）：

```python
class TenantStatus(enum.StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    TRIAL = "trial"


class ModelVendor(enum.StrEnum):
    DEEPSEEK = "deepseek"
    DOUBAO = "doubao"
    QWEN = "qwen"
    OPENAI = "openai"
    OTHER = "other"


class ModelCapabilityType(enum.StrEnum):
    LLM = "llm"
    REASONING = "reasoning"
    VISION = "vision"
    EMBEDDING = "embedding"
    RERANK = "rerank"
    IMAGE_GEN = "image_gen"
    VIDEO_GEN = "video_gen"
    ASR = "asr"
    TTS = "tts"
    OTHER = "other"
```

其余 18 个类的类体（逐字照抄；`enum.StrEnum` 的成员值一律双引号；ORM 侧带类 docstring 的 5 个类须连 docstring 一起照抄）：

```python
class A2aPeerStatus(enum.StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    ERROR = "error"
    INACTIVE = "inactive"


class AgentStatus(enum.StrEnum):
    ENABLED = "enabled"
    DISABLED = "disabled"


class AgentType(enum.StrEnum):
    CUSTOM = "custom"
    A2A = "a2a"


class CategoryDomain(enum.StrEnum):
    """工作台资源域；与列表 Tab、校验时的 domain 参数一致。"""

    AGENT = "agent"
    PROMPT = "prompt"
    SKILL = "skill"
    TOOL = "tool"


class SensitiveAction(enum.StrEnum):
    """敏感词处置动作。"""

    WARN = "warn"
    BLOCK = "block"


class FlowStatus(enum.StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"


class GenerativeJobStatus(enum.StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class HookType(enum.StrEnum):
    HTTP = "http"
    PYTHON = "python"


class HookTrigger(enum.StrEnum):
    """挂载时机：调用、推理、工具、错误等关键节点。"""

    BEFORE_CALL = "before_call"
    AFTER_CALL = "after_call"
    BEFORE_REASONING = "before_reasoning"
    AFTER_REASONING = "after_reasoning"
    BEFORE_TOOL = "before_tool"
    AFTER_TOOL = "after_tool"
    ON_ERROR = "on_error"


class HookScope(enum.StrEnum):
    GLOBAL = "global"
    AGENT = "agent"
    FLOW = "flow"
    TOOL = "tool"
    APP = "app"


class DocumentStatus(enum.StrEnum):
    """入库流水线状态（PENDING → PARSING → EMBEDDING → READY）。"""

    PENDING = "pending"
    PARSING = "parsing"
    EMBEDDING = "embedding"
    READY = "ready"
    PARSE_FAILED = "parse_failed"
    EMBED_FAILED = "embed_failed"


class McpStatus(enum.StrEnum):
    """同步与可用性状态，供工作台卡片展示。"""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


class TaskStatus(enum.StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ToolType(enum.StrEnum):
    HTTP = "http"
    SCRIPT = "script"


class RiskSeverity(enum.StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class BillStatus(enum.StrEnum):
    DRAFT = "draft"
    ISSUED = "issued"
    PAID = "paid"
    VOID = "void"
```

> 复核方式：若对任一成员值或类 docstring 有疑问，以 ORM 源为准逐字对照 ——
> `rg -n -A8 'class (A2aPeerStatus|AgentStatus|AgentType|BillStatus|CategoryDomain|DocumentStatus|FlowStatus|GenerativeJobStatus|HookScope|HookTrigger|HookType|MarketplaceAppStatus|MarketplaceAppVisibility|McpStatus|ModelCapabilityType|ModelVendor|RiskSeverity|SensitiveAction|TaskStatus|TenantStatus|ToolType)\(enum\.StrEnum\)' packages/*/src`

- [ ] **Step 4: 运行测试确认通过**

```bash
uv run --all-packages --group dev python -m pytest tests/models/test_api_enum_parity.py -q
```
Expected: PASS，**44 例** = 平价 21 + 独立声明 21 + 完整性 1 + 身份比较守卫 1。

- [ ] **Step 5: 五项验证 + 提交**

```bash
uv run --all-packages --group dev ruff check --fix . && uv run --all-packages --group dev ruff format .
uv run --all-packages --group dev python /tmp/scan_orm_sites.py    # 期望 TOTAL=25（本任务不改引用）
uv run --all-packages --group dev lint-imports                     # 期望 6 kept
uv run --all-packages --group dev python -m miles_server.scripts.export_openapi --check   # 期望 OK
git diff HEAD --stat -- openapi/openapi.snapshot.json              # 期望空（新声明尚无人 import，不影响 schema）
uv run --all-packages --group dev python -m pytest -q              # 期望 1166 passed（1122 + 44）
```

```bash
git add -A
git commit -F - <<'EOF'
feat(api): 为 21 个持久化枚举建立 API 侧独立声明

API 声明层不得依赖 ORM 包，故各域在 schemas/enums.py 独立声明枚举，基类/成员名/顺序/
值/类 docstring 逐字复制 ORM 侧（类 docstring 会渲染进 schema description）。跨端共用
的 3 个（TenantStatus、ModelVendor、ModelCapabilityType）放 miles_common，因 portal 与
admin 互不可见。

新增平价测试逐成员比对两份声明，并守卫「不得对枚举成员做 is 比较」——两份声明是
不同类，str 语义下 == / hash / format 都按值成立，唯独 is 跨类恒为 False。
EOF
```

---

### Task 3: portal 侧 17 处枚举引用迁移 + `from_model` 去注解

**Files:**
- Modify: 17 个 portal `views/`/`schemas/` 文件（下表）
- Modify: `backend/packages/miles-portal/src/miles_portal/tenant/agents/schemas/schedule_run.py`

**Interfaces:**
- Consumes: Task 2 的 11 个 portal `schemas/enums.py` 与 `miles_common.schemas.api_enums`。
- Produces: portal 侧 `views/`/`schemas/` 对 ORM 包的直接 import 归零。

- [ ] **Step 1: 逐处替换 import**

下表「行」列是**改造前审计快照**（迁移动工前扫到的原始行号；如 `agents/schemas/agent.py` 的 14 在 Task 1 docstring + Task 3 isort 后已下移到 22）——**不要**拿它去当前文件里定位。

| 文件（`packages/miles-portal/src/miles_portal/tenant/`） | 行（改造前快照） | 旧 | 新 |
|---|---|---|---|
| `a2a/schemas/peer.py` | 12 | `from miles_portal.tenant.a2a.models import A2aPeerStatus` | `from miles_portal.tenant.a2a.schemas.enums import A2aPeerStatus` |
| `agents/schemas/agent.py` | 14 | `from miles_core.models.agent import AgentStatus, AgentType` | `from miles_portal.tenant.agents.schemas.enums import AgentStatus, AgentType` |
| `agents/views/agents.py` | 17 | `from miles_core.models.agent import AgentType` | `from miles_portal.tenant.agents.schemas.enums import AgentType` |
| `categories/schemas/category.py` | 8 | `from miles_core.models.meta.category import CategoryDomain` | `from miles_portal.tenant.categories.schemas.enums import CategoryDomain` |
| `categories/views/categories.py` | 17 | `from miles_core.models.meta.category import CategoryDomain` | `from miles_portal.tenant.categories.schemas.enums import CategoryDomain` |
| `compliance/schemas/compliance.py` | 8 | `from miles_portal.tenant.compliance.models import SensitiveAction` | `from miles_portal.tenant.compliance.schemas.enums import SensitiveAction` |
| `flows/schemas/flow.py` | 9 | `from miles_core.models.flow import FlowStatus` | `from miles_portal.tenant.flows.schemas.enums import FlowStatus` |
| `generative/schemas/job.py` | 8 | `from miles_core.models.model.generative_job import GenerativeJobStatus` | `from miles_portal.tenant.generative.schemas.enums import GenerativeJobStatus` |
| `generative/views/jobs.py` | 14 | `from miles_core.models.model.generative_job import GenerativeJobStatus` | `from miles_portal.tenant.generative.schemas.enums import GenerativeJobStatus` |
| `hooks/schemas/hook.py` | 8 | `from miles_portal.tenant.hooks.models import HookScope, HookTrigger, HookType` | `from miles_portal.tenant.hooks.schemas.enums import HookScope, HookTrigger, HookType` |
| `kb/schemas/kb.py` | 25 | `from miles_core.models.kb import DocumentStatus` | `from miles_portal.tenant.kb.schemas.enums import DocumentStatus` |
| `mcp/schemas/mcp.py` | 13 | `from miles_portal.tenant.mcp.models import McpStatus` | `from miles_portal.tenant.mcp.schemas.enums import McpStatus` |
| `models/schemas/model.py` | 8 | `from miles_core.models.model.catalog import ModelCapabilityType, ModelVendor` | `from miles_common.schemas.api_enums import ModelCapabilityType, ModelVendor` |
| `system/schemas/tenant.py` | 8 | `from miles_core.models.platform.tenant import TenantStatus` | `from miles_common.schemas.api_enums import TenantStatus` |
| `tasks/schemas/task.py` | 8 | `from miles_core.models.task.task_record import TaskStatus` | `from miles_portal.tenant.tasks.schemas.enums import TaskStatus` |
| `tasks/views/tasks.py` | 10 | `from miles_core.models.task.task_record import TaskStatus` | `from miles_portal.tenant.tasks.schemas.enums import TaskStatus` |
| `tools/schemas/tools.py` | 11 | `from miles_portal.tenant.tools.models import ToolType` | `from miles_portal.tenant.tools.schemas.enums import ToolType` |

替换后由 Ruff 的 isort 归位（`miles_common` 组会排到 `miles_core` 之前），故 Step 2 先跑 `--fix` 再核 diff。

- [ ] **Step 2: `schedule_run.py` 去掉 ORM 实体注解**

`agents/schemas/schedule_run.py`：
1. 删除第 10 行 `from miles_core.models.agent.schedule_run import AgentScheduleRun`；
2. `def from_model(cls, entity: AgentScheduleRun) -> AgentScheduleRunOut:` 改为 `def from_model(cls, entity) -> AgentScheduleRunOut:`——与同目录既有写法一致（`agents/schemas/schedule.py:61` 的 `def from_model(cls, entity) -> "AgentScheduleOut"` 本就不注解 ORM 实体）；
3. 该方法的 docstring 若提及 `AgentScheduleRun` 类型注解，改为说明「入参为 ORM 实体，不注解以避免 API 层依赖 ORM」。

**不要**用 `TYPE_CHECKING` 包裹，也**不要**新建 `Protocol`——实测 `TYPE_CHECKING` 与函数内 import 同样被契约判违规（设计 §3.3 第 4 条）。

- [ ] **Step 3: 跑迁移验证**

```bash
uv run --all-packages --group dev ruff check --fix . && uv run --all-packages --group dev ruff format .
uv run --all-packages --group dev python /tmp/scan_orm_sites.py    # 期望 TOTAL=7（25-18）
git diff HEAD --stat -- openapi/openapi.snapshot.json              # 期望空
uv run --all-packages --group dev python -m pytest -q              # 期望 passed，无 failed
```

`TOTAL=7` 即剩余 admin 侧 7 处（Task 4 处理）。若数字不符，把 `git diff` 里多改/少改的行与上表逐条对齐。

- [ ] **Step 4: 五项门禁 + 提交**

```bash
uv run --all-packages --group dev ruff format --check .
uv run --all-packages --group dev ruff check .
uv run --all-packages --group dev lint-imports                    # 期望 6 kept
uv run --all-packages --group dev python -m miles_server.scripts.export_openapi --check   # 期望 OK
uv run --all-packages --group dev python -m pytest -q
```

```bash
git add -A
git commit -F - <<'EOF'
refactor(portal): 声明层改引 API 侧枚举，解耦 ORM 包

17 处 views/schemas 的枚举 import 从 ORM 包指向本域 schemas/enums.py（跨端共用的
TenantStatus 等指向 miles_common）。schedule_run.from_model 去掉 ORM 实体注解，
与同目录既有写法一致——实测 TYPE_CHECKING 与函数内 import 同样被契约判违规，
故不做注解逃逸。

OpenAPI 快照逐字节不变。
EOF
```

---

### Task 4: admin 侧 7 处枚举引用迁移

**Files:**
- Modify: 7 个 admin `views/`/`schemas/` 文件（下表）

**Interfaces:**
- Consumes: Task 2 的 `miles_admin.app_ops.schemas.enums` 与 `miles_common.schemas.api_enums`。
- Produces: admin 侧归零 → 全仓 `views/`/`schemas/` 对 ORM 包的直接 import 为 0。

- [ ] **Step 1: 逐处替换 import**

| 文件（`packages/miles-admin/src/miles_admin/app_ops/`） | 行 | 旧 | 新 |
|---|---|---|---|
| `schemas/billing.py` | 9 | `from miles_admin.models import BillStatus` | `from miles_admin.app_ops.schemas.enums import BillStatus` |
| `schemas/model_catalog.py` | 8 | `from miles_core.models.model.catalog import ModelCapabilityType, ModelVendor` | `from miles_common.schemas.api_enums import ModelCapabilityType, ModelVendor` |
| `schemas/risk.py` | 8 | `from miles_admin.models import RiskSeverity` | `from miles_admin.app_ops.schemas.enums import RiskSeverity` |
| `schemas/tenant.py` | 8 | `from miles_core.models.platform.tenant import TenantStatus` | `from miles_common.schemas.api_enums import TenantStatus` |
| `views/billing.py` | 13 | `from miles_admin.models import BillStatus` | `from miles_admin.app_ops.schemas.enums import BillStatus` |
| `views/risk.py` | 12 | `from miles_admin.models import RiskSeverity` | `from miles_admin.app_ops.schemas.enums import RiskSeverity` |
| `views/tenants.py` | 16 | `from miles_core.models.platform.tenant import TenantStatus` | `from miles_common.schemas.api_enums import TenantStatus` |

- [ ] **Step 2: 跑迁移验证（关键：TOTAL 必须为 0）**

```bash
uv run --all-packages --group dev ruff check --fix . && uv run --all-packages --group dev ruff format .
uv run --all-packages --group dev python /tmp/scan_orm_sites.py    # 期望 TOTAL=0
git diff HEAD --stat -- openapi/openapi.snapshot.json              # 期望空
uv run --all-packages --group dev python -m pytest -q              # 期望 passed
```

- [ ] **Step 3: 五项门禁 + 提交**

```bash
uv run --all-packages --group dev ruff format --check .
uv run --all-packages --group dev ruff check .
uv run --all-packages --group dev lint-imports                    # 期望 6 kept（契约尚未加）
uv run --all-packages --group dev python -m miles_server.scripts.export_openapi --check   # 期望 OK
uv run --all-packages --group dev python -m pytest -q
```

```bash
git add -A
git commit -F - <<'EOF'
refactor(admin): 声明层改引 API 侧枚举，解耦 ORM 包

admin app_ops 的 7 处 views/schemas 枚举 import 从 miles_admin.models 与
miles_core.models 指向本层 schemas/enums.py 或 miles_common。至此全仓
views/schemas 对 ORM 包的直接依赖归零（AST 复算 TOTAL=0）。

OpenAPI 快照逐字节不变。
EOF
```

---

### Task 5: `.importlinter` 第 7 条契约 + 四项敏感度对照

**Files:**
- Modify: `backend/.importlinter`（新增第 7 条契约）

**Interfaces:**
- Consumes: Task 3 / Task 4 完成的零违规现状（契约加在此后才会 `KEPT`，无需提交过任何红灯门禁的中间态）。
- Produces: 硬禁边界的契约，供后续所有改动长期生效。

- [ ] **Step 1: 追加契约**

在 `backend/.importlinter` 末尾追加（`forbidden_modules` 已按设计 §3.3 第 5 条收敛为父聚合）：

```ini
# API 声明层的目录级约束：views/schemas 不得 import 承载 SQLAlchemy 实体或持久化枚举的模块。
# 必要性：包分层方向契约管不到这条边（miles_portal 用 miles_core.models 是被允许的——
# services/repositories 必须用 ORM 查询），故需要包内的目录级约束。
[importlinter:contract:api-layer-no-orm]
name = API 声明层不得依赖 ORM
type = forbidden
source_modules =
    miles_portal.tenant.*.views
    miles_portal.tenant.*.schemas
    miles_admin.app_ops.views
    miles_admin.app_ops.schemas
    miles_admin.app_sys.views
    miles_admin.app_sys.schemas
    miles_openapi.views
# 必须列到**最外层胖聚合**：
# 1) from miles_core.models.agent import X 的图边目标是包 __init__ 而非叶子模块，只列叶子会漏网；
# 2) miles_core/models/__init__.py 自身 re-export 了 43 个名字（含 8 个持久化枚举）且带 __all__，
#    故 from miles_core.models import AgentStatus 的图边目标是 miles_core.models —— 只列子域包会静默放过。
#    （数字实测：`len(miles_core.models.__all__)` == 43；被 re-export 的持久化枚举恰 8 个：
#      AgentStatus / CategoryDomain / DocumentStatus / FlowStatus / GenerativeJobStatus /
#      MarketplaceAppStatus / MarketplaceAppVisibility / TaskStatus。）
#    （实测：from miles_core.models import agent 这种取子模块的写法会被解析到子模块边，故逃逸面仅限父包自身属性。）
# 代价是整包禁令：views/schemas 也不得引用 miles_core.models.base / media.reader / tool.parameters 等
# 非 ORM 模块。实测当前零引用；若将来确需引用，正解是把该中立模块下沉 miles_common，而不是放宽契约。
# 因此被禁包内的纯 DTO 会被一并禁止 —— 这就是 chat_io / marketplace.dto 下沉的来由。
forbidden_modules =
    miles_core.models
    miles_admin.models
    miles_portal.tenant.a2a.models
    miles_portal.tenant.audit_log.models
    miles_portal.tenant.compliance.models
    miles_portal.tenant.hooks.models
    miles_portal.tenant.marketplace.models
    miles_portal.tenant.mcp.models
    miles_portal.tenant.prompts.models
    miles_portal.tenant.skills.models
    miles_portal.tenant.tools.models
# 只判直接导入：不加会沿 views → miles_core.deps → miles_core.models.* 误报。
# 代价：经中间模块的一跳借用（如 from ...agents.meta import AgentStatus）不被本契约拦截 ——
# 那段由 tests/models/test_api_enum_parity.py::test_enum_names_imported_only_from_allowlisted_modules
# 的名称级守卫补上（按「枚举名 + 来源模块白名单」判定，不依赖图边），两者合起来才完整。
allow_indirect_imports = True
```

- [ ] **Step 2: 跑契约**

```bash
uv run --all-packages --group dev lint-imports
```
Expected: `Contracts: 7 kept, 0 broken.`

若 BROKEN，输出会逐个列出漏网文件与图边 —— 按它回到 Task 3 / Task 4 补齐，不要在契约里加 `ignore_imports`。

- [ ] **Step 3: 敏感度对照（四项，缺一不可）**

门禁可能形同虚设，故必须证明它们**会失败**。四项都在临时改动后**完整还原**：

1. **契约敏感度（子模块边）**：把 `packages/miles-portal/src/miles_portal/tenant/agents/schemas/agent.py` **第 22 行**（`from miles_portal.tenant.agents.schemas.enums import AgentStatus, AgentType`；行号在 Task 1/3 的 docstring 与 isort 变动后由 14 下移到 22，**按内容定位**）临时改回 `from miles_core.models.agent import AgentStatus, AgentType` → `lint-imports` 必须报出该文件；还原后重新 `7 kept`。
2. **契约敏感度（父聚合属性边，本设计专门堵的那个洞）**：把同一行临时改为 **`from miles_core.models import AgentStatus`**（只用 `AgentStatus` —— 实测它是那 8 个被父包 re-export 的持久化枚举之一；**不要**用 `AgentStatus, AgentType`，`AgentType` **未被** `miles_core.models` 父包 re-export，那样写导入语义本身就不成立）→ `lint-imports` **必须也报出**；还原后重新 `7 kept`。这一项失败即说明收敛清单没生效。
3. **快照敏感度**：把 `packages/miles-portal/src/miles_portal/tenant/agents/schemas/enums.py` 的 `ENABLED = "enabled"` 临时改为 `"enable"` → `python -m miles_server.scripts.export_openapi --check` 必须非零退出（报 snapshot drift）；还原后必须 `OpenAPI snapshot OK`。
4. **平价测试敏感度**：再对 `packages/miles-portal/src/miles_portal/tenant/agents/schemas/enums.py` 做与第 3 项相同的临时改动（`ENABLED = "enable"`）→ `pytest tests/models/test_api_enum_parity.py -q` 必须失败，且失败信息**逐字包含** `AgentStatus.ENABLED 的 API 值 'enable' != ORM 值 'enabled'`；还原后必须通过。

还原后复核：

```bash
git diff HEAD --stat        # 期望只剩 .importlinter 一个文件
uv run --all-packages --group dev lint-imports
uv run --all-packages --group dev python -m pytest tests/models/test_api_enum_parity.py -q
```

- [ ] **Step 4: 五项门禁 + 提交**

```bash
uv run --all-packages --group dev ruff format --check .
uv run --all-packages --group dev ruff check .
uv run --all-packages --group dev lint-imports                    # 期望 7 kept, 0 broken
uv run --all-packages --group dev python -m miles_server.scripts.export_openapi --check
uv run --all-packages --group dev python -m pytest -q
```

```bash
git add -A
git commit -F - <<'EOF'
feat(lint): 新增契约禁止 API 声明层依赖 ORM

包分层方向契约管不到这条边——portal 内部用 miles_core.models 是被允许的（services
必须用 ORM 查询），故补一条目录级约束，覆盖 portal 全域 views/schemas、admin
app_ops/app_sys 与开放面。

清单列到最外层胖聚合：写实施计划前的沙箱探针发现，只列子域包时
from miles_core.models import AgentStatus 会静默通过，而它正是本仓惯用写法
（该 __init__ re-export 了 43 个名字含 8 个枚举）。收敛后清单从 20 条降到 10 条，
且 miles_core 下新增模块自动被拦。
EOF
```

---

### Task 6: 全支线终检 + spec 回填

**Files:**
- Modify: `docs/superpowers/specs/2026-09-17-api-layer-orm-decoupling-design.md`（修订记录 + 实测值回填）

**Interfaces:**
- Consumes: Task 1–5 的全部产出。
- Produces: 可合并的分支与与实现一致的 spec。

- [ ] **Step 1: 终检清单（逐条给出实测输出，不得凭记忆）**

```bash
BASE=$(git merge-base main HEAD)

# 1) 违规面归零
uv run --all-packages --group dev python /tmp/scan_orm_sites.py          # 期望 TOTAL=0

# 2) 契约：新 7 条全 kept，原 6 条未被误伤
uv run --all-packages --group dev lint-imports                            # 期望 Contracts: 7 kept, 0 broken

# 3) 快照逐字节不变
git diff --stat "$BASE" -- openapi/openapi.snapshot.json                  # 期望空输出

# 4) ORM 侧零改动：只允许两个 re-export 壳
git diff --name-only "$BASE" -- packages/miles-core/src/miles_core/models/
#    期望恰好两行：.../agent/chat_io.py 与 .../marketplace/dto.py
git diff --name-only "$BASE" -- alembic/                                  # 期望空（迁移目录零改动）
git diff "$BASE" -- packages/miles-core/src/miles_core/models/ \
  | (rg -c '^[+-].*(\(enum\.StrEnum\)|values_callable|SAEnum)' || echo 0)  # 期望 0：枚举定义/列类型零改动
git diff "$BASE" -- pyproject.toml | (rg '^[+-].*values_callable\s*=' || echo 0)   # 期望 0

# 5) 平价表覆盖数
uv run --all-packages --group dev python -m pytest tests/models/test_api_enum_parity.py -q   # 期望 45 passed

# 6) 五项门禁
uv run --all-packages --group dev ruff format --check .
uv run --all-packages --group dev ruff check .
uv run --all-packages --group dev lint-imports
uv run --all-packages --group dev python -m miles_server.scripts.export_openapi --check
uv run --all-packages --group dev python -m pytest -q                     # 记录实测 passed 数
```

- [ ] **Step 2: 文档陈旧清扫（用户 2026-09-17 裁决「全做」，执行前逐条复核）**

本计划的文档在 6 个任务推进中被反复回填，留下了一批与最终代码不符的陈述。**内嵌代码块必须可照抄执行**，否则后人抄下来会得到与 docstring 声明不符的实现。逐条处理：

| # | 位置 | 问题 | 处置 |
|---|---|---|---|
| 1 | plan `~:143`、`~:190`、`~:200` | 内嵌的 `_IDENTITY_COMPARISON` 判据示例仍是**旧的 `import re` + 正则**版本，而实际代码已是 AST 判据（`_enum_class_of` 覆盖 `Name.MEMBER` / `alias.Class.MEMBER` / `pkg.mod.Class.MEMBER`） | 把示例同步为 `tests/models/test_api_enum_parity.py` 的实际实现，或删掉内嵌实现、改为指向真实文件 |
| 2 | plan `~:85` | `marketpalce` 拼写（应为 `marketplace`） | 直接改 |
| 3 | plan `~:157-167` | 同一代码块内：模块 docstring（`~:126-129`）与 `test_api_enum_matches_orm_verbatim` 的 docstring（`~:178-181`）已改成「五项全等」，但内嵌的 `_mismatch_report` 函数体仍是三项（无基类分支、无 docstring 分支） | 与第 1 条同法同步（或改为指向真实文件） |
| 4 | `categories/schemas/enums.py:3`、`compliance/schemas/enums.py:3`、`hooks/schemas/enums.py:3`、`kb/schemas/enums.py:3`、`mcp/schemas/enums.py:3` | 模块 docstring 仍写「逐字同形（成员名/顺序/值）」，而这 5 个恰是补了类 docstring 的，描述偏低 | 5 处各补为「成员名/顺序/值/类 docstring」；并同步 plan 模板 `~:533` 的同句措辞（plan-mandated 陈旧的源头） |
| 5 | plan `~:756` 与 spec `~:65` | 仍写 `agents/schemas/agent.py | 14`，而 Task 5 勘误只改了执行指引（plan `~:944` → 22）。同一文档同一行号出现 14/22 两个值 | 若这两处是「改造前审计快照」，加「（改造前快照）」消歧；否则一并勘误为 22 |
| 6 | plan/spec 中所有「45 个名字」类表述 | Task 5 已勘误为 43 | 全支线 `rg` 复核，确认无残留 |

**要求**：清扫后 plan 内的所有内嵌代码块必须与仓库实际文件一致（建议逐块 diff 比对，而不是凭记忆）；spec 同理。清扫产生的改动与 Step 3 的回填可放在同一次 docs 提交里。

- [ ] **Step 3: 回填 spec 修订记录**

在 `docs/superpowers/specs/2026-09-17-api-layer-orm-decoupling-design.md` 的 §10 追加一条实测记录，内容必须包含：

- 实际新增文件数（设计 §5.5 预估 15 个：11 portal + 3 `miles_common` + 1 admin）；
- 实际修改文件数（预估 27）；
- `pytest` 实测 passed 数（基线 1122；终态 **1167** = 1122 + 平价/独立声明参数化例 + Task 3 加固 + Task 5b 的名称级守卫）；
- 终检 6 项的实测输出摘要（尤其 `TOTAL=0`、`7 kept`、快照 diff 为空、ORM 侧只有两个壳文件）；
- **Task 5b 追加的两道互补门禁**：`import-linter` 契约 `api-layer-no-orm` 只能拦直接依赖（因其必须设 `allow_indirect_imports = True`），一跳借用由 `test_api_enum_parity.py::test_enum_names_imported_only_from_allowlisted_modules` 的名称级守卫补上；两者职责互补，缺一即有静默漏洞。附其已知边界（`from X import meta` 再 `meta.AgentStatus` 等形态不受覆盖）。
- 与预估不符之处及其原因。

- [ ] **Step 4: 提交**

```bash
git add -A
git commit -F - <<'EOF'
docs(spec): 回填 API 层解耦的实测数据

记录实际文件数、门禁输出与 pytest 实测数，并列出与预估不符之处及原因，避免
spec 停留在推算值。
EOF
```

- [ ] **Step 5: 终检后交付**

向调用者报告：终检 6 项的实测输出、`TOTAL=0` 与 `7 kept` 的证据、快照 diff 为空、ORM 侧改动仅两壳，以及分支名供合并评审。**不要**自行合并到 `main`。

---

## 附：常见失败与处置

| 现象 | 原因 | 处置 |
|---|---|---|
| `ModuleNotFoundError: No module named 'miles_core'` | 用了裸 `python -m pytest` | 改 `uv run --all-packages --group dev python -m pytest -q` |
| 裸 `pytest` 收集期报 9 个错 | 本仓既存缺陷（无 `__init__.py` 与 `pythonpath` 配置），与本设计无关 | 用上面的 `python -m pytest` 形式；**不要**顺手修 pytest 配置 |
| 平价测试报「成员名或顺序不一致」/「类 docstring … != …」 | 声明时漏抄、错序，或漏抄 ORM 侧的类 docstring | 以 ORM 源为唯一准，逐字对照（Task 2 Step 3 的 `rg` 复核命令） |
| `lint-imports` BROKEN 且指向没改过的文件 | 某处 import 被漏迁 | 按输出回到 Task 3 / Task 4 补；**不要**加 `ignore_imports` |
| `export_openapi --check` 报 drift | 某枚举的值/顺序与 ORM 不一致（Pydantic 会塌成 `X__1` 组件名）、漏抄/擅加枚举类 docstring（Pydantic 渲染成 `description`），或某 schema 字段类型被改 | 先跑平价测试定位到具体枚举；若差值恰是若干行 `"description"`，即为类 docstring 漏抄；快照**不要**用 `--write` 覆盖 |
| `ruff check` 报 re-export 壳的 F401 | 壳缺 `__all__` | 按 Global Constraints 补 `__all__` |
