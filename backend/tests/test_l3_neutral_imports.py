"""多包布局守卫：L3 叶子包不得反向依赖上层装配/门户包。

Phase 2 把 ``app/`` 拆成 10 个 uv workspace 包后，原有的单包源码扫描改为按包扫描：

- ``miles-ai``（L3 引擎层）不得 import ``miles_portal``；
- ``miles-server``（装配层）不得含 ``views/`` 目录，也不得直接构造 ``APIRouter(``
  （路由装配应下沉到各域视图包）。

风格与原守卫一致：直接扫描源码文本（import 检查只匹配 import 语句，避免误伤
docstring 中的说明性提及）。
"""

from __future__ import annotations

import re
from pathlib import Path

_PKG = Path(__file__).resolve().parents[1] / "packages"
_MILES_AI = _PKG / "miles-ai" / "src" / "miles_ai"
_MILES_SERVER = _PKG / "miles-server" / "src" / "miles_server"

# 仅匹配真正的 import 语句（含缩进的惰性/TYPE_CHECKING import），不匹配 docstring 提及。
_MILES_PORTAL_IMPORT_RE = re.compile(r"^\s*(?:from|import)\s+.*\bmiles_portal\b")


def _iter_py_files(target: Path) -> list[Path]:
    if target.is_file():
        return [target]
    return sorted(p for p in target.rglob("*.py") if "__pycache__" not in p.parts)


def test_multi_package_layout_guard():
    """miles-ai 不得依赖 miles_portal；miles-server 只装配、不自建 views/router。"""
    offenders: list[str] = []
    for path in _iter_py_files(_MILES_AI):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if _MILES_PORTAL_IMPORT_RE.match(line):
                offenders.append(f"miles-ai→portal {path.relative_to(_PKG)}:{lineno}: {line.strip()}")
    assert not offenders, "miles-ai 出现 miles_portal import：\n" + "\n".join(offenders)

    views_dirs = sorted(str(p.relative_to(_PKG)) for p in _MILES_SERVER.rglob("views") if p.is_dir())
    assert not views_dirs, "miles-server 下不应有 views/ 目录：\n" + "\n".join(views_dirs)

    offenders = []
    for path in _iter_py_files(_MILES_SERVER):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if "APIRouter(" in line:
                offenders.append(f"{path.relative_to(_PKG)}:{lineno}: {line.strip()}")
    assert not offenders, "miles-server 不应直接构造 APIRouter：\n" + "\n".join(offenders)
