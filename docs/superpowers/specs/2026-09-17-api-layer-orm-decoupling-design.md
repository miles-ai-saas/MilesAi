# API 声明层与 ORM 解耦：把持久化枚举移出 `views/` 与 `schemas/`

- 日期：2026-09-17
- 状态：待实施
- 关联：Batch 3「功能边界」项 11；`.importlinter` 第 7 条契约
- 实施分支：待定（见 §11）

---

## 1. 背景与动机

Batch 3「函数实现与功能边界」清单中的项 11 原文是「解耦 `views/agents.py` 里对 ORM 模块 `AgentStatus`/`AgentType` 的依赖」。勘察后确认这不是单点问题：

- `miles_portal` 与 `miles_admin` 的 `views/`、`schemas/` 目录共有 **27 个文件 / 28 处 import** 直接引用 ORM 模块；
- 其中 **21 个是持久化枚举**：19 个被 `views/`/`schemas/` 直接 import（17 个已成为 OpenAPI 的命名枚举组件，2 个只作字段默认值），另 2 个随 `marketplace.dto` 携带进入 API 面；
- 其余是 DTO 与聚合 re-export，另 1 处是 ORM 实体引用。

用户已明确要求两件事同时成立：

1. **公开契约与 ORM 模型解耦**——改 ORM 枚举不应无声改公开 API；
2. **该边界由 lint 硬禁**——以后新增的 `views/`/`schemas/` 代码不能再引入这条依赖。

仓内现有 6 条 import-linter 契约（见 `.importlinter`）都不覆盖这条边：`包分层方向` 只约束包与包之间，而 `miles_portal` 内部用 `miles_core.models` 是**被允许**的（services/repositories 必须用 ORM 实体查询）。所以本设计要新增的是**包内的目录级**约束，而不是调整分层。

---

## 2. 目标 / 非目标

### 2.1 目标

- G1 `views/` 与 `schemas/` 目录**不再 import 任何承载 SQLAlchemy 实体的模块**（含聚合 re-export 包）；
- G2 该边界由新增的 import-linter 契约硬禁，且**新域、新文件自动纳入**（不依赖人工登记源文件）；
- G3 **OpenAPI 快照逐字节不变**——本次改动对 API 消费者零可观测影响；
- G4 21 个持久化枚举在 API 侧有自己的声明，与 ORM 侧的关系由**显式护栏**约束。

### 2.2 非目标

- N1 不改任何 API 行为、路由、字段名、枚举值、默认值、错误文案；
- N2 不动 services / repositories / deps —— 它们本来就该用 ORM；
- N3 **ORM 侧零改动**：ORM 枚举、列类型、`values_callable`、Alembic 迁移文件全部不动；
- N4 不治理各域 `meta.py`（它们不在契约源内，仍可引用 ORM 枚举；作为可选跟进登记在 §9）；
- N5 不把 ORM 枚举删除或改为 `StrEnum` 之外的形式（`StrEnum` 迁移是另一专项，已完成）。

---

## 3. 现状勘察（全部为实测）

### 3.1 违规面：27 文件 / 28 处

`views/` 与 `schemas/` 下对 ORM 模块的直接 import，按被引用对象分类：

| 类别 | 处数 | 去重后被引用对象 | 处置 |
|---|---|---|---|
| 持久化枚举（作类型注解） | 22 | 17 个枚举 | 迁移到 API 侧声明（§5.2） |
| 持久化枚举（仅取 `.value` 作默认值） | 2 | 2 个枚举 | 同上 |
| 纯 DTO | 3 | 2 个模块（`marketplace.dto` 内另携带 2 个枚举，见 §5.3） | 随 DTO 模块下沉（§5.3） |
| ORM 实体（`AgentScheduleRun`） | 1 | 1 个实体 | 结构性改造（§5.4） |
| **合计** | **28** | **21 个枚举**（17 直接 + 2 取值 + 2 随 DTO 携带）+ 2 个 DTO 模块 + 1 个实体 | |

明细（文件:行 → 被引用模块 → 名称）：

| # | 文件 | 行 | 被引用模块 | 名称 | 类别 |
|---|---|---|---|---|---|
| 1 | `miles-portal/.../a2a/schemas/peer.py` | 12 | `miles_portal.tenant.a2a.models` | `A2aPeerStatus` | 枚举 |
| 2 | `miles-portal/.../agents/schemas/agent.py` | 14 | `miles_core.models.agent` | `AgentStatus`, `AgentType` | 枚举 |
| 3 | `miles-portal/.../agents/schemas/agent.py` | 15 | `miles_core.models.agent.chat_io` | `ChatArtifact`, `ChatMediaIn`, `ChatRequest`, `ChatResponse`, `PendingToolCall` | DTO（re-export） |
| 4 | `miles-portal/.../agents/schemas/schedule_run.py` | 10 | `miles_core.models.agent.schedule_run` | `AgentScheduleRun` | ORM 实体 |
| 5 | `miles-portal/.../agents/views/agents.py` | 17 | `miles_core.models.agent` | `AgentType` | 枚举 |
| 6 | `miles-portal/.../categories/schemas/category.py` | 8 | `miles_core.models.meta.category` | `CategoryDomain` | 枚举 |
| 7 | `miles-portal/.../categories/views/categories.py` | 17 | `miles_core.models.meta.category` | `CategoryDomain` | 枚举 |
| 8 | `miles-portal/.../compliance/schemas/compliance.py` | 8 | `miles_portal.tenant.compliance.models` | `SensitiveAction` | 枚举 |
| 9 | `miles-portal/.../flows/schemas/flow.py` | 9 | `miles_core.models.flow` | `FlowStatus` | 枚举 |
| 10 | `miles-portal/.../generative/schemas/job.py` | 8 | `miles_core.models.model.generative_job` | `GenerativeJobStatus` | 枚举 |
| 11 | `miles-portal/.../generative/views/jobs.py` | 14 | `miles_core.models.model.generative_job` | `GenerativeJobStatus` | 枚举 |
| 12 | `miles-portal/.../hooks/schemas/hook.py` | 8 | `miles_portal.tenant.hooks.models` | `HookScope`, `HookTrigger`, `HookType` | 枚举 |
| 13 | `miles-portal/.../kb/schemas/kb.py` | 25 | `miles_core.models.kb` | `DocumentStatus` | 枚举 |
| 14 | `miles-portal/.../marketplace/schemas/marketplace.py` | 9 | `miles_core.models.marketplace.dto` | 17 个 DTO（含 `AppReviewBody`） | DTO（re-export） |
| 15 | `miles-portal/.../mcp/schemas/mcp.py` | 13 | `miles_portal.tenant.mcp.models` | `McpStatus` | 枚举 |
| 16 | `miles-portal/.../models/schemas/model.py` | 8 | `miles_core.models.model.catalog` | `ModelCapabilityType`, `ModelVendor` | 枚举（仅 `.value`） |
| 17 | `miles-portal/.../system/schemas/tenant.py` | 8 | `miles_core.models.platform.tenant` | `TenantStatus` | 枚举 |
| 18 | `miles-portal/.../tasks/schemas/task.py` | 8 | `miles_core.models.task.task_record` | `TaskStatus` | 枚举 |
| 19 | `miles-portal/.../tasks/views/tasks.py` | 10 | `miles_core.models.task.task_record` | `TaskStatus` | 枚举 |
| 20 | `miles-portal/.../tools/schemas/tools.py` | 11 | `miles_portal.tenant.tools.models` | `ToolType` | 枚举 |
| 21 | `miles-admin/.../app_ops/schemas/billing.py` | 9 | `miles_admin.models` | `BillStatus` | 枚举 |
| 22 | `miles-admin/.../app_ops/schemas/model_catalog.py` | 8 | `miles_core.models.model.catalog` | `ModelCapabilityType`, `ModelVendor` | 枚举（仅 `.value`） |
| 23 | `miles-admin/.../app_ops/schemas/risk.py` | 8 | `miles_admin.models` | `RiskSeverity` | 枚举 |
| 24 | `miles-admin/.../app_ops/schemas/tenant.py` | 8 | `miles_core.models.platform.tenant` | `TenantStatus` | 枚举 |
| 25 | `miles-admin/.../app_ops/views/billing.py` | 13 | `miles_admin.models` | `BillStatus` | 枚举 |
| 26 | `miles-admin/.../app_ops/views/marketplace_review.py` | 15 | `miles_core.models.marketplace.dto` | `AppReviewBody` | DTO |
| 27 | `miles-admin/.../app_ops/views/risk.py` | 12 | `miles_admin.models` | `RiskSeverity` | 枚举 |
| 28 | `miles-admin/.../app_ops/views/tenants.py` | 16 | `miles_core.models.platform.tenant` | `TenantStatus` | 枚举 |

> 复现方式：对 `packages/{miles-portal,miles-admin}/src/**/{views,schemas}/**.py` 取 AST 的 `ImportFrom.module`，筛选以 `miles_core.models` / `miles_admin.models` / `miles_portal.tenant.<域>.models` 开头者。纯文本 `rg` 会漏掉不含
> `Status|Type|Mode|…` 关键字的枚举（实际漏掉过 `CategoryDomain` 与 `A2aPeerStatus`，后者因域名含数字被 `[a-z_]+` 漏掉），故**必须以 AST 复算**。

### 3.2 19 个对外枚举的归属

OpenAPI 快照 `components.schemas` 中含 `enum` 的组件共 **19 个**（另有 28 处内联 `enum`，均为普通字符串字段的字面量取值，不属于本次范围）：

| 枚举 | 定义模块 |
|---|---|
| `A2aPeerStatus` | `miles_portal.tenant.a2a.models` |
| `AgentStatus` / `AgentType` | `miles_core.models.agent.agent` |
| `BillStatus` | `miles_admin.models.billing` |
| `CategoryDomain` | `miles_core.models.meta.category` |
| `DocumentStatus` | `miles_core.models.kb.knowledge_base` |
| `FlowStatus` | `miles_core.models.flow.flow` |
| `GenerativeJobStatus` | `miles_core.models.model.generative_job` |
| `HookScope` / `HookTrigger` / `HookType` | `miles_portal.tenant.hooks.models` |
| `MarketplaceAppStatus` / `MarketplaceAppVisibility` | `miles_core.models.marketplace.models` |
| `McpStatus` | `miles_portal.tenant.mcp.models` |
| `RiskSeverity` | `miles_core.models.risk` |
| `SensitiveAction` | `miles_core.models.compliance.constants` |
| `TaskStatus` | `miles_core.models.task.task_record` |
| `TenantStatus` | `miles_core.models.platform.tenant` |
| `ToolType` | `miles_portal.tenant.tools.models` |

另有 2 个持久化枚举**不构成对外枚举组件**，仅在 schema 中取 `.value` 作字段默认值：`ModelVendor`、`ModelCapabilityType`（同属 `miles_core.models.model.catalog`）。

上表 19 个组件中，17 个由 `views/`/`schemas/` 直接 import（§3.1 明细中可见）；`MarketplaceAppStatus` 与 `MarketplaceAppVisibility` 不由这些文件直接 import，而是随 `marketplace.dto`（`MarketplaceAppOut` 等 DTO 的字段类型）进入 API 面。故需 API 侧声明的持久化枚举为 **17 + 2 + 2 = 21** 个。

### 3.3 契约可表达性的四项实测结论

四项结论均以临时契约在本仓实跑得到，是 §5.1 契约形状的直接依据：

1. **中缀通配符受支持**：`source_modules = miles_portal.tenant.*.views` 能解析出 `miles_portal.tenant.workbench.views` 等并正常判定。通配按 fnmatch 语义（`*` 可跨 `.`），故 `miles_portal.tenant.*.models` 不会误伤「模型目录」域（实测 `miles_portal.tenant.models.views` → 自家 `...models.schemas.model` 未被判违规，因为模式两端锚定：目标以 `.model` 结尾，不匹配以 `.models` 结尾的模式）。
2. **必须列到聚合包层级**：`forbidden_modules = miles_core.models.agent.agent`（叶子）对 `from miles_core.models.agent import AgentType` **判定为 KEPT（漏网）**——该 import 的图边目标是包 `miles_core.models.agent`，即聚合 `__init__`，不是叶子模块。改列 `miles_core.models.agent` 后正确报出。
3. **`allow_indirect_imports = True` 是必需的**：不加会沿 `views → miles_core.deps → miles_core.models.platform.user` 这类链误报（`miles_core.deps` 本身会拉到 models，但那是 deps 的职责，不是视图的违规）。
4. **`TYPE_CHECKING` 与函数内 import 同样被判违规**：实测三种写法（模块顶层、`if TYPE_CHECKING:` 内、函数体内）全部报出。故类型注解**不是**逃逸口，§5.4 必须结构性改造。

### 3.4 既有约定与本设计的冲突点

- `agents/schemas/agent.py` 与 `marketplace/schemas/marketplace.py` 的 docstring 均记录了「实现已上移**中立域** `miles_core.models.*`（admin 与 tenant 共用）」——即「共享契约放 `miles_core.models`」是本仓**已文档化**的惯例。本设计与之结构性冲突：`miles_core.models` 的聚合包里既有 ORM 又有 DTO，契约按前缀禁止 ORM 时无法把包内 DTO 排除在外。故这些 DTO 需要再下沉一层（§5.3）。
- `miles_common/schemas/tag.py` 提供了已落地的先例：把跨域共用的中立模型从租户域**下沉到 `miles_common`**，旧路径转 re-export 保持 import 稳定。本设计对 DTO 与跨端枚举沿用该先例。
- 仓内目前**没有**任何「同一概念的多个独立枚举类」：`MarketplaceAppStatus`（3 处）、`SensitiveAction`（3 处）、`RiskSeverity`（2 处）经实测均为**同一对象**的 re-export。引入 API 侧声明将是本仓第一例真实重复定义，故 §6 必须有专项护栏。

---

## 4. 方案取舍

| 方案 | 内容 | 结论 |
|---|---|---|
| **外科式（采用）** | 契约只禁**承载 ORM 实体或持久化枚举**的模块（逐条列举，包层级）；嵌在 ORM 包内的 2 个 DTO 下沉；API 枚举分域声明 | 边界精确、改动面最小；代价是契约清单需随新增 ORM 模块同步 |
| 下沉式 | 连 DTO 一并下沉，并把契约写成「禁整个 `miles_core.models`」 | 与 §3.4 的既有约定正面冲突，且 `miles_core.models` 内还有 `base`（mixin）、`media.reader`、`tool.parameters` 等本就该留在 models 的模块，无法凑出「models 包只放 ORM」的不变量，故否决 |
| 门面 re-export | 在域根建 `api_enums.py` 转 re-export ORM 枚举，满足契约字面 | 零复制，但公开契约仍绑 ORM，不满足 G1/G4 的动机，明确否决 |

用户已确认采用**外科式**，并确认 DTO 下沉由契约形状决定、必须一并处理。

---

## 5. 设计

### 5.1 契约形状（`.importlinter` 新增第 7 条）

```ini
[importlinter:contract:api-layer-no-orm]
name = API 声明层不得依赖 ORM
type = forbidden
# 视图与入参声明层不得 import 承载 SQLAlchemy 实体或持久化枚举的模块。
# 必要性：本契约是「包内目录级」约束，包分层方向契约管不到（miles_portal
# 用 miles_core.models 是被允许的——services/repositories 必须用 ORM 查询）。
# 维护须知：新增 ORM 模块（含 *_models.py 与聚合 re-export）必须同步加入下方清单，
# 否则该模块下的依赖不会被拦截。
source_modules =
    miles_portal.tenant.*.views
    miles_portal.tenant.*.schemas
    miles_admin.app_ops.views
    miles_admin.app_ops.schemas
    miles_admin.app_sys.views
    miles_admin.app_sys.schemas
    miles_openapi.views
# 必须列到**聚合包**层级：from miles_core.models.agent import X 的图边目标是包
# __init__ 而非叶子模块，只列叶子会漏网（实测）。
# 也因此，包内的纯 DTO 会被一并禁止 —— 这就是 §5.3 下沉的来由。
forbidden_modules =
    miles_core.models.agent
    miles_core.models.compliance
    miles_core.models.flow
    miles_core.models.kb
    miles_core.models.marketplace
    miles_core.models.media
    miles_core.models.meta
    miles_core.models.model
    miles_core.models.platform
    miles_core.models.risk
    miles_core.models.storage
    miles_core.models.task
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
allow_indirect_imports = True
```

两处需要说明的清单成员：

- `miles_core.models.compliance` **本身不含 ORM 表**（只有 `constants.py` 枚举与 `pipeline.py`），但它是 `SensitiveAction` 的定义处、且被 `miles_portal.tenant.compliance.models` 再导出。若不列入，schema 仍可经 `miles_core.models.compliance.constants` 绕道引用持久化枚举，与本设计的 G4 相悖。
- `miles_portal.tenant.prompts.models` / `skills.models` / `audit_log.models` 当前没有 `views/`/`schemas/` 引用它们，列入是为了边界的**完整性**（它们确实是 ORM），而非修复现存违规。

`miles_openapi.views` 纳入的理由：它是对外开放面，公开契约的解耦在这里收益最大；当前它只引用 `miles_portal...schemas`，纳入属廉价保险。

### 5.2 API 枚举归宿（21 个）

命名与成员值必须与 ORM 侧**逐字相同**（含成员顺序，因为 Pydantic 以枚举定义顺序生成 `enum` 数组）。

| 归宿 | 数量 | 枚举 |
|---|---|---|
| `miles_common/schemas/api_enums.py` | 3 | `TenantStatus`、`ModelVendor`、`ModelCapabilityType`（portal 与 admin 互不可见，`miles_common` 是二者唯一共同下层；后两者仅作 `.value` 默认值，不构成对外枚举组件） |
| `miles_common/schemas/marketplace.py`（随 DTO 下沉，§5.3） | 2 | `MarketplaceAppStatus`、`MarketplaceAppVisibility`（随 `marketplace.dto` 携带进入 API 面） |
| `miles_portal/tenant/<域>/schemas/enums.py` | 14 项 / 11 个文件 | `AgentStatus`、`AgentType`（agents）；`CategoryDomain`（categories）；`FlowStatus`（flows）；`GenerativeJobStatus`（generative）；`DocumentStatus`（kb）；`HookScope`、`HookTrigger`、`HookType`（hooks，同文件）；`McpStatus`（mcp）；`TaskStatus`（tasks）；`ToolType`（tools）；`A2aPeerStatus`（a2a）；`SensitiveAction`（compliance） |
| `miles_admin/app_ops/schemas/enums.py` | 2 | `RiskSeverity`、`BillStatus` |

合计 3 + 2 + 14 + 2 = **21**。

跨端枚举（5 个）必须在 `miles_common` 而非各写一份：portal 与 admin 互不可见，各写一份会产生**两个同名不同类**的枚举。虽经实测「同名同值」Pydantic 会合并成同一组件（快照不变），但那是三份定义（ORM + portal + admin）的漂移风险，无必要。

### 5.3 两个 DTO 模块下沉

| 原路径 | 新路径 | 消费者 |
|---|---|---|
| `miles_core.models.agent.chat_io` | `miles_common/schemas/chat_io.py` | `miles_ai` 3 文件 + portal `agents/schemas/agent.py` 的 re-export |
| `miles_core.models.marketplace.dto` | `miles_common/schemas/marketplace.py` | admin services 1 文件 + admin `views/marketplace_review.py` + portal `marketplace/schemas/marketplace.py` |

处置方式：

- **旧路径转 re-export 壳**（循 `miles_common/schemas/tag.py` 的先例），故 `miles_ai`(L2) 与 admin services 的 import **零改动**；
- 必须改的消费者只有 `views/`/`schemas/` 内的 3 处（§3.1 的 #3、#14、#26）；
- `miles_common` 是干净底层（实测：全包无任何对 `miles_core`/`miles_exec`/`miles_ai`/`miles_portal`/`miles_admin`/`miles_openapi`/`miles_server`/`miles_worker`/`miles_runner` 的 import），故下沉不引入反向边；
- `marketplace.dto` 的定义模块 `miles_core.models.marketplace.models`（ORM）**不 import** 该 DTO（实测），故下沉不产生环。

### 5.4 ORM 实体引用改造

`miles_portal/tenant/agents/schemas/schedule_run.py:10` 的 `AgentScheduleRun` 只用于 `from_model` 的入参注解：

```python
@classmethod
def from_model(cls, entity: AgentScheduleRun) -> AgentScheduleRunOut:
    return cls.model_validate(entity)
```

改为**去掉注解**，与同目录既有写法一致（`agents/schemas/schedule.py:61` 的 `def from_model(cls, entity) -> "AgentScheduleOut"` 本就不注解 ORM 实体）：

```python
@classmethod
def from_model(cls, entity) -> AgentScheduleRunOut:
    return cls.model_validate(entity)
```

调用点 `agents/services/schedule.py:117` 的 `AgentScheduleRunOut.from_model(i)` 不变。不用 `TYPE_CHECKING` 包裹——实测它同样被判违规（§3.3 第 4 条）；也不用 `Protocol` 新类型，因为同目录已有更简的先例。

### 5.5 迁移面

- 新增文件：`miles_common/schemas/api_enums.py`、`miles_common/schemas/chat_io.py`、`miles_common/schemas/marketplace.py` + 11 个 portal `schemas/enums.py` + 1 个 admin `schemas/enums.py` = **15 个新文件**；
- 修改文件：§3.1 的 **27 个文件全部需要改 import 指向**（枚举换声明处、DTO 换新路径、实体去注解）；
- 旧路径转 re-export 壳：`miles_core/models/agent/chat_io.py`、`miles_core/models/marketplace/dto.py`（2 个文件改为 re-export）；
- `.importlinter`：新增第 7 条契约；
- 测试：新增枚举平价测试（§6.1）。

---

## 6. 护栏与验证

### 6.1 枚举平价测试（新增）

新增 `backend/tests/models/test_api_enum_parity.py`，对 21 对「API 声明 ↔ ORM 定义」逐成员比对（与既有 `tests/models/test_enum_contract.py` 同目录，便于集中发现枚举类护栏）：

- 成员名集合与顺序一致；
- 成员值一致；
- 基类为 `StrEnum`。

选择测试而非依赖快照 diff 的原因：快照漂移的失败信息是一个巨大的 JSON diff，无法直指「哪个枚举的哪个成员漂移」；平价测试的失败信息可以写成 `AgentStatus.ENABLED 的 API 值 'enable' != ORM 值 'enabled'`。两者互补而非替代。

### 6.2 五道门禁

| 门禁 | 本设计的作用 |
|---|---|
| `ruff format --check .` | 保证新文件风格 |
| `ruff check .` | 保证新文件 lint 干净（注意 re-export 壳与 `__all__` 的 `F401` 关系，见 §7 R4） |
| `lint-imports` | **本设计的主门禁**：第 7 条契约须 `KEPT`，且原 6 条仍 `KEPT`（新增契约不得误伤既有边） |
| `export_openapi --check` | **快照必须逐字节不变**（G3） |
| `python -m pytest -q` | 全量回归；基线 1122，新增平价测试后递增 |

### 6.3 敏感度对照（必须做，否则门禁可能形同虚设）

对三道关键门禁各做一次「故意破坏 → 必须报错 → 还原」：

1. **契约敏感度**：临时把某个 API 枚举的 import 改回 ORM 路径 → `lint-imports` 必须报出该文件；还原后必须重新 `KEPT`。
2. **快照敏感度**：临时把某个 API 枚举的某个值改错 → `export_openapi --check` 必须失败；还原后必须通过。
3. **平价测试敏感度**：临时改错一个成员值（或删一个成员）→ 平价测试必须失败。

---

## 7. 风险与对策

| # | 风险 | 对策 |
|---|---|---|
| R1 | API 枚举与 ORM 枚举名字相同但内容漂移——Pydantic 会塌成 `xxx__1/__2` 组件名，正常能被 `--check` 抓到；但若漂移恰好发生在**未暴露**的 `.value` 默认值上，快照可能不报 | §6.1 的平价测试覆盖全部 21 对，含 2 个非对外枚举 |
| R2 | 契约清单随新增 ORM 模块漂移（新增 `*.models` 未登记则边界有洞） | 契约内写明维护须知（§5.1 注释）；本设计不承诺自动发现，这是「逐条列举」方案的已知代价 |
| R3 | 新增契约误伤既有边（如源通配匹配到非预期包） | §6.3 敏感度对照 + 第 7 条 `KEPT` 时原 6 条亦须 `KEPT`；实施时需先实跑确认违规清单恰为 §3.1 的 27 个文件 |
| R4 | re-export 壳与 `__all__` 触发 `F401` | 循 toolkit 拆分时已确立的做法：非 `__init__.py` 的 re-export 模块需显式 `__all__`，否则 `ruff` 报未使用导入（该文件级检测不认 `__all__` 之外的用途） |
| R5 | `miles_common` 承载 API 契约枚举，定位从「基础原语」扩到「API 契约」 | 有 `tag.py` 先例支撑（同为跨域共用的中立模型）；若将来要独立成包，`miles_common/schemas/` 可整体迁出，成本可控 |
| R6 | 新增 15 个文件（含 11 个 portal `schemas/enums.py`）增加文件数 | 与仓内「域自持、跨域下沉」的既有约定一致（各域已有 `meta.py`）；备选是全部集中 `miles_common`，用户已确认采用分域方案 |
| R7 | `miles_common/schemas/marketplace.py` 同时承载 DTO 与枚举，职责偏杂 | 与现状一致（`marketplace.dto` 本就同时含 DTO 与枚举 re-export），不额外恶化 |

---

## 8. 验证判据（完成定义）

1. §3.1 的 28 处 import 全部迁移；`views/`/`schemas/` 下对 ORM 模块的直接 import 为 **0**（以 §3.1 的 AST 复现脚本复算）；
2. 第 7 条契约 `KEPT`，原 6 条契约仍 `KEPT`；
3. `export_openapi --check` 通过，且快照文件**逐字节未变**（`git diff --stat` 对 `openapi/openapi.snapshot.json` 为空）；
4. 21 对枚举的平价测试通过，且 §6.3 的三项敏感度对照全部按期失败；
5. 五道门禁全绿；
6. ORM 侧零改动：`git diff` 中 `miles_core/models/**` 的改动只允许 `chat_io.py`、`marketplace/dto.py` 两个 re-export 壳，且 Alembic 目录零改动。

---

## 9. 后续（不在本次范围）

- 各域 `meta.py` 仍引用 ORM 枚举（不在契约源内）。若要让 `/meta` 端点也走 API 枚举，属独立改动，本次不做。
- `marketplace.dto` 与 `chat_io` 的旧路径 re-export 壳可择机清理（需先迁移所有消费者）。
- 契约清单的自动生成（从 `__tablename__` 扫描产物生成 `forbidden_modules`）是消除 R2 的正解，本次不做。

---

## 10. 修订记录

- 2026-09-17 首稿。基于只读勘察与本仓实跑的探针：27 文件 / 28 处违规面、19 个对外枚举归属、四项契约可表达性结论（中缀通配受支持、必须列聚合包层级、`allow_indirect_imports` 必需、`TYPE_CHECKING` 同样被抓）、两个 DTO 模块的下沉方案、`from_model` 去注解的既有先例。
- 2026-09-17 **自审修正**：初稿 §3.1 的分类计数（写成 17+2+4+1）、§5.2 的 `api_enums` 计数（写成 5）、portal 文件数（写成 12）、§5.5/§7 的新文件总数（写成 17）均有误，已改为机器复算值：枚举行 22 / 取值行 2 / DTO 行 3 / 实体行 1 = 28 处；去重后 17（作类型）+ 2（取值）+ 2（随 DTO 携带）= **21** 个枚举；新文件 **15** 个（11 portal + 3 `miles_common` + 1 admin）。复算脚本见 §3.1 的「复现方式」。

---

## 11. 实施方式

按本仓惯例，实施前需先决定是否在新 worktree + 特性分支上执行（与 `feat/langchain-toolkit-split`、`feat/up042-strenum` 同形），并经 `writing-plans` 生成逐任务实施计划。
