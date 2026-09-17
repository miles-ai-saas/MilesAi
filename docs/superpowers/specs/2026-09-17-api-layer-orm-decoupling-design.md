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
- G2 该边界由新增的 import-linter 契约硬禁，且**新域、新文件自动纳入**（源文件通配自动覆盖；`miles_core` / `miles_admin` 的新增 ORM 模块因列的是父聚合也自动覆盖，仅新增 portal 域的 `models.py` 需登记）；
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

明细（文件:行 → 被引用模块 → 名称）。**「行」列是改造前审计快照**（迁移动工前扫到的原始行号；如 `agents/schemas/agent.py` 的 14 在 Task 1 docstring + Task 3 isort 后已下移到 22），不要拿它去当前文件里定位：

| # | 文件 | 行（改造前快照） | 被引用模块 | 名称 | 类别 |
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

五项结论均以临时契约在隔离沙箱或本仓实跑得到，是 §5.1 契约形状的直接依据：

1. **中缀通配符受支持**：`source_modules = miles_portal.tenant.*.views` 能解析出 `miles_portal.tenant.workbench.views` 等并正常判定。通配按 fnmatch 语义（`*` 可跨 `.`），故 `miles_portal.tenant.*.models` 不会误伤「模型目录」域（实测 `miles_portal.tenant.models.views` → 自家 `...models.schemas.model` 未被判违规，因为模式两端锚定：目标以 `.model` 结尾，不匹配以 `.models` 结尾的模式）。
2. **必须列到聚合包层级**：`forbidden_modules = miles_core.models.agent.agent`（叶子）对 `from miles_core.models.agent import AgentType` **判定为 KEPT（漏网）**——该 import 的图边目标是包 `miles_core.models.agent`，即聚合 `__init__`，不是叶子模块。改列 `miles_core.models.agent` 后正确报出。
3. **`allow_indirect_imports = True` 是必需的**：不加会沿 `views → miles_core.deps → miles_core.models.platform.user` 这类链误报（`miles_core.deps` 本身会拉到 models，但那是 deps 的职责，不是视图的违规）。
4. **`TYPE_CHECKING` 与函数内 import 同样被判违规**：实测三种写法（模块顶层、`if TYPE_CHECKING:` 内、函数体内）全部报出。故类型注解**不是**逃逸口，§5.4 必须结构性改造。
5. **必须列到最外层「胖聚合」包，否则被地道写法绕过**（§5.1 清单按此收敛）：
   - `from miles_core.models.agent import AgentType`（图边 → `miles_core.models.agent`）：列子域包即被抓；
   - `from miles_core.models import AgentStatus`（图边 → **`miles_core.models`**，取父包 `__init__` 自身 re-export 的名字）：只列子域包时**静默通过**；
   - `from miles_core.models import agent`（先取子模块再取属性）：实测会解析到子模块边 `miles_core.models.agent`，**被抓**——故逃逸面仅限「父包自身属性」这一种。
   `miles_core/models/__init__.py` 恰好是胖聚合（实测 `__all__` 43 个名字，含 8 个持久化枚举，且带 `__all__`），而 `from miles_core.models import X` 正是本仓惯用写法，故这一条必须堵。
   已核实收敛安全：对 `views/`、`schemas/` 做全量 AST 扫描，对 `miles_core.models.*` 的引用**恰好**是 §3.1 的 28 处，无任何「合法的非 ORM」引用会被误伤。
   对照：portal 侧 9 个 ORM 入口全是 `models.py` **模块**（非包），且 `miles_portal/tenant/__init__.py` 无 re-export，故那边列到子域即可；admin 侧列 `miles_admin.models` 本身就是父包，spec 原本即正确。

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
# 更要紧的是必须列到**最外层胖聚合**：miles_core/models/__init__.py 自身 re-export
# 了 43 个名字（含 8 个持久化枚举）且带 __all__，故 from miles_core.models import
# AgentStatus 的图边目标是 miles_core.models —— 只列子域包会静默放过（实测，见 §3.3 第 5 条）。
# 也因此，被禁包内的纯 DTO 会被一并禁止 —— 这就是 §5.3 下沉的来由。
forbidden_modules =
    # 父聚合一条覆盖全部子域，含 __init__ 自身 re-export 的 43 个名字。
    # 附带收益：miles_core.models 下新增模块自动被拦，无需登记（缓解 §7 R2）。
    miles_core.models
    # admin 侧列的就是父包（其 __init__ re-export BillStatus / RiskSeverity）。
    miles_admin.models
    # portal 侧全部是 models.py 模块（非包），且 tenant/__init__.py 无 re-export，
    # 故无父聚合逃逸面；新增 portal 域需在此登记。
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

清单按「最外层聚合」收敛后的三点说明：

- **`miles_core.models` 一条覆盖 12 个子域**（platform / kb / flow / model / media / meta / task / storage / agent / marketplace / risk / compliance）。这既堵住 §3.3 第 5 条的父包逃逸，又把清单从 20 条压到 10 条。
- **代价是一条整包禁令**：`views/`/`schemas/` 因此也不得引用 `miles_core.models.base`（mixin）、`media.reader`、`tool.parameters` 等非 ORM 模块。已实测当前零引用，故无实际损失；若将来确需引用，正解是把该中立模块下沉 `miles_common`，而不是放宽契约——否则父包逃逸面会重新打开。
- **`miles_portal.tenant.prompts.models` / `skills.models` / `audit_log.models`** 当前没有 `views/`/`schemas/` 引用它们，列入是为了边界的**完整性**（它们确实是 ORM），而非修复现存违规。

`miles_openapi.views` 纳入的理由：它是对外开放面，公开契约的解耦在这里收益最大；当前它只引用 `miles_portal...schemas`，纳入属廉价保险。

### 5.2 API 枚举归宿（21 个）

基类、命名、成员值、类 docstring 必须与 ORM 侧**逐字相同**（含成员顺序，因为 Pydantic 以枚举定义顺序生成 `enum` 数组；类 docstring 会被 Pydantic 渲染进 schema 的 `description`，漏抄会静默漂移 OpenAPI 快照——Task 3 实测 5 条 description）。

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

新增 `backend/tests/models/test_api_enum_parity.py`，对 21 对「API 声明 ↔ ORM 定义」逐项比对（与既有 `tests/models/test_enum_contract.py` 同目录，便于集中发现枚举类护栏）：

- 基类一致（都是 `enum.StrEnum`）；
- 成员名集合与顺序一致；
- 成员值一致；
- 类 docstring 一致（Pydantic 会把它渲染成 schema 的 `description`，故同属「逐字一致」的范畴）。

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
4. **父聚合逃逸敏感度**：临时把某个 API 枚举的 import 改成父包属性写法 `from miles_core.models import <枚举>` → `lint-imports` 必须报出；还原后必须重新 `KEPT`。这一条专门验 §3.3 第 5 条的洞确实被 §5.1 的收敛清单堵住。

---

## 7. 风险与对策

| # | 风险 | 对策 |
|---|---|---|
| R1 | API 枚举与 ORM 枚举名字相同但内容漂移——Pydantic 会塌成 `xxx__1/__2` 组件名，正常能被 `--check` 抓到；但若漂移恰好发生在**未暴露**的 `.value` 默认值上，快照可能不报 | §6.1 的平价测试覆盖全部 21 对，含 2 个非对外枚举 |
| R2 | 契约清单随新增 ORM 模块漂移（新增 `*.models` 未登记则边界有洞） | **已缩减**：`miles_core.models` 与 `miles_admin.models` 列的是父聚合，其下新增模块自动被拦；残余仅「新增 portal 域的 `models.py`」需登记（§5.1 注释）。仍不承诺自动发现 |
| R3 | 新增契约误伤既有边（如源通配匹配到非预期包） | §6.3 敏感度对照 + 第 7 条 `KEPT` 时原 6 条亦须 `KEPT`；实施时需先实跑确认违规清单恰为 §3.1 的 27 个文件 |
| R4 | re-export 壳与 `__all__` 触发 `F401` | 循 toolkit 拆分时已确立的做法：非 `__init__.py` 的 re-export 模块需显式 `__all__`，否则 `ruff` 报未使用导入（该文件级检测不认 `__all__` 之外的用途） |
| R5 | `miles_common` 承载 API 契约枚举，定位从「基础原语」扩到「API 契约」 | 有 `tag.py` 先例支撑（同为跨域共用的中立模型）；若将来要独立成包，`miles_common/schemas/` 可整体迁出，成本可控 |
| R6 | 新增 15 个文件（含 11 个 portal `schemas/enums.py`）增加文件数 | 与仓内「域自持、跨域下沉」的既有约定一致（各域已有 `meta.py`）；备选是全部集中 `miles_common`，用户已确认采用分域方案 |
| R7 | `miles_common/schemas/marketplace.py` 同时承载 DTO 与枚举，职责偏杂 | 与现状一致（`marketplace.dto` 本就同时含 DTO 与枚举 re-export），不额外恶化 |

---

## 8. 验证判据（完成定义）

1. §3.1 的 28 处 import 全部迁移；`views/`/`schemas/` 下对 ORM 模块的直接 import 为 **0**（以 §3.1 的 AST 复现脚本复算）；
2. 第 7 条契约 `KEPT`，原 6 条契约仍 `KEPT`；且 §6.3 的四项敏感度对照全部按期失败（含父聚合逃逸那一项）；
3. `export_openapi --check` 通过，且快照文件**逐字节未变**（`git diff --stat` 对 `openapi/openapi.snapshot.json` 为空）；
4. 21 对枚举的平价测试通过；
5. 五道门禁全绿；
6. ORM 侧零改动：`git diff` 中 `miles_core/models/**` 的改动只允许 `chat_io.py`、`marketplace/dto.py` 两个 re-export 壳，且 Alembic 目录零改动。

---

## 9. 后续（不在本次范围）

- 各域 `meta.py` 仍引用 ORM 枚举（不在契约源内）。若要让 `/meta` 端点也走 API 枚举，属独立改动，本次不做。
- `marketplace.dto` 与 `chat_io` 的旧路径 re-export 壳可择机清理（需先迁移所有消费者）。
- 契约清单的自动生成（从 `__tablename__` 扫描产物生成 `forbidden_modules`）是消除 R2 的正解，本次不做。

---

## 10. 修订记录

- 2026-09-17 首稿。基于只读勘察与本仓实跑的探针：27 文件 / 28 处违规面、19 个对外枚举归属、契约可表达性结论（中缀通配受支持、必须列聚合包层级、`allow_indirect_imports` 必需、`TYPE_CHECKING` 同样被抓）、两个 DTO 模块的下沉方案、`from_model` 去注解的既有先例。
- 2026-09-17 **自审修正**：初稿 §3.1 的分类计数（写成 17+2+4+1）、§5.2 的 `api_enums` 计数（写成 5）、portal 文件数（写成 12）、§5.5/§7 的新文件总数（写成 17）均有误，已改为机器复算值：枚举行 22 / 取值行 2 / DTO 行 3 / 实体行 1 = 28 处；去重后 17（作类型）+ 2（取值）+ 2（随 DTO 携带）= **21** 个枚举；新文件 **15** 个（11 portal + 3 `miles_common` + 1 admin）。复算脚本见 §3.1 的「复现方式」。
- 2026-09-17 **契约漏洞修正（用户已确认收敛方案）**：写实施计划前的隔离沙箱探针发现，只列子域包时 `from miles_core.models import AgentStatus`（图边指向**父聚合自身**）会**静默通过**，而它正是本仓惯用写法（`miles_core/models/__init__.py` re-export 43 个名字含 8 个枚举）。故 §5.1 的 `forbidden_modules` 由 20 条收敛为 10 条：12 条 `miles_core.models.<子域>` → 1 条 `miles_core.models`。新增 §3.3 第 5 条记录该探针（含「`from miles_core.models import agent` 取子模块会被抓，故逃逸面仅限父包自身属性」这一区分），§6.3 增加第 4 项敏感度对照，§7 R2 相应缩减，§2.1 G2 与 §8 判据同步更新。收敛安全性已实测：views/schemas 对 `miles_core.models.*` 的引用恰好是 §3.1 的 28 处，无合法的非 ORM 引用被误伤。
- 2026-09-17 **数字勘误（Task 5 执行期实测）**：`miles_core/models/__init__.py` 的 `__all__` 实为 **43** 个名字（此前 spec/plan 多处写 45，无任何度量依据）。同时订正两处执行细节：敏感度对照第 1 项的行号由 14 下移到 **22**（Task 1 docstring + Task 3 isort 变动所致，改为按内容定位）；第 2 项原写 `from miles_core.models import AgentStatus, AgentType`，但 **`AgentType` 未被父包 re-export**（8 个被 re-export 的枚举中不含它），该写法导入语义本身不成立，已改为只用 `AgentStatus`。
- 2026-09-17 **终检实测回填（Task 6，BASE = `a1e6e95a`，HEAD = 终检提交前 `40e06362`）**：
  - 终检 6 项逐条实测：探测器 `scan_orm_sites.py` → `TOTAL=0`；`lint-imports` → `Contracts: 7 kept, 0 broken.`（analyzed 772 files / 2515 dependencies）；快照 → `git diff --stat $BASE -- openapi/openapi.snapshot.json` 空输出；ORM 侧零改动 → `models/` 下**恰好 2 个 re-export 壳**（`models/agent/chat_io.py`、`models/marketplace/dto.py`）、`alembic/` 空、`(enum.StrEnum)`/`values_callable`/`SAEnum` 改动行 `0`、`pyproject.toml` 的 `values_callable =` 改动 `0`；平价测试 `tests/models/test_api_enum_parity.py` → **`45 passed`**；五道门禁 → `ruff format --check .`（979 files already formatted）、`ruff check .`（All checks passed!）、`lint-imports`（7 kept）、`export_openapi --check`（OK）、`pytest -q` → **1167 passed in 12.54s**。
  - **实际文件数 vs §5.5 预估**：新增 15 个如期（11 portal `schemas/enums.py` + 3 `miles_common` + 1 admin），另加 1 个新测试文件 `tests/models/test_api_enum_parity.py`（§5.5 单列）→ 共 16；修改 30 项如期（§3.1 的 27 个全部命中 + `.importlinter` + 2 个壳），另加 `tests/tenant/agents/test_agent_chat_io_shim.py`（Task 1 Step 8 补 `ChatRequest is common_chat_io.ChatRequest` 断言）→ 共 31，比预估多 1。
  - **pytest 1167 = 基线 1122 + 45**，+45 恰为新平价测试文件全部用例：逐字比对 21 + 独立声明 21 + 表完整性 1 + `is` 比较守卫 1 + **名称级守卫 1（Task 5b 追加，故 Task 5 时的 1166/44 升为 1167/45）**。
  - **Task 5b 的两道互补门禁（用户裁决方案 B）**：`api-layer-no-orm` 契约必须设 `allow_indirect_imports = True`（否则 36 处 `views`/`schemas` → `miles_core.deps` → ORM 的引用全成误报），故**只能拦直接依赖**；经中间模块的一跳借用（`from ...agents.meta import AgentStatus`，`meta` 自身 import 了该 ORM 枚举）实测契约仍报 `7 kept`、探测器仍 `TOTAL=0` —— 两道门全绿而耦合已回流。补位的是 `test_api_enum_parity.py::test_enum_names_imported_only_from_allowlisted_modules`：按「导入名 + 来源模块白名单」判定、不依赖图边，覆盖 `from <非白名单模块> import <枚举名>` 形态（含相对 import）。两者职责互补，**缺一即有静默漏洞**。
  - **名称级守卫的已知边界（需模块属性流/图分析，有意不堵）**：`from X import meta` 再 `meta.AgentStatus`（导入的是模块名而非枚举名）、`import X as m` 再 `m.AgentStatus`（裸 `import` 的绑定名不是枚举名）均不受覆盖；`from X import enums` 再 `enums.AgentStatus` 引的就是白名单模块本身，不算漏洞。
  - **其余偏差**：前置专项 U042（`(str, Enum)` → `StrEnum` 迁移，§2.2 N5）无偏差 —— 本支线对 `models/` 的枚举基类/成员值/`values_callable` 改动为 0（见上「ORM 侧零改动」），U042 的等价性结论继续成立。除此之外与预估一致（新文件数、契约条数 6→7、快照逐字节不变）。
  - **同提交的文档陈旧清扫**（用户 2026-09-17 裁决「全做」）：plan 内嵌的正则版 `is` 判据与三项 `_mismatch_report` 删除并改为指向真实测试文件、记录判据要点（五项全等 / AST 判据 / 名称级守卫）；修 `marketpalce` 拼写；plan 模块 docstring 模板与 5 个带类 docstring 的声明文件补「类 docstring」；plan Task 3 表与 §3.1 表加「（改造前快照）」消歧（行号数值 14/15 保持原样、只声明其口径）；plan 内嵌 `.importlinter` 契约块补齐 Task 5b 的注释；plan 的 18 类内嵌块补回 5 个类 docstring。
- 2026-09-17 **整支线终审后的收尾修补（用户裁决「修完 3 条再合并」，`cd588652` + 其后一次 docstring 提交）**：
  - 终审结论：**可合并，无阻塞项**。独立复算确认 176 个 `views`/`schemas` 文件对 ORM 包的直接 import 归零；21 对枚举平价零差异；等价性在 SQLAlchemy `bind_processor` 绑定外来枚举、Pydantic 强转、`==`/`hash`/`in` 三处边界实测成立；唯一不等价的 `is` 在 `packages/` 下零命中。
  - **修补 1（真实 bug）**：`_module_and_package` 对 `__init__.py` 少算一层 —— 模块 `a.b/__init__.py` 的 `__package__` 是 `a.b` 本身，旧实现再剥一层得 `a`，使 `schemas/__init__.py` 里的 `from .enums import X` 被解析成**不存在的** `...categories.enums`（真值 `...categories.schemas.enums` 在白名单内）→ **假失败**且报错指向不存在的模块。已按 `is_init` 区分修正（潜伏缺陷：仓内相对 import 当前为 0）。敏感性：临时造真实相对 import 触发点，旧逻辑报假失败、新逻辑通过。
  - **修补 2（堵终审判定的最深风险）**：`CASES`/`_ENUM_NAMES` 是人工清单，**新增对外持久化枚举时三道护栏同时 fail-open**（契约拦不住一跳借用形态、名称级守卫认不得新名字、`test_parity_table_covers_exactly_21_enums` 只查项数）。新增 `test_parity_table_covers_every_enum_in_openapi_snapshot`：反向以快照为准，断言 `components.schemas` 中带 `enum` 键的组件名集合 ⊆ `CASES` 名字集合（实测 `19 ⊆ 21`）。敏感性：临时从 `CASES` 删 1 项 → 必须 FAILED 并报出缺失名。
  - **修补 3（docstring 与代码不一致）**：`models/agent/chat_io.py` 壳曾声称 portal `agents/schemas/agent.py` 的 re-export 指向它，而后者已直连 `miles_common.schemas.chat_io`（必须如此，否则撞契约）；同步修正 plan 的同源句。另修 `agent.py` 头部 docstring 的反向陈述（原写「（经 ``miles_core.models.agent.chat_io`` re-export 壳）」，与修正后的壳 docstring 直接矛盾）与 `test_no_identity_comparison_on_enum_members` 的「全仓」措辞（实现只扫 `packages/`）。
  - 终态：`Contracts: 7 kept, 0 broken.` / `OpenAPI snapshot OK` / `TOTAL=0` / `pytest -q` → **1168 passed**（1167 + 新增快照绑定用例）。

---

## 11. 实施方式

用户已确认：在**新 worktree + 特性分支**上执行（与 `feat/langchain-toolkit-split`、`feat/up042-strenum` 同形）：

- worktree：`.worktrees/api-layer-orm-decoupling`
- 分支：`feat/api-layer-orm-decoupling`（自 `main` 切出，禁止直接在 `main` 上改）

逐任务实施计划见 `docs/superpowers/plans/2026-09-17-api-layer-orm-decoupling.md`（由 `writing-plans` 生成）。
