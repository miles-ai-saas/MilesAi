"""API 侧枚举声明与 ORM 侧的逐字一致护栏，以及「不得 `is` 比较枚举成员」的守卫。

背景：API 声明层（``views/`` / ``schemas/``）不得 import ORM 包（``.importlinter``
契约 ``api-layer-no-orm``），故 21 个持久化枚举在 API 侧各有一份**独立声明**。
本模块把「两份定义逐字一致」变成可执行约束：基类、成员名、成员顺序、成员值、类 docstring
五项全等。类 docstring 也在其列，因为 Pydantic 会把 enum 类 docstring 渲染成 schema 的
``description`` —— 漏抄会静默漂移 ``openapi.snapshot.json``（Task 3 实测：5 个带 docstring
的 ORM 枚举曾因此丢掉 description）。

为什么不能只靠 OpenAPI 快照：快照漂移的失败信息是一整份 JSON diff，指不出是哪个枚举的
哪个成员；本模块的失败信息能直接写成 ``AgentStatus.ENABLED 的 API 值 'enable' != ORM 值 'enabled'``。
两者互补而非替代。

第二个不变量：不得对枚举成员做 ``is`` / ``is not`` 比较。两份声明是**不同类**；
``StrEnum`` 的 ``==`` / ``hash`` / ``str`` / ``format`` 都按值成立（实测，见设计 §3），
唯独 ``is`` 跨类恒为 ``False`` —— 这是本设计唯一会静默出错的写法。

第三个不变量：``views/`` / ``schemas/`` 只能从各域 ``*.schemas.enums`` 白名单模块引入这 21 个枚举名。
``.importlinter`` 的 ``api-layer-no-orm`` 契约必须设 ``allow_indirect_imports = True``，否则 36 处
``views`` / ``schemas`` 对 ``miles_core.deps`` 的引用会因 ``deps`` 自身 import ORM 而全成误报；
代价是经中间模块的一跳借用（如 ``from ...agents.meta import AgentStatus``，而 ``meta`` 自己 import 了
ORM 枚举）可绕开契约 —— 实测此时契约仍报 ``7 kept``。本守卫按「导入名 + 来源模块」判定、不依赖图边，
正好补上契约拦不住的那一段；两者合起来才完整。

第四个不变量：``CASES`` 的名字集合、``_ENUM_NAMES``、``_ENUM_IMPORT_ALLOWLIST`` 与 API 侧实际声明
必须四向一致。这三个常量都是人工清单，任一漂移都会让守卫对着错误的名字集合工作（实测把表内两个名字
改坏后全套 46 项仍通过），故以「按目录约定扫出的声明」为锚，而非再列一份硬编码清单。
"""

from __future__ import annotations

import ast
import enum
import json
from pathlib import Path

import pytest

from miles_admin.app_ops.schemas import enums as admin_enums
from miles_admin.models import billing as orm_admin_billing
from miles_common.schemas import api_enums as common_enums
from miles_common.schemas import marketplace as common_marketplace
from miles_core.models import risk as orm_risk
from miles_core.models.agent import agent as orm_agent
from miles_core.models.compliance import constants as orm_compliance
from miles_core.models.flow import flow as orm_flow
from miles_core.models.kb import knowledge_base as orm_kb
from miles_core.models.marketplace import models as orm_marketplace
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


def _mismatch_report(name: str, api: type[enum.Enum], orm: type[enum.Enum]) -> str:
    """返回首个不一致的可读描述；完全一致时返回空串。

    按「基类 → 成员名/顺序 → 成员值 → 类 docstring」短路。四项都是 Pydantic 生成 schema 的
    输入（类 docstring 渲染成 ``description``），故都必须逐字一致。
    """
    if api.__bases__ != orm.__bases__:
        return f"{name} 的直接基类不一致：API={api.__bases__} ORM={orm.__bases__}"
    api_pairs = [(m.name, m.value) for m in api]
    orm_pairs = [(m.name, m.value) for m in orm]
    if [n for n, _ in api_pairs] != [n for n, _ in orm_pairs]:
        return f"{name} 的成员名或顺序不一致：API={[n for n, _ in api_pairs]} ORM={[n for n, _ in orm_pairs]}"
    for member_name, api_value in api_pairs:
        orm_value = dict(orm_pairs)[member_name]
        if api_value != orm_value:
            return f"{name}.{member_name} 的 API 值 {api_value!r} != ORM 值 {orm_value!r}"
    if api.__doc__ != orm.__doc__:
        return f"{name} 的 API 类 docstring {api.__doc__!r} != ORM 类 docstring {orm.__doc__!r}"
    return ""


@pytest.mark.parametrize(("name", "api", "orm"), CASES, ids=[c[0] for c in CASES])
def test_api_enum_is_an_independent_declaration(name, api, orm):
    """API 侧必须是独立类；转 re-export 会字面满足契约而公开契约仍绑 ORM（设计 §4 已否决）。"""
    assert api is not orm, f"{name} 在 API 侧是 ORM 枚举的 re-export，不是独立声明"


@pytest.mark.parametrize(("name", "api", "orm"), CASES, ids=[c[0] for c in CASES])
def test_api_enum_matches_orm_verbatim(name, api, orm):
    """基类、成员名、成员顺序、成员值、类 docstring 必须与 ORM 侧逐字一致。

    前四项决定 Pydantic 生成的 ``enum`` 数组，类 docstring 决定 ``description``。
    """
    assert issubclass(api, enum.StrEnum), f"{name} 的 API 声明不是 enum.StrEnum"
    report = _mismatch_report(name, api, orm)
    assert not report, report


_BACKEND = Path(__file__).resolve().parents[2]
_PACKAGES = _BACKEND / "packages"
_OPENAPI_SNAPSHOT = _BACKEND / "openapi" / "openapi.snapshot.json"
_ENUM_NAMES = frozenset(name for name, _, _ in CASES)

# 这 21 个枚举名在 API 侧被允许的**引入来源模块**白名单（实测当前 19 个 (模块, 名) 组合全在其中）。
# 前两个是跨端共用声明地，其余是本域 ``schemas/enums.py`` 声明；views/schemas 之外的文件不在扫描面内。
_ENUM_IMPORT_ALLOWLIST = frozenset(
    {
        "miles_common.schemas.api_enums",
        "miles_common.schemas.marketplace",
        "miles_admin.app_ops.schemas.enums",
        "miles_portal.tenant.a2a.schemas.enums",
        "miles_portal.tenant.agents.schemas.enums",
        "miles_portal.tenant.categories.schemas.enums",
        "miles_portal.tenant.compliance.schemas.enums",
        "miles_portal.tenant.flows.schemas.enums",
        "miles_portal.tenant.generative.schemas.enums",
        "miles_portal.tenant.hooks.schemas.enums",
        "miles_portal.tenant.kb.schemas.enums",
        "miles_portal.tenant.mcp.schemas.enums",
        "miles_portal.tenant.tasks.schemas.enums",
        "miles_portal.tenant.tools.schemas.enums",
    }
)

# 契约 ``api-layer-no-orm`` 的目录级范围：这三个包下的 ``views/`` / ``schemas/`` 是 API 声明层。
_API_PACKAGES = frozenset({"miles-admin", "miles-openapi", "miles-portal"})
_API_DECL_DIRS = frozenset({"views", "schemas"})


def _scan_declaration_files() -> list[Path]:
    """按目录约定列出 API 侧枚举的候选声明文件：各包 ``*/schemas/enums.py`` + ``miles_common/schemas/*.py``。"""
    paths: list[Path] = []
    for path in sorted(_PACKAGES.glob("*/src/**/*.py")):
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(_PACKAGES)
        is_enums = path.name == "enums.py" and "schemas" in rel.parts
        is_common = rel.parts[0] == "miles-common" and rel.parts[-2:-1] == ("schemas",)
        if is_enums or is_common:
            paths.append(path)
    assert paths, f"未扫到任何声明文件，扫描面已失效（目录改名？）：{_PACKAGES}"
    return paths


def _declared_api_enums() -> dict[str, Path]:
    """扫出 API 侧声明的枚举名 -> 声明文件（类名去重，取首次声明）。

    扫描面是目录约定，与 ``_ENUM_IMPORT_ALLOWLIST`` 描述同一批「合法声明地」；两者的一致性由
    ``test_enum_import_allowlist_matches_declaration_modules`` 绑定，避免本函数与白名单各自漂移。
    """
    found: dict[str, Path] = {}
    for path in _scan_declaration_files():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.ClassDef):
                continue
            bases = {(base.id if isinstance(base, ast.Name) else getattr(base, "attr", None)) for base in node.bases}
            if bases & {"StrEnum", "Enum"}:
                found.setdefault(node.name, path)
    return found


def _enum_class_of(operand: ast.expr) -> str | None:
    """若 ``operand`` 形如 ``<任意前缀>.ClassName.MEMBER`` 且 ``ClassName`` 是已知枚举类，返回它。

    覆盖 ``Name.MEMBER``、``alias.ClassName.MEMBER``、``pkg.mod.ClassName.MEMBER`` 三种写法
    —— 后两种正是迁移后 ``from ...schemas import enums as X`` 的风格，旧判据（要求
    ``operand.value`` 是 ``ast.Name``）会漏检。

    已核实的边界（当前仓均不存在，要堵需模块属性流分析，代价远超收益，有意接受）：

    - **类被别名时漏检**：``from ... import McpStatus as S`` 再 ``S.ACTIVE is x`` —— 判据取属性名，
      而这里属性名是 ``S``。模块别名（``import ... as X``）不受影响，因为被取属性名仍是类名。
    - **非成员属性误报**：``X.McpStatus.<任意属性>`` 一律判为违规，如 ``X.McpStatus.__members__ is y``。
      保守方向是「多报」而非「漏报」，可接受。
    """
    if not isinstance(operand, ast.Attribute):
        return None
    parent = operand.value
    if isinstance(parent, ast.Name):
        class_name = parent.id
    elif isinstance(parent, ast.Attribute):
        class_name = parent.attr
    else:
        return None
    return class_name if class_name in _ENUM_NAMES else None


def _identity_comparisons(path: Path) -> list[tuple[int, str]]:
    """返回该文件里对枚举成员做 ``is`` / ``is not`` 比较的 (行号, 表达式)。"""
    found: list[tuple[int, str]] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.Compare) or not any(isinstance(op, (ast.Is, ast.IsNot)) for op in node.ops):
            continue
        for operand in [node.left, *node.comparators]:
            if _enum_class_of(operand):
                found.append((node.lineno, ast.unparse(operand)))
    return found


def test_no_identity_comparison_on_enum_members():
    """两份声明是不同类，`is` 跨类恒为 False —— `packages/` 内生产代码禁止该写法。

    用 AST 判据而非文本匹配：注释与 docstring 里的说明性提及不应误伤（同 ``tests/test_l3_neutral_imports.py``
    的意图，但那里的目标是 import 语句、这里是比较表达式，故收紧为语法级）。
    """
    paths = [p for p in sorted(_PACKAGES.glob("*/src/**/*.py")) if "__pycache__" not in p.parts]
    assert paths, f"未扫到任何源码文件，扫描面已失效（目录改名？）：{_PACKAGES}"
    offenders: list[str] = []
    for path in paths:
        for lineno, expr in _identity_comparisons(path):
            offenders.append(f"{path.relative_to(_PACKAGES)}:{lineno}: is 比较 {expr}")
    assert not offenders, "API 侧与 ORM 侧的枚举是不同类，`is` 比较跨类恒为 False（`==` / `in` 才按值成立）：\n" + "\n".join(offenders)


def _module_and_package(path: Path) -> tuple[str, str]:
    """由 ``<pkg>/src/a/b.py`` 推出 (模块全名 ``a.b``, 所在包名 ``a``)，用于解析相对 import。

    只取相对 ``_PACKAGES`` 的路径段：绝对路径若恰好含外层 ``src``（如检出在 ``~/src/...``），
    ``parts.index("src")`` 会命中外层那个，相对 import 被解析成垃圾模块名而假失败。
    ``__init__.py`` 的 ``__package__`` 是去掉 ``.__init__`` 后的模块全名**本身**（``a.b``），
    再剥一层会得到 ``a``，使 ``from .x import y`` 解析成不存在的 ``a.x`` 而假失败。
    """
    parts = path.relative_to(_PACKAGES).parts
    dotted = ".".join(parts[parts.index("src") + 1 :])[: -len(".py")]
    is_init = path.name == "__init__.py"
    if is_init:
        dotted = dotted[: -len(".__init__")]
    return dotted, (dotted if is_init else dotted.rsplit(".", 1)[0])


def _resolve_import_from(path: Path, node: ast.ImportFrom) -> str:
    """把 ``from ...x import y`` 的 ``.`` 前缀解析成绝对模块名，避免相对写法绕过白名单判定。"""
    if node.level == 0:
        return node.module or ""
    package_parts = _module_and_package(path)[1].split(".")
    up = node.level - 1
    base = package_parts[: len(package_parts) - up] if up < len(package_parts) else []
    return ".".join([*base, *([node.module] if node.module else [])])


def _enum_name_imports(path: Path) -> list[tuple[int, str, str]]:
    """返回该文件引入 21 个枚举名的 (行号, 来源模块, 名字)；来源模块为解析后的绝对名。"""
    found: list[tuple[int, str, str]] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom):
            module = _resolve_import_from(path, node)
            found.extend((node.lineno, module, alias.name) for alias in node.names if alias.name in _ENUM_NAMES)
        elif isinstance(node, ast.Import):
            # 兜底 ``import X as AgentStatus`` 这类把枚举名当绑定名的写法（实测 169 个文件零命中）：
            # 删掉会让名称级判据在类型上不完整，故保留。
            for alias in node.names:
                bound = alias.asname or alias.name.split(".")[0]
                if bound in _ENUM_NAMES:
                    found.append((node.lineno, alias.name, bound))
    return found


def test_enum_names_imported_only_from_allowlisted_modules():
    """``views`` / ``schemas`` 只能从白名单声明模块引入这 21 个枚举名 —— 拦住经中间模块的一跳借用。

    ``api-layer-no-orm`` 契约必须设 ``allow_indirect_imports = True``，只能判直接依赖：把
    ``from ...agents.schemas.enums import AgentStatus`` 改成 ``from ...agents.meta import AgentStatus``
    （``meta`` 自身 import 了该 ORM 枚举）时契约仍报 ``7 kept``、模块路径探测器仍报 0 —— 全绿而
    ORM 耦合已回流。本守卫按导入名判定、不依赖图边，覆盖其中
    ``from <非白名单模块> import <枚举名>`` 形态（详见模块 docstring）。

    已知边界（名称级判据挡不住的形态，均需模块属性流/图分析，有意不堵）：
    - ``from ...agents.meta import meta`` 再 ``meta.AgentStatus``：导入的是模块名而非枚举名，判据不命中；
    - ``import ...agents.meta as m`` 再 ``m.AgentStatus``：裸 import 的绑定名不是枚举名；
    - ``from ...agents.schemas import enums`` 再 ``enums.AgentStatus`` 语义上就是引白名单模块本身，不算漏洞。
    """
    paths = []
    for candidate in sorted(_PACKAGES.glob("*/src/**/*.py")):
        if "__pycache__" in candidate.parts:
            continue
        rel_parts = candidate.relative_to(_PACKAGES).parts
        if rel_parts[0] in _API_PACKAGES and _API_DECL_DIRS & set(rel_parts):
            paths.append(candidate)
    assert paths, f"未扫到任何 views/schemas 文件，扫描面已失效（目录改名？）：{_PACKAGES}"
    offenders: list[str] = []
    for path in paths:
        for lineno, module, name in _enum_name_imports(path):
            if module not in _ENUM_IMPORT_ALLOWLIST:
                offenders.append(f"{path.relative_to(_PACKAGES)}:{lineno}: 从 {module} 引入枚举 {name}")
    assert not offenders, (
        "views/schemas 只能从各域 *.schemas.enums 白名单声明引入这 21 个持久化枚举；"
        "从其它模块引入等于借道中转重新耦合 ORM —— 契约因 allow_indirect_imports 只拦直接依赖，"
        "这一段由本守卫拦住：\n" + "\n".join(offenders)
    )


def test_parity_table_covers_exactly_21_enums():
    """平价表的名字集合必须逐字等于「声明模块里实际声明的枚举」——防改坏名字「修好」测试。

    只查「项数 == 21 且无重名」挡不住把某项的**名字字符串**改错：实测把 ``ModelVendor`` /
    ``ModelCapabilityType`` 改名后本文件仍 46 passed —— ``_ENUM_NAMES`` 随之少一个名字，名称级守卫
    对该名失效，而 ``test_parity_table_covers_every_enum_in_openapi_snapshot`` 看不见未暴露于快照的
    枚举（这两个恰好都不在快照内），三道护栏同时静默放行。故期望集合按目录约定推导而非硬编码：
    声明了新枚举却没登记，这里同样会失败。
    """
    declared = _declared_api_enums()
    names = [name for name, _, _ in CASES]
    assert len(CASES) == 21, f"平价表应恰有 21 项，实际 {len(CASES)}"
    assert len(set(names)) == len(names), f"平价表有重名：{sorted({n for n in names if names.count(n) > 1})}"
    missing = sorted(set(declared) - set(names))
    extra = sorted(set(names) - set(declared))
    assert not missing and not extra, (
        f"平价表与 API 侧声明不一致：仅声明未登记 {missing}"
        f"（声明于 {sorted(str(declared[n].relative_to(_PACKAGES)) for n in missing)}）；"
        f"仅在表内 {extra}。新增 API 侧枚举需同步 CASES 与 _ENUM_IMPORT_ALLOWLIST，"
        "否则名称级守卫认不得新名字"
    )


def test_enum_import_allowlist_matches_declaration_modules():
    """``_ENUM_IMPORT_ALLOWLIST`` 必须逐字等于约定扫描到的声明模块 —— 两者描述同一批「合法声明地」。

    多一项：名称级守卫放行了非声明模块（缺口）；少一项：真实声明模块被判定违规（误报）。两个方向
    都要有人看一眼，故钉住相等而非包含。
    """
    declared_modules = {_module_and_package(path)[0] for path in _declared_api_enums().values()}
    assert declared_modules == _ENUM_IMPORT_ALLOWLIST, (
        f"白名单与声明模块不一致：仅白名单 {sorted(_ENUM_IMPORT_ALLOWLIST - declared_modules)}；仅声明模块 {sorted(declared_modules - _ENUM_IMPORT_ALLOWLIST)}"
    )


def test_parity_table_covers_every_enum_in_openapi_snapshot():
    """公开契约实际暴露的枚举必须都在平价表内 —— 堵住「新增枚举未登记」的静默放行。

    本测试与 ``test_parity_table_covers_exactly_21_enums`` 的分工：后者以「API 侧实际声明」为锚，
    覆盖全部 21 个（含未暴露于快照的 ``ModelVendor`` / ``ModelCapabilityType``），但看不见
    「声明在扫描面之外的新模块」；本测试以快照（对外契约的实际产物）为锚，能抓到这类新增，
    却看不见未暴露的枚举。两者互补，缺一即留静默放行段。

    ``CASES`` 是人工清单：新增一个对外持久化枚举时，契约（一跳借用形态）拦不住、名称级守卫
    认不得新名字，此时靠上述两道锚定断言失败。Pydantic 把 ``StrEnum`` 渲染成带 ``enum`` 键的
    组件，故凡带 ``enum`` 键的组件名都必须在 ``CASES`` 中。
    """
    schemas = json.loads(_OPENAPI_SNAPSHOT.read_text(encoding="utf-8"))["components"]["schemas"]
    exposed = {name for name, schema in schemas.items() if isinstance(schema, dict) and "enum" in schema}
    missing = sorted(exposed - _ENUM_NAMES)
    assert not missing, (
        f"OpenAPI 快照暴露了平价表未登记的枚举：{missing}。"
        "新增对外（持久化）枚举时需同步 CASES 与 _ENUM_IMPORT_ALLOWLIST，"
        "否则契约、名称级守卫与项数检查会同时静默放行"
        f"（快照：{_OPENAPI_SNAPSHOT}）。"
    )
