"""tests 目录结构守卫：一级目录 = 被测包；深层 = 包内模块；用例归属包前缀自洽；文件基名唯一。

背景：2026-09-21 把 ``tests/`` 由「单包时代的域目录」重构为按 ``packages/`` 镜像
（一级目录 = 被测包，深层 = 包内模块层）。四条判据把该结构固化成契约：

1. ``tests/`` 一级只能是被测包目录、``integration/`` 与根级守卫/基础设施文件；
2. ``tests/miles_<pkg>/**`` 下的用例至少 import 一次该包（宽松口径：只判包前缀，
   不判到具体目录，跨域用例仍可存在）；
3. ``tests/miles_<pkg>/<a>/…/<z>/`` 对应真实的 ``miles_<pkg>.<a>.….<z>`` 源码目录
   （判据 2 只管到一级，深层漂移靠这条兜住）；
4. 全仓 ``test_*.py`` 基名唯一——``tests/`` 无 ``__init__.py``，pytest 的 ``prepend``
   导入模式要求基名唯一，否则报 import file mismatch。

约定（判据 1 无法机器判定的部分）：根级 ``test_*.py`` 仅限**跨包**守卫/契约
（R3，如 AST 守卫、枚举契约、ORM 登记），单个包的用例一律落到 ``miles_<pkg>/`` 下
——把单域用例放到根级会绕过判据 2/3，别这么做。
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.paths import PACKAGES, TESTS_ROOT

# 允许的一级目录：被测包 + 跨包集成
_ALLOWED_TOP_LEVEL = frozenset(
    {
        "integration",
        "miles_common",
        "miles_exec",
        "miles_core",
        "miles_ai",
        "miles_portal",
        "miles_admin",
        "miles_openapi",
        "miles_server",
        "miles_worker",
        "miles_runner",  # 当前无直接用例（能力经 miles_exec 覆盖），保留以便新增用例时无需改守卫
    }
)

# 根级允许的非测试文件（README.md 是目录说明，随守卫一起保留）
_ALLOWED_ROOT_FILES = frozenset({"conftest.py", "paths.py", "README.md"})

# 例外登记：以路径读取被测源码做文本断言，无 import。新增例外须写明理由。
_PATH_ONLY_EXEMPTIONS = frozenset({"miles_server/scripts/seed/test_model_catalog_seed.py"})


def _iter_tests() -> list[Path]:
    """全仓测试文件（排序后返回，排除 __pycache__）。"""
    return sorted(p for p in TESTS_ROOT.rglob("test_*.py") if "__pycache__" not in p.parts)


def _assert_scan_surface(files: list[Path]) -> None:
    """守卫自身防呆：扫描面收敛到 0 或异常偏小时，下面几条判据会**静默通过**。

    与 ``test_no_unreferenced_modules.py`` 的 ``n_files > 100`` 同口径——把
    ``TESTS_ROOT`` 写错、glob 写漏、测试文件改名成 ``*_test.py`` 都会先在这里报出来。
    """
    assert len(files) >= 200, f"只扫到 {len(files)} 个 test_*.py，扫描面疑似失效：{TESTS_ROOT}"


def test_top_level_dirs_are_package_or_integration():
    """``tests/`` 一级只允许被测包目录与 ``integration/``，根级只允许守卫与基础设施文件。"""
    offenders: list[str] = []
    for path in sorted(TESTS_ROOT.iterdir()):
        if path.name == "__pycache__":
            continue
        if path.is_file():
            if path.name in _ALLOWED_ROOT_FILES or path.name.startswith("test_"):
                continue
            offenders.append(path.name)
            continue
        if path.name not in _ALLOWED_TOP_LEVEL:
            offenders.append(f"{path.name}/")
    assert not offenders, "tests/ 一级出现未登记的目录/文件：\n" + "\n".join(offenders)


def test_package_prefixed_tests_import_their_package():
    """``tests/miles_<pkg>/**`` 下的用例至少要 import 一次该包（拦住包归属漂移）。"""
    files = _iter_tests()
    _assert_scan_surface(files)
    offenders: list[str] = []
    for path in files:
        rel = path.relative_to(TESTS_ROOT)
        pkg = rel.parts[0]
        if not pkg.startswith("miles_") or len(rel.parts) < 2:
            continue
        if rel.as_posix() in _PATH_ONLY_EXEMPTIONS:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if re.search(rf"^\s*(?:from|import)\s+{pkg}\b", text, re.MULTILINE) is None:
            offenders.append(rel.as_posix())
    assert not offenders, "以下用例未 import 其目录对应的包（放错包目录）：\n" + "\n".join(offenders)


def test_package_subdirs_mirror_source_modules():
    """``tests/miles_<pkg>/<a>/…/<z>/`` 必须对应 ``packages/miles-<pkg>/src/miles_<pkg>/<a>/…/<z>/``。

    上层判据只看到一级目录，深层漂移（把用例塞进一个并不存在的域目录）测不出来；
    「位置 ⇔ 模块」这条契约正是靠这一条兜住的。
    """
    offenders: list[str] = []
    for path in sorted(TESTS_ROOT.rglob("*")):
        if not path.is_dir() or "__pycache__" in path.parts:
            continue
        rel = path.relative_to(TESTS_ROOT)
        if len(rel.parts) < 2 or not rel.parts[0].startswith("miles_"):
            continue
        pkg_dir = "miles-" + rel.parts[0].removeprefix("miles_")
        src = PACKAGES / pkg_dir / "src" / Path(*rel.parts)
        if not src.is_dir():
            offenders.append(rel.as_posix())
    assert not offenders, "测试子目录不对应任何源码模块目录（位置与模块已脱钩）：\n" + "\n".join(offenders)


def test_test_file_basenames_are_unique():
    """全仓 ``test_*.py`` 基名唯一——无 ``__init__.py`` 时 pytest 的硬约束。"""
    files = _iter_tests()
    _assert_scan_surface(files)
    by_name: dict[str, list[str]] = {}
    for path in files:
        by_name.setdefault(path.name, []).append(path.relative_to(TESTS_ROOT).as_posix())
    dupes = {name: paths for name, paths in by_name.items() if len(paths) > 1}
    assert not dupes, "测试文件基名重复（pytest 会报 import file mismatch）：\n" + "\n".join(f"{name}: {paths}" for name, paths in sorted(dupes.items()))
