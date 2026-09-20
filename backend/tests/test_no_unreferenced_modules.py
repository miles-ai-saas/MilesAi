"""守卫：包内不得出现「零引用模块」（入口点与有意未接线者除外）。

背景：`compliance/desensitize.py`、`services/compliance/media_audit.py` 自引入起从未被
任何模块 import，文档却按「已交付」记录（见 `docs/features/compliance.md` §1.2）；两个
`generative/jobs/*_params.py` 更是与生产侧内联构造逐字段重复、只被自己的测试引用。
这类模块不会让任何测试变红，只会静默腐化并误导文档，故设此守卫把「有没有人用」
从「靠偶尔想不起来去查」变为「可执行」。

判据说明（两个来源缺一不可）：

1. **AST import** —— 按包结构解析相对导入；``from a.b import c`` 既算引用 ``a.b``，
   也算引用子模块 ``a.b.c``（若存在）。
2. **非 docstring 的字符串字面量** —— 覆盖 ``importlib.import_module`` 与登记清单
   （如 ``miles_server/registry.py`` 的 ``_ORM_MODULES`` 是按字符串加载的，只认 import
   会把 21 个 ORM 模块全部误报）。**docstring 里提到模块名不算引用** —— 否则一句注释
   就能把死代码洗白。

已知覆盖边界：入口点由 ``Dockerfile`` 的 ``CMD`` / ``[project.scripts]`` / Makefile 的
``python -m`` 拉起，都不在 Python 的 import 图里，故一律进 ``_ALLOWED_UNREFERENCED``
白名单并写明理由；同样，按名加载的插件（钩子）也在白名单内。
"""

from __future__ import annotations

import ast
from pathlib import Path

from tests.paths import BACKEND_ROOT, PACKAGES

#: 包根名（用于识别「像模块路径的字符串字面量」）。
_ROOTS: tuple[str, ...] = (
    "miles_core",
    "miles_common",
    "miles_ai",
    "miles_portal",
    "miles_admin",
    "miles_exec",
    "miles_server",
    "miles_worker",
)

#: 允许「零静态引用」的模块名 → 理由。
#: 新增一条等于书面承认「这个模块现在没有调用方」，请同时确认是入口点还是有意保留。
_ALLOWED_UNREFERENCED: dict[str, str] = {
    "miles_runner.main": "Dockerfile.mcp-runner 的 CMD 以 ``uvicorn miles_runner.main:app`` 拉起",
    "miles_server.cli": "console script（`[project.scripts]`）与 Makefile 的 ``python -m miles_server.cli``",
    "miles_server.scripts.export_openapi": "Makefile 的 ``python -m miles_server.scripts.export_openapi``",
    "miles_portal.tenant.hooks.plugins.echo": "Python 钩子插件，模块名存租户配置后按名加载",
    "miles_portal.tenant.compliance.services.compliance.media_audit": ("有意保留未接线（接入属按需立项），见 docs/features/compliance.md §1.2"),
}

_SEP = "/"


def _iter_backend_files() -> list[Path]:
    out: list[Path] = []
    for path in BACKEND_ROOT.rglob("*.py"):
        parts = path.parts
        if any(p in parts for p in (".venv", "node_modules", "__pycache__", ".git")):
            continue
        out.append(path)
    return sorted(out)


def _module_name(path: Path) -> str | None:
    """``packages/<dist>/src/<mod>.py`` → ``<mod>``；非包内文件返回 None。"""
    if not path.is_relative_to(PACKAGES):
        return None
    parts = list(path.parts)
    if "src" not in parts:
        return None
    tail = parts[parts.index("src") + 1 :]
    if path.name == "__init__.py":
        tail = tail[:-1]
    elif tail:
        tail[-1] = path.stem
    return ".".join(tail) or None


def _package_of(path: Path, module: str) -> str:
    """模块所属包（``__init__`` 的包即自身），用于解析相对导入。"""
    if path.name == "__init__.py":
        return module
    return module.rpartition(".")[0]


def _resolve_relative(base_pkg: str, level: int, tail: str | None) -> str | None:
    if level == 0:
        return tail
    parts = base_pkg.split(".") if base_pkg else []
    up = level - 1
    if up > len(parts):
        return None
    parts = parts[: len(parts) - up] if up else parts
    if tail:
        parts = parts + tail.split(".")
    return ".".join(parts) or None


def _docstrings(tree: ast.AST) -> set[int]:
    """模块/类/函数体的首个字符串表达式 —— 这些提到模块名不算引用。"""
    found: set[int] = set()
    scopes = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    for node in ast.walk(tree):
        if not isinstance(node, scopes) or not node.body:
            continue
        first = node.body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
            found.add(id(first.value))
    return found


def _note(refs: dict[str, set[Path]], target: str, path: Path) -> None:
    """记录一处引用。

    ``path`` 显式传入而非由闭包捕获循环变量 —— 闭包捕获循环变量（ruff B023）在
    「循环内定义、循环外调用」时会取到最后一轮的值，是典型静默错源。
    """
    refs.setdefault(target, set()).add(path)


def _is_test_file(path: Path) -> bool:
    """测试文件不算「有人在用」——「仅测试引用」正是本守卫要拦的死代码形态。"""
    return path.is_relative_to(BACKEND_ROOT / "tests")


def _scan() -> tuple[set[str], set[str], int, int]:
    """返回 ``(零引用模块, 全部模块, 扫描文件数, 引用键数)``。

    判定口径两点：

    - 只看**生产侧**引用（``backend/tests/`` 的引用不计）；
    - 包（``__init__.py`` → 如 ``miles_core.models``）不参与判定：大家直接 import 叶子
      模块，包自身从未被引用属常态；包若整体废弃，其叶子模块会各自被报出来。
    """
    files = _iter_backend_files()
    modules: set[str] = set()
    packages: set[str] = set()
    parsed: list[tuple[Path, ast.Module]] = []
    for path in files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        parsed.append((path, tree))
        name = _module_name(path)
        if name:
            modules.add(name)
            if path.name == "__init__.py":
                packages.add(name)

    refs: dict[str, set[Path]] = {}
    for path, tree in parsed:
        name = _module_name(path)
        base = _package_of(path, name) if name else ""
        skip = _docstrings(tree)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    _note(refs, alias.name, path)
            elif isinstance(node, ast.ImportFrom):
                target = _resolve_relative(base, node.level, node.module)
                if not target:
                    continue
                _note(refs, target, path)
                for alias in node.names:
                    # ``from a.b import c`` 里的 c 可能是子模块。
                    _note(refs, f"{target}.{alias.name}", path)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip:
                value = node.value.strip()
                if value.startswith(_ROOTS) and " " not in value and _SEP not in value:
                    _note(refs, value, path)

    def alive(module: str) -> bool:
        for path in refs.get(module, ()):
            if _is_test_file(path) or _module_name(path) == module:
                continue
            return True
        return False

    unreferenced = {m for m in modules if m not in packages and not alive(m)}
    return unreferenced, modules, len(files), len(refs)


def test_guard_surface_is_not_silently_empty():
    """守卫自身防呆：扫描面、模块面、引用面都不得为空，否则规则在静默失效。"""
    unreferenced, modules, n_files, n_refs = _scan()

    assert n_files > 100, f"只扫到 {n_files} 个 .py，扫描面疑似失效"
    assert len(modules) > 100, f"只解析出 {len(modules)} 个模块，模块名推导疑似失效"
    assert n_refs > 100, f"只收集到 {n_refs} 个引用键，引用解析疑似失效"
    assert unreferenced <= modules


def test_reference_detector_counts_imports_and_strings_but_not_docstrings():
    """检测器自检：import 与数据字符串算引用，docstring 里提到模块名不算。"""
    tree = ast.parse(
        '''
"""模块 docstring 提到 miles_core.ghost 不算引用。"""
import miles_core.alpha
from miles_core import beta

REGISTRY = ["miles_core.gamma"]


def f():
    """函数 docstring 提到 miles_core.delta 不算引用。"""
    return None
'''
    )
    skip = _docstrings(tree)
    seen: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            seen.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            seen.add(node.module or "")
            seen.update(f"{node.module}.{a.name}" for a in node.names)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip:
            seen.add(node.value.strip())

    assert "miles_core.alpha" in seen
    assert "miles_core.beta" in seen
    assert "miles_core.gamma" in seen
    assert "miles_core.ghost" not in seen, "docstring 里的提及不得算引用"
    assert "miles_core.delta" not in seen, "函数 docstring 里的提及不得算引用"


def test_every_allowlist_entry_is_a_real_module():
    """白名单不得陈旧：条目必须是真实存在的模块。"""
    _, modules, _, _ = _scan()
    stale = sorted(set(_ALLOWED_UNREFERENCED) - modules)
    assert not stale, "白名单条目已不存在（请删除）：\n  " + "\n  ".join(stale)


def test_no_unreferenced_modules_outside_allowlist():
    """零引用集合必须与白名单**精确一致**（双向）：新增死模块会失败，白名单过期也会失败。"""
    unreferenced, _, _, _ = _scan()

    unexpected = sorted(unreferenced - set(_ALLOWED_UNREFERENCED))
    stale = sorted(set(_ALLOWED_UNREFERENCED) - unreferenced)

    messages = []
    if unexpected:
        messages.append(
            "以下模块零引用（无任何 import 或按名加载）：\n  "
            + "\n  ".join(f"{m}" for m in unexpected)
            + "\n请接线、删除，或加入 _ALLOWED_UNREFERENCED 并写明理由。"
        )
    if stale:
        messages.append("白名单里以下模块现已有人引用，应移出白名单：\n  " + "\n  ".join(stale))
    assert not messages, "\n\n".join(messages)
