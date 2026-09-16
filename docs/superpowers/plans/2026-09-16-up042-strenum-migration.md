# 启用 UP042：32 处枚举迁移到 StrEnum 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 32 个 `(str, Enum)` 枚举迁移为 `StrEnum` 并在 ruff 中启用 `UP042`，同时用契约测试锁住唯一的行为变化与 SQLAlchemy 等价性。

**Architecture:** 先写契约测试（其中 2 条断言的正是**新**行为，故先红），再用 ruff 的 `UP042` unsafe autofix 做机械迁移，最后从 `pyproject.toml` 移除忽略项。迁移只改类声明与 1 处 import，不改成员名、成员值、`values_callable`、列名或任何迁移。

**Tech Stack:** Python 3.12 / ruff 0.15.13 / SQLAlchemy 2.x (asyncpg) / pytest（`asyncio_mode = "auto"`）

## Global Constraints

- **不改** 任何枚举成员名或成员值（`.value` 一字不动）。
- **不改** `values_callable`、列名、DDL、或任何 Alembic 迁移。
- **不动** 其余忽略项（`RUF001/002/003`、`RUF005`、`RUF012`、`RUF100`）与 `ARG` 的禁用决定。
- **不借机** 重排或改名任何枚举。
- `StrEnum` 需 Python ≥ 3.11：本仓 `target-version = "py311"`，运行时 3.12.2 ✓
- **探针/调试输出禁用 `str()` 家族**：本次迁移改变的就是 `str(member)` 的输出；用 `str()` 打印枚举会把假象写成结论（本设计初稿即因此误报过 `_lookup` 差异）。一律用 `repr()`。
- 提交信息用**简体中文**，格式 `<type>(<scope>): <简述>`。
- 所有命令在 `backend/` 下执行；ruff 统一走 `uv run --all-packages --group dev ruff`。

## 实测基线（计划内所有数字的来源）

| 项 | 值 | 命令 |
|---|---|---|
| UP042 命中 | **32 处** | `ruff check --select UP042 --output-format json .` |
| 分布 | 22 模块 / 5 包（core 20、portal 8、exec 2、admin 1、ai 1） | 同上 |
| 枚举成员总数 | **134** | 遍历 32 个枚举的成员 |
| 声明风格 | 31 处 `(str, enum.Enum)`；1 处 `(str, Enum)`（`miles_exec/mcp/spec.py`） | `rg "^class \w+\(str, (enum\.)?Enum\)"` |
| 现有测试数 | 1118 passed | `python -m pytest -q` |

`UP042` 的 autofix **可用但属 unsafe**（会改类层次），32/32 全部可修。

---

## File Structure

| 文件 | 职责 | 动作 |
|---|---|---|
| `backend/tests/models/test_enum_contract.py` | 枚举契约：迁移目标 + 唯一行为差异 + SQLAlchemy 等价性 | **新建**（Task 1） |
| `backend/pyproject.toml` | 移除 `UP042` 忽略项并改写注释 | 改（Task 1） |
| 22 个含枚举的模块（见 Task 1 Step 3 清单） | 各改 1–3 行类声明；`miles_exec/mcp/spec.py` 另改 1 行 import | 改（Task 1） |
| `/tmp/probe_enum_pg.py` | 真库探针（**不入库**） | 新建（Task 2） |
| `docs/superpowers/specs/2026-09-16-up042-strenum-migration-design.md` | 补充验证结论到修订记录 | 改（Task 2） |

---

## Task 1: 契约测试 + 迁移 32 处 + 启用 UP042

**Files:**
- Create: `backend/tests/models/test_enum_contract.py`
- Modify: `backend/pyproject.toml`（`ignore` 列表的 `"UP042"` 项）
- Modify: 22 个含枚举的模块（由 autofix 产出）

**Interfaces:**
- Consumes: 无（首个任务）
- Produces:
  - `_UP042_ENUMS: dict[str, tuple[str, ...]]`（测试内私有常量；22 模块 → 类名元组）
  - `_iter_enum_classes() -> Iterator[tuple[str, Any]]`（测试内私有 helper，产出 `(限定名, 枚举类)`）
  - `_iter_members() -> Iterator[tuple[str, enum.Enum]]`（测试内私有 helper，产出 `(限定名, 成员)`）
  - 4 个测试函数：`test_migration_checklist_is_complete`、`test_all_migrated_enums_are_strenum`、`test_str_family_returns_member_value`、`test_sqlalchemy_enum_columns_keep_same_values`
  - 迁移后的 32 个枚举均为 `enum.StrEnum` 子类（后续任务依赖此事实）

- [ ] **Step 1: 写契约测试文件**

创建 `backend/tests/models/test_enum_contract.py`：

```python
"""枚举契约：UP042 迁移（``(str, Enum)`` → ``StrEnum``）后的结构不变量与可观测行为。

为什么必须存在：本次迁移把 32 个枚举的基类由 ``(str, Enum)`` 换成 ``StrEnum``。
实测两者唯一的行为差异是 **str() 家族**——``str()`` / f-string / ``format()`` 旧得
``"Class.MEMBER"``、新得成员值本身；而 ``repr()``、``json.dumps``、``==``、
``.name`` / ``.value``、字符串方法、Pydantic 序列化与 JSON schema、以及 SQLAlchemy
的 ``.enums`` / 绑定 / 读回**全部一致**。

故本文件只锁三件事：迁移目标是否达成、唯一被改变的行为是否符合预期、SQLAlchemy
层是否等价。第三条尤其必要——测试套件用 ``AsyncMock`` 顶替 DB、不跑真库，DB 路径
没有任何其他守卫。

**探针注意**：本文件的断言对象就是 ``str(member)``，故任何调试输出必须用
``repr()``；否则会与被测目标同源，把假象写成结论（本设计初稿曾因此误报
``_valid_lookup`` 差异）。
"""

from __future__ import annotations

import enum
import importlib
from collections.abc import Iterator
from typing import Any

from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects import postgresql

# UP042 迁移清单（实测导出：`ruff check --select UP042 --output-format json .`）。
# 22 模块 / 32 枚举 / 134 成员。此表同时是「清单自身不得漂移」的锚点。
_UP042_ENUMS: dict[str, tuple[str, ...]] = {
    "miles_admin.models.billing": ("BillStatus",),
    "miles_ai.flow_runtime.constants": ("CanvasNodeType",),
    "miles_core.models.agent.agent": ("AgentStatus", "AgentType"),
    "miles_core.models.agent.constants": ("AgentPlanner", "AgentRuntimeMode", "SubAgentRoleHint"),
    "miles_core.models.agent.schedule_run": ("AgentScheduleRunStatus",),
    "miles_core.models.compliance.constants": ("SensitiveAction",),
    "miles_core.models.flow.flow": ("FlowStatus",),
    "miles_core.models.kb.knowledge_base": ("DocumentStatus",),
    "miles_core.models.marketplace.models": ("MarketplaceAppStatus", "MarketplaceAppVisibility"),
    "miles_core.models.meta.category": ("CategoryDomain",),
    "miles_core.models.meta.tag": ("TagEntityType",),
    "miles_core.models.model.catalog": ("ModelCapabilityType", "ModelPublishStatus", "ModelVendor"),
    "miles_core.models.model.generative_job": ("GenerativeJobStatus",),
    "miles_core.models.platform.tenant": ("TenantStatus",),
    "miles_core.models.risk": ("RiskSeverity",),
    "miles_core.models.task.task_record": ("TaskStatus",),
    "miles_exec.mcp.constants": ("McpTransport",),
    "miles_exec.mcp.spec": ("NetworkMode",),
    "miles_portal.tenant.a2a.models": ("A2aInvokePolicy", "A2aPeerStatus", "A2aPlanTrigger"),
    "miles_portal.tenant.hooks.models": ("HookScope", "HookTrigger", "HookType"),
    "miles_portal.tenant.mcp.models": ("McpStatus",),
    "miles_portal.tenant.tools.models": ("ToolType",),
}


def _iter_enum_classes() -> Iterator[tuple[str, Any]]:
    """遍历清单内全部枚举类，产出 ``(限定名, 枚举类)``。"""
    for module_name, class_names in _UP042_ENUMS.items():
        module = importlib.import_module(module_name)
        for class_name in class_names:
            yield f"{module_name}.{class_name}", getattr(module, class_name)


def _iter_members() -> Iterator[tuple[str, enum.Enum]]:
    """遍历清单内全部枚举成员，产出 ``(限定名, 成员)``。"""
    for enum_label, enum_cls in _iter_enum_classes():
        for member in enum_cls:
            yield f"{enum_label}.{member.name}", member


def test_migration_checklist_is_complete() -> None:
    """冻结清单本身不得漂移：22 模块 / 32 枚举 / 134 成员。"""
    assert len(_UP042_ENUMS) == 22
    assert sum(len(names) for names in _UP042_ENUMS.values()) == 32
    assert sum(1 for _ in _iter_members()) == 134


def test_all_migrated_enums_are_strenum() -> None:
    """32 个枚举必须全部是 ``StrEnum`` 子类（迁移目标）。"""
    for enum_label, enum_cls in _iter_enum_classes():
        assert issubclass(enum_cls, enum.StrEnum), f"{enum_label} 尚未迁移为 StrEnum"


def test_str_family_returns_member_value() -> None:
    """``str()`` / f-string / ``format()`` 返回成员值（本次迁移唯一可见的行为变化）。

    这里用内建 ``format(member)`` 而非 ``"{}".format(member)``：两者走同一条
    ``__format__`` 路径，但后者会被 ruff 的 UP032 要求改写为 f-string，从而与
    本测试「刻意覆盖 format 路径」的目的冲突。
    """
    for label, member in _iter_members():
        assert str(member) == member.value, f"{label}: str() 应为成员值"
        assert f"{member}" == member.value, f"{label}: f-string 应为成员值"
        assert format(member) == member.value, f"{label}: format() 应为成员值"
        assert f"{member:>20}" == member.value.rjust(20), f"{label}: 格式说明符应作用于成员值"


def test_sqlalchemy_enum_columns_keep_same_values() -> None:
    """真实 ORM 枚举列：``.enums``（DDL 值列表）与绑定值不因迁移改变。

    套件用 ``AsyncMock`` 顶替 DB、不跑真库，故这里直接对列的 SAEnum 做断言，
    不依赖数据库连接。
    """
    from miles_core.models.agent.agent import Agent, AgentStatus, AgentType
    from miles_portal.tenant.tools.models import Tool, ToolType

    cases: tuple[tuple[Any, str, Any], ...] = (
        (Agent, "status", AgentStatus),
        (Agent, "agent_type", AgentType),
        (Tool, "tool_type", ToolType),
    )
    dialect = postgresql.dialect()
    for model, column_name, enum_cls in cases:
        col_type = model.__table__.c[column_name].type
        assert isinstance(col_type, SAEnum), f"{model.__name__}.{column_name} 应为 SAEnum"
        assert col_type.enums == [m.value for m in enum_cls], f"{model.__name__}.{column_name} 的 DDL 值列表已变"
        bind = col_type.bind_processor(dialect)
        first = next(iter(enum_cls))
        assert bind(first) == first.value, f"{model.__name__}.{column_name} 绑定值已变"
```

- [ ] **Step 2: 跑测试，确认按预期「2 红 2 绿」**

Run:
```bash
cd backend && uv run --all-packages --group dev python -m pytest tests/models/test_enum_contract.py -v
```

Expected:
- `test_migration_checklist_is_complete` **PASS**（清单与现状一致）
- `test_all_migrated_enums_are_strenum` **FAIL** — `AssertionError: ... 尚未迁移为 StrEnum`
- `test_str_family_returns_member_value` **FAIL** — `AssertionError: ... str() 应为成员值`
- `test_sqlalchemy_enum_columns_keep_same_values` **PASS**（等价性护栏，迁移前后都应绿）

> 两条红是本任务要消除的目标；两条绿是必须**保持绿**的等价性护栏。若护栏先红，说明基线认知有误，**停下**而不是继续。

- [ ] **Step 3: 用 autofix 做机械迁移，并清掉随之产生的未使用 import**

```bash
cd backend && uv run --all-packages --group dev ruff check --select UP042 --unsafe-fixes --fix . \
  && uv run --all-packages --group dev ruff check --fix .
```

Expected:
1. `Found 32 errors (32 fixed, 0 remaining).`
2. `Found 1 error (1 fixed, 0 remaining).`

> 第 2 条**必需**：`miles_exec/mcp/spec.py` 原本 `from enum import Enum` 只服务于 `class NetworkMode(str, Enum)`；迁移为 `StrEnum` 后 `Enum` 即变为未使用，而 UP042 的 autofix **不会**顺手删除它（已在 dry run 中实测确认）。这是本次迁移**引入的唯一新 lint 错误**，若不清理，Step 8 的 `ruff check` 会失败。

- [ ] **Step 4: 核对 diff 只含预期的 34 行**

Run:
```bash
cd backend && git diff -U0 | rg "^[+-](class |from enum)" | sort
```

Expected: 34 行删除 + 34 行新增（32 个 class 声明 + `spec.py` 的 import 前后各一次改动），且**每一行**都匹配下列形态之一：

```
-class <Name>(str, enum.Enum):     →  +class <Name>(enum.StrEnum):     （31 处）
-class NetworkMode(str, Enum):     →  +class NetworkMode(StrEnum):      （1 处）
-from enum import Enum             →  +from enum import Enum, StrEnum  （autofix 产出）
-from enum import Enum, StrEnum    →  +from enum import StrEnum        （F401 收敛）
```

用脚本严格校验（任何不符即失败）：

```bash
cd backend && uv run --group dev python -c "
import subprocess, re, sys
diff = subprocess.run(['git','diff','-U0'], capture_output=True, text=True).stdout
changed = [l for l in diff.splitlines() if l.startswith(('+','-')) and not l.startswith(('+++','---'))]
allowed = re.compile(r'^[+-](class \w+\((?:str, enum\.Enum|enum\.StrEnum|str, Enum|StrEnum)\):|from enum import (?:Enum|Enum, StrEnum|StrEnum))\$')
bad = [l for l in changed if not allowed.match(l)]
print(f'变更行 {len(changed)} 条（预期 68）；不符合预期 {len(bad)} 条')
for l in bad: print('  ★', repr(l))
sys.exit(1 if bad or len(changed) != 68 else 0)
" && echo "  ✓ diff 仅含预期的 34 删 / 34 增"
```

> 期望 `len(changed) == 68`。若不符，**不要**手工修补，先 `git checkout .` 回到干净状态再排查 autofix 行为。

- [ ] **Step 5: 确认 `spec.py` 的 import 已收敛**

Run:
```bash
cd backend && rg -n "^from enum import" packages/miles-exec/src/miles_exec/mcp/spec.py
```

Expected: `from enum import StrEnum`（**不含** `Enum`）。

- [ ] **Step 6: 从 pyproject 移除 UP042 忽略项并改写注释**

修改 `backend/pyproject.toml` 的 `ignore` 列表：删除 `"UP042"` 及其上方的多行注释，替换为一条简短记录（保留「原理由说反了」的结论，避免后人再把落库当成理由）：

旧（3 行注释 + 1 行条目）：
```toml
    # 枚举保留 (str, Enum) 而非 StrEnum（实测 32 处）。注意理由不是落库：这些列
    # 一律以 values_callable 取 `.value`，json.dumps 与 == 实测亦一致，故三者都不受影响。
    # 唯一差异在 str()/f-string/format() 的输出——(str, Enum) 得 "Class.MEMBER"，
    # StrEnum 得成员值本身；该类枚举名被 f-string 插值处粗测仅 2 处，但仍须逐处确认
    # 无日志/文案依赖后再改，故整体保留。
    "UP042",
```

新：
```toml
    # UP042 已于 2026-09-16 迁移完毕（32 处 (str, Enum) → StrEnum），故不再忽略。
    # 留档：当初以「影响落库语义」为由忽略是**说反了**——这些列一律以 values_callable
    # 取 .value，json.dumps、== 与 SQLAlchemy 的 .enums/绑定/读回实测均不受影响；
    # 唯一变化是 str()/f-string/format() 由 "Class.MEMBER" 变为成员值本身。
    # 契约见 tests/models/test_enum_contract.py。
```

- [ ] **Step 7: 跑契约测试，确认 4 条全绿**

Run:
```bash
cd backend && uv run --all-packages --group dev python -m pytest tests/models/test_enum_contract.py -v
```

Expected: `4 passed`

- [ ] **Step 8: 确认 UP042 已收敛为 0 且规则确实启用**

Run:
```bash
cd backend && uv run --all-packages --group dev ruff check --select UP042 . && echo "UP042: 0 remaining"
```

Expected: `All checks passed!` + `UP042: 0 remaining`

再确认 `UP042` 已不在忽略列表、且出现在解析后的启用规则集中：

```bash
cd backend && uv run --group dev ruff check --show-settings . | sed -n '/^linter.rules.enabled/,/^]/p' | rg -c "\(UP042\)"
```

Expected: `1`（UP042 已启用；迁移前为 0）

- [ ] **Step 9: 跑全部五道门禁**

Run:
```bash
cd backend && uv run --all-packages --group dev ruff format --check . \
  && uv run --all-packages --group dev ruff check . \
  && uv run --all-packages --group dev lint-imports \
  && uv run --all-packages --group dev python -m miles_server.scripts.export_openapi --check \
  && uv run --all-packages --group dev python -m pytest -q
```

Expected:
- `962 files already formatted`（行数可能因新增 1 测试文件变为 963）
- `All checks passed!`
- `Contracts: 6 kept, 0 broken.`
- `OpenAPI snapshot OK`
- `1122 passed`（基线 1118 + 新增 4 条）

> 若 `ruff format --check` 报新测试文件未格式化，执行 `uv run --all-packages --group dev ruff format tests/models/test_enum_contract.py` 后再跑。

- [ ] **Step 10: 提交**

```bash
git add backend/pyproject.toml backend/tests/models/test_enum_contract.py backend/packages
git commit -F - <<'EOF'
refactor(lint): 启用 UP042，32 处枚举由 (str, Enum) 迁移为 StrEnum

pyproject 原先以「改 StrEnum 会影响落库语义」为由忽略 UP042，该理由说反了：
这些列一律以 values_callable 取 .value，与 str() 无关。实测 json.dumps、==、
SQLAlchemy 的 .enums（DDL 值列表）/绑定/读回、以及 Pydantic 序列化与 JSON schema
全部不受影响；整个迁移唯一的行为变化是 str()/f-string/format() 由 "Class.MEMBER"
变为成员值本身。

可达路径上无一处依赖该旧输出：全仓无 "Class.MEMBER" 硬编码字面量；8 处
str()/f-string 候选经逐处核对为 4 处走 .value 守卫分支、3 处误报（domain/action
实为 str 参数）、1 处不可达防御分支（ToolType 仅 HTTP/SCRIPT，工具分发已穷尽且无
任何测试断言该文案）。

故迁移是机械替换：ruff 的 UP042 unsafe autofix 改 32 处类声明与 spec.py 的 import
（diff 严格校验为 34 删 / 34 增），随后 ruff 的 F401 修复清掉迁移**引入**的未使用
`Enum` import（spec.py 原本只用它做基类）。不改成员名、成员值、values_callable、
列定义或任何迁移。

新增 tests/models/test_enum_contract.py 锁三件事：迁移目标（32 个均为 StrEnum）、
唯一行为变化（str() 家族返回成员值）、以及 SQLAlchemy 等价性（.enums 与绑定值
不变）。第三条是必要的——测试套件用 AsyncMock 顶替 DB、不跑真库，DB 路径没有
其他守卫。
EOF
```

---

## Task 2: 独立验证（真库探针 + 敏感度对照 + 门禁复核 + spec 回填）

**Files:**
- Create: `/tmp/probe_enum_pg.py`（**不入库**，仅验证用）
- Modify: `docs/superpowers/specs/2026-09-16-up042-strenum-migration-design.md`（§10 修订记录）

**Interfaces:**
- Consumes: Task 1 迁移后的 32 个 `StrEnum`
- Produces: 验证结论（真库写入/读回一致、敏感度对照能报错），回填进 spec §10

- [ ] **Step 1: 确认真库可达**

Run:
```bash
cd backend && uv run --group dev python -c "
import asyncio
from miles_core.infra.db import engine
async def main():
    async with engine.connect() as conn:
        v = await conn.exec_driver_sql('select version()')
        print('  PG:', v.scalar()[:40])
asyncio.run(main())
"
```

Expected: 打印 PostgreSQL 版本。

> 若真库不可达（`POSTGRES_DB` 未配置或未启动），**不要**跳过验证：改为在 Step 2 用 `sqlite+aiosqlite` 的内存引擎做同一轮 bind/读回（SQLAlchemy 的枚举编解码层与方言无关），并在 spec §10 明确记录「以 sqlite 内存引擎替代真库」及其局限。禁止把「测试全绿」当作 DB 层已验证。

- [ ] **Step 2: 写真库探针**

创建 `/tmp/probe_enum_pg.py`：

```python
"""真库探针：StrEnum 迁移后，枚举列的写入/读回与迁移前逐行一致。

不进仓库。用法：uv run --group dev python /tmp/probe_enum_pg.py [--corrupt]
``--corrupt`` 为敏感度对照：故意把期望值改错，探针必须报错。
"""

import asyncio
import sys

from sqlalchemy import select

from miles_core.infra.db import AsyncSessionLocal
from miles_core.models.agent.agent import Agent, AgentStatus, AgentType
from miles_core.models.platform.tenant import Tenant, TenantStatus

CORRUPT = "--corrupt" in sys.argv


async def main() -> None:
    async with AsyncSessionLocal() as session:
        tenant = Tenant(name="enum-probe", status=TenantStatus.ACTIVE)
        session.add(tenant)
        await session.flush()

        agent = Agent(
            tenant_id=tenant.id,
            name="enum-probe-agent",
            agent_type=AgentType.CUSTOM,
            status=AgentStatus.ENABLED,
        )
        session.add(agent)
        await session.flush()
        await session.commit()

        agent_id = agent.id
        tenant_id = tenant.id

    # 新会话读回，避免 identity map 掩盖真实 SQL 往返
    async with AsyncSessionLocal() as session:
        got = (await session.execute(select(Agent).where(Agent.id == agent_id))).scalar_one()
        expected = "disabled" if CORRUPT else AgentStatus.ENABLED.value
        print(f"  读回 status      = {got.status!r}   (期望 {expected!r})")
        assert got.status == AgentStatus.ENABLED, "读回的枚举成员不对"
        assert got.status.value == expected, f"读回的值不对：{got.status.value!r} != {expected!r}"
        assert got.agent_type is AgentType.CUSTOM, "agent_type 读回不对"
        print("  ✓ 写入/读回一致")

        # 清理
        await session.execute(Agent.__table__.delete().where(Agent.id == agent_id))
        await session.execute(Tenant.__table__.delete().where(Tenant.id == tenant_id))
        await session.commit()


asyncio.run(main())
print("  probe OK")
```

- [ ] **Step 3: 跑探针（正常路径）**

Run:
```bash
cd backend && uv run --group dev python /tmp/probe_enum_pg.py
```

Expected: 打印读回值与 `✓ 写入/读回一致`，最后 `probe OK`。

- [ ] **Step 4: 跑敏感度对照（必须失败）**

Run:
```bash
cd backend && uv run --group dev python /tmp/probe_enum_pg.py --corrupt; echo "exit=$?"
```

Expected: `AssertionError: 读回的值不对：'enabled' != 'disabled'`，且 `exit=1`。

> 探针必须能**失败**，否则它证明不了任何事。若对照也通过，说明探针是空转（断言写错/读回被 identity map 掩盖），先修探针再继续。

- [ ] **Step 5: 复核 Task 1 未触碰非目标**

Run:
```bash
cd backend && echo "=== 未改任何迁移 ===" && git diff --name-only HEAD~1 | rg "alembic" || echo "  ✓ 无迁移改动" && \
echo "=== 未改 values_callable ===" && git diff HEAD~1 | rg "values_callable" || echo "  ✓ 无 values_callable 改动" && \
echo "=== 枚举成员值未变 ===" && git diff HEAD~1 | rg "^[+-]\s+[A-Z_]+ = " || echo "  ✓ 无成员行改动" && \
echo "=== 其余忽略项原样 ===" && rg -c "RUF001|RUF002|RUF003|RUF005|RUF012|RUF100" pyproject.toml | xargs echo "  仍保留条目数："
```

Expected: 前三条均打印 `✓`；最后一条为 `6`。

- [ ] **Step 6: 回填 spec 修订记录**

在 `docs/superpowers/specs/2026-09-16-up042-strenum-migration-design.md` 的 `## 10. 修订记录` 追加（把命令实际输出填进去，不要写占位）：

```markdown
- 2026-09-16 实施：32 处迁移完成，UP042 启用（`ruff check --select UP042 .` 收敛为 0）。
  契约测试 `tests/models/test_enum_contract.py`（4 条）全绿；五道门禁全绿（N passed）。
  真库探针写入/读回一致，敏感度对照（`--corrupt`）按期报错。spec §5.2 的条件已满足：
  迁移未产生任何 DB 层差异。
```

同时把文件头 `- 状态：待评审` 改为 `- 状态：已实施`。

- [ ] **Step 7: 提交**

```bash
git add docs/superpowers/specs/2026-09-16-up042-strenum-migration-design.md
git commit -F - <<'EOF'
docs(spec): 回填 UP042 迁移的实施与验证结论

记录真库探针（含敏感度对照）与五道门禁的实际结果，并把状态改为已实施。
EOF
```

---

## 收尾：整分支终审

Task 2 提交后，派一个 fresh subagent 做**整分支终审**（独立重建 `HEAD~2` 的旧实现并实测对比，而非只读 diff），重点：

1. 旧新对比：32 个枚举的成员集合、成员值、`.enums`/绑定/读回是否逐条一致；
2. 契约测试是否非空洞（对 `test_str_family_returns_member_value` 做变异：把某个 `str()` 断言改回 `"Class.MEMBER"` 应失败）；
3. 是否有本计划未列出的文件被改动；
4. spec 与实际是否一致（含 §5.2 勘误后的结论）。

---

## Self-Review

**1. Spec coverage**

| spec 章节 | 落点 |
|---|---|
| §2 目标：启用 UP042 + 迁移 32 处 | Task 1 Step 3、Step 5、Step 7 |
| §2 目标：固化唯一差异（`str()`） | Task 1 Step 1（`test_str_family_returns_member_value`） |
| §2 目标：锁 SQLAlchemy 等价性 | Task 1 Step 1（`test_sqlalchemy_enum_columns_keep_same_values`） |
| §2 非目标：不改成员/值/values_callable/迁移 | Task 1 Step 4（diff 严格校验）+ Task 2 Step 5（复核） |
| §5.1 静态扫描：无硬编码字面量、8 处候选已分类 | Task 1 Step 8（五道门禁的 pytest 全量） |
| §5.2 SQLAlchemy 等价（勘误后结论） | Task 1 Step 1 第三条测试 + Task 2 Step 2–4（真库探针） |
| §6 改动方案 1（pyproject） | Task 1 Step 5 |
| §6 改动方案 2（31 处 `(str, enum.Enum)`） | Task 1 Step 3–4 |
| §6 改动方案 3（1 处 `(str, Enum)` + import） | Task 1 Step 3–4（`spec.py` 由 autofix 处理） |
| §7 五道门禁 | Task 1 Step 8 |
| §7.1 真库探针 + 敏感度对照 | Task 2 Step 1–4 |
| §7.2 固化 `str()` 差异 | Task 1 Step 1 |
| §7.3 锁 SQLAlchemy 等价性 | Task 1 Step 1 |
| §7.4 `alembic check`（若可达） | Task 2 Step 1 备注；真库可达时附件执行 |
| §10 修订记录 | Task 2 Step 6 |

**2. Placeholder scan**

已检查：无 `TBD`/`TODO`/「稍后实现」/「类似 Task N」。所有代码步骤含完整代码；除 Task 2 Step 6 的修订记录要求「把实测输出填入」外无占位（该处刻意要求填真实数字而非预设，以免又写一个未实测的数）。

**3. Type consistency**

- `_UP042_ENUMS: dict[str, tuple[str, ...]]` 在 Step 1 定义，`_iter_members()` 消费其 `.items()`；任务内自洽。
- `test_sqlalchemy_enum_columns_keep_same_values` 的 `cases` 元素为 `(model, column_name, enum_cls)`，与循环解包一致。
- Task 2 探针使用的 `Agent`/`AgentType`/`AgentStatus`/`Tenant`/`TenantStatus` 均为 Task 1 已迁移的枚举所在模块，符号名与 Task 1 清单一致。
- 跨任务无重命名（本计划仅 2 个任务，且 Task 2 不定义新接口）。

**4. Dry run 实测（本计划的预期输出全部来自真实执行，非推测）**

在临时 worktree（`--detach main`）上完整跑过一遍，确认并**修正**了以下事实：

| 项 | 计划原写 | 实测 |
|---|---|---|
| UP042 autofix 输出 | `Found 32 errors (32 fixed, 0 remaining).` | 一致 ✓ |
| autofix 的 diff | 66 行（33 删 + 33 增） | 一致 ✓ |
| 迁移后 `ruff check` | 预期全绿 | **FAIL：`spec.py` 报 F401**（`Enum` 变为未使用，autofix 不删）→ 已加 Step 3 第二条命令 |
| 测试文件内 `"{}".format(member)` | 计划原写 `.format()` | **FAIL：ruff `UP032` 要求改 f-string** → 已改为内建 `format(member)`（同一 `__format__` 路径，且不触发该规则） |
| 契约测试迁移前 | 2 红 2 绿 | 一致 ✓（失败信息正是 `'BillStatus.DRAFT' == 'draft'`） |
| 契约测试迁移后 | 4 绿 | 一致 ✓ |
| 全量 pytest | 1122 passed | 一致 ✓ |
| `ruff format --check` | — | 963 files ✓ |

两处差异都是**会让计划执行失败**的缺陷，且第二处（UP032）是我自己写测试时引入的——说明「计划里的代码也必须先跑过」不是形式要求。
