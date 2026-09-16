# 启用 UP042：32 处 `(str, Enum)` 迁移到 `StrEnum`

- 日期：2026-09-16
- 状态：待评审
- 上游线索：`backend/pyproject.toml` 的 `UP042` 忽略项。其原注释理由（「改 StrEnum 会影响**落库**语义」）经实测**说反了**——落库恰是唯一不受影响的路径。修正注释时发现真实风险面远小于原注释暗示，故评估启用。

## 1. 问题

`backend/pyproject.toml` 以「落库语义」为由整体忽略 `UP042`（`(str, Enum)` 应为 `StrEnum`）。该理由不成立：

- 这些枚举列一律以 `values_callable=lambda x: [e.value for e in x]` 取 `.value`，与 `str()` 无关；
- 实测 `json.dumps`、`==`、Pydantic 序列化与 JSON schema 均不受影响。

同时，忽略项的注释让读者以为迁移成本很高（「需单独评估」），而实测可达路径上**零行为差异**。本设计把成本量化清楚后启用该规则。

## 2. 目标 / 非目标

**目标**

- 启用 `UP042`，将 32 处 `(str, Enum)` 迁移为 `StrEnum`；
- 把实测出的两条**真实差异**固化成测试，而非留成隐患。

**非目标**

- 不改任何枚举成员名或成员值（`.value` 一字不动）；
- 不改 `values_callable`、列名、DDL 或任何迁移；
- 不动其余忽略项（`RUF001/002/003`、`RUF005`、`RUF012`、`RUF100`）与 `ARG` 的禁用决定；
- 不借机重排或改名任何枚举。

## 3. 现状（实测）

`ruff check --select UP042 --output-format json .` 命中 **32 处，分布 22 文件 / 5 包**：

| 包 | 枚举数 | 文件数 |
|---|---|---|
| `miles-core` | 20 | 14 |
| `miles-portal` | 8 | 4 |
| `miles-exec` | 2 | 2 |
| `miles-admin` | 1 | 1 |
| `miles-ai` | 1 | 1 |

声明风格：**31 处** `class X(str, enum.Enum):`（所在文件均已 `import enum`）；**1 处** `class NetworkMode(str, Enum):`（`miles_exec/mcp/spec.py`，也是唯一使用 `from enum import` 的文件）。

**测试基础设施的关键限制**：`tests/conftest.py` 用 `AsyncMock` 顶替 DB session（`app.dependency_overrides[get_db] = override_db`），因此 **1118 条测试基本不跑真库**。SQLAlchemy 层的等价性**不能**指望测试来证明，必须专项验证（见 §6）。

## 4. 语义差异矩阵（实测）

探针：Python 3.12.2，同名类对比（**排除类名造成的假差异**）。

| 操作 | `(str, Enum)` | `StrEnum` | 结果 |
|---|---|---|---|
| `str(x)` | `'E.A'` | `'a'` | **变** |
| `f"{x}"` | `'E.A'` | `'a'` | **变** |
| `f"{x:>6}"` | `'   E.A'` | `'     a'` | **变** |
| `f"{x!r}"` | `"<E.A: 'a'>"` | `"<E.A: 'a'>"` | 同 |
| `"{}".format(x)` | `'E.A'` | `'a'` | **变** |
| `repr(x)` | `"<E.A: 'a'>"` | `"<E.A: 'a'>"` | 同 |
| `json.dumps(x)` | `'"a"'` | `'"a"'` | 同 |
| `x == "a"` / `x in {"a"}` | `True` | `True` | 同 |
| `len(x)` / `x.upper()` / `x.startswith("a")` / `"p" + x` / `x * 2` | 同 | 同 | 同 |
| `E("a")` / `sorted([x])` / dict 键查找 / `isinstance(x, str)` | 同 | 同 | 同 |
| `.name` / `.value` | `'A'` / `'a'` | `'A'` / `'a'` | 同 |
| Pydantic `model_dump_json()` | `'"a"'` | `'"a"'` | 同 |
| Pydantic `json_schema()` | `{enum: ["a"], type: "string"}` | 同 | 同 |

**结论：真实差异仅在 `str()` 家族**（`str()`、f-string、`format()` 及其格式说明符）。`repr()` 与其余全部一致。

> 勘误：首次探针曾报 `repr()` 有差异，系探针自身用了 `Old` / `New` 两个不同类名所致，同名重测后一致。此处记录以免后人重走。

## 5. 风险面分析

### 5.1 静态扫描（全仓，含 tests）

- **硬编码 `"Class.MEMBER"` 字符串字面量：0 处** → 无字符串比较会断。
- `str()` / f-string / `format()` 作用于枚举实例的候选：**8 处**，逐一核对后：
  - **4 处**形如 `x.value if hasattr(x, "value") else str(x)`（`tools/services/tools.py:317`、`custom_tools.py:43`、`monitor/services/monitor.py:279`、`agents/services/architecture.py:240`）→ `StrEnum` 成员仍有 `.value`，走 `.value` 分支，**不受影响**；
  - **3 处误报**（`sys_category.py:24`、`categories/services/category.py:23`、`test_user_service.py:123`）→ 命中的 `domain` / `action` 是 `str` 型函数参数，非枚举实例；
  - **1 处不可达防御分支**（`tools/invoke/context.py:94`，报错文案 `f"暂不支持执行工具类型: {tool.tool_type}"`）→ `ToolType` 仅 `HTTP` / `SCRIPT` 两成员，第 90/92 行已穷尽，该行不可达；且**无任何测试断言此文案**。若将来新增成员使其可达，文案会由 `ToolType.X` 变为 `x`。

### 5.2 SQLAlchemy（最高风险区）

`SAEnum(E, name=..., values_callable=...)` 内部结构实测：

| 内部结构 | `(str, Enum)` | `StrEnum` | 结果 |
|---|---|---|---|
| `.enums`（DDL 值列表） | `['a','b']` | `['a','b']` | 同 |
| `_object_lookup`（**读库**值→成员） | `{None,'a','b'}` | `{None,'a','b'}` | 同 |
| `_db_value_for_elem(E.A)`（绑定值） | `'a'` | `'a'` | 同 |
| `_valid_lookup`（**入参校验**） | `{None,'E.A','E.B'}` | `{None,'a','b'}` | **变** |

即：**DDL、读库、绑定值全同；唯一变化是入参校验变严** —— 旧类型容忍把 `str(member)`（如 `"ToolType.HTTP"`）当值传入，新类型不容忍。

评估：该收紧是**期望方向**——旧行为等于默默接受一个来自 `str()` 误用的值。全仓已确认无此形态（§5.1 无硬编码字面量、无 f-string 馈入查询）。但由于测试不跑真库，此差异**测不到**，故列入 §6 专项验证。

## 6. 改动方案

1. **`pyproject.toml`**：从 `ignore` 移除 `"UP042"`；同步改写其注释为「已迁移」并保留 §4 的差异结论与理由勘误。
2. **31 处**：`class X(str, enum.Enum):` → `class X(enum.StrEnum):`。
3. **1 处**：`miles_exec/mcp/spec.py` 的 `class NetworkMode(str, Enum):` → `class NetworkMode(StrEnum):`，并把 `StrEnum` 加入 `from enum import`。
4. 不改成员、值、列定义与迁移。

## 7. 验证策略

除常规五道门禁（`ruff format --check` / `ruff check` / `lint-imports` / `export_openapi --check` / `pytest`）外，针对测试不跑真库这一限制补三项：

新增契约测试落 `backend/tests/models/test_enum_contract.py`（与 `tests/models/` 现有职责一致：模型层纯测试、不依赖 DB）。

1. **真库探针**（`/tmp`，不入库）：对代表枚举列做 bind → 写 PostgreSQL → 读回，改前 / 改后比对输出必须一致；并做**敏感度对照**（故意改错值应能被探针发现），避免探针本身是空转。
2. **固化入参校验差异**：在 `test_enum_contract.py` 断言新类型**拒绝** `"Class.MEMBER"` 形式、**接受** `.value` 形式。把 §5.2 的已知差异变成显式契约，而非隐患。
3. **固化 `str()` 差异**：在 `test_enum_contract.py` 断言 `str()` / f-string 输出为**成员值**（而非 `"Class.MEMBER"`），以显式记录新的可观测行为。
4. 若数据库可达，加跑 `alembic check` 证无 DDL 漂移。

## 8. 风险与对策

| # | 风险 | 对策 |
|---|---|---|
| R1 | 某处依赖 `str(枚举)` 旧输出（日志/文案/拼接） | §5.1 已全仓扫描：4 处走 `.value` 分支、3 处误报、1 处不可达；无硬编码字面量 |
| R2 | 某处把 `str(枚举)` 当值传入（现会被拒） | §5.1 已确认无此形态；§7.2 固化成测试；且失败形态是**响亮报错**而非静默 |
| R3 | 真库路径回归而测试测不到 | §7.1 真库探针 + 敏感度对照；§7.4 `alembic check` |
| R4 | SQLAlchemy 或 Alembic 对 `StrEnum` 支持差异 | §5.2 已实测内部结构；`.enums` 相同 ⇒ DDL 不变 |
| R5 | 漏改文件或改错风格（31+1 两种） | 以 `ruff check --select UP042` 从 32 → 0 作为收敛判据 |
| R6 | 将来某处依赖 `str()` 新输出，反向锁死 | §7.3 把新行为写成显式测试，使依赖可见 |

## 9. 后续（不在本次范围）

- `miles_server/registry.py` 的副作用导入块可改为 `importlib.import_module` 循环，从根上消除「F401 只报每组末行」的导入顺序依赖，从而删掉全部 21 条 `# noqa: F401`。已在上游注释中留档，另行处理。
- `ARG` 维持不启用（噪声主体 88% 在 tests，生产侧 48 处全为接口契约）。

## 10. 修订记录

- 2026-09-16 初稿。
