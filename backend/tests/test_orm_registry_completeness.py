"""守 ``miles_server.registry`` 的 ORM 登记清单不静默过期。

失败模式：新增 ORM 模块却漏加进 ``_ORM_MODULES`` → ``Base.metadata`` 缺表 →
Alembic autogenerate 把线上已有表判成待 DROP 的差异。这个失败**静默**：导入照常成功，
只有迁移那一刻才显形，故必须由测试堵住。

期望值取「源码扫出的表名」而非「metadata 里的表名」：若拿 metadata 当期望值，
同会话里 ``conftest`` 或别的测试先 import 过模型，漏登记就会被掩盖成假通过。
因此真实值一律在**子进程**里取，与本次会话的 import 历史无关。
"""

from __future__ import annotations

import ast
import importlib
import subprocess
import sys
from pathlib import Path

from miles_server.registry import _ORM_MODULES
from tests.paths import BACKEND_ROOT, PACKAGES

# 在干净解释器里导入全部 ORM 模块，打印排序后的表名（表名不含空格，直接按空白切分）。
_PROBE = """
from miles_core.infra.db import Base
from miles_server.registry import load_all_models

load_all_models()
print(*sorted(Base.metadata.tables))
"""

# 实测全仓声明 65 张表；留出余量，明显偏低即说明扫描面失效而非真的删了表。
_MIN_EXPECTED_TABLES = 60


def _is_table_call(node: ast.Call) -> bool:
    """是否为 ``Table("<字面量>", ...)`` 形式（``sqlalchemy.Table`` / ``sa.Table``）。"""
    func = node.func
    name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
    if name != "Table" or not node.args:
        return False
    first = node.args[0]
    return isinstance(first, ast.Constant) and isinstance(first.value, str)


def _declared_tables(path: Path) -> list[str]:
    """扫出该文件声明的表名，覆盖两种声明形式。

    - ``__tablename__ = "<字面量>"``：常规 ORM 类
    - ``Table("<字面量>", Base.metadata, ...)``：没有 ``__tablename__`` 的关联表
      （``agt_kb_bindings`` / ``sys_user_roles`` / ``sys_role_permissions``）

    只认字面量：全仓无 f-string / 拼接写法，一旦出现本测试的 ``==`` 会失败而非漏判。
    """
    found: list[str] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__tablename__" for t in node.targets):
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                found.append(node.value.value)
        elif isinstance(node, ast.Call) and _is_table_call(node):
            first = node.args[0]
            assert isinstance(first, ast.Constant) and isinstance(first.value, str)  # _is_table_call 已保证
            found.append(first.value)
    return found


def _scan_declared_tables() -> dict[str, Path]:
    """全仓扫表名 -> 声明它的文件，用于失败信息里直接指路。"""
    paths = [p for p in sorted(PACKAGES.glob("*/src/**/*.py")) if "__pycache__" not in p.parts]
    assert paths, f"未扫到任何源码文件，扫描面已失效（目录改名？）：{PACKAGES}"
    tables: dict[str, Path] = {}
    for path in paths:
        for table in _declared_tables(path):
            tables.setdefault(table, path)
    assert len(tables) >= _MIN_EXPECTED_TABLES, f"只扫到 {len(tables)} 张表（预期 >= {_MIN_EXPECTED_TABLES}），扫描面已失效：{PACKAGES}"
    return tables


def _registered_tables() -> set[str]:
    """在子进程里跑 ``load_all_models()`` 后取 metadata 表名。"""
    result = subprocess.run([sys.executable, "-c", _PROBE], capture_output=True, text=True, timeout=180, cwd=BACKEND_ROOT)
    assert result.returncode == 0, f"子进程导入 ORM 模块失败（rc={result.returncode}）：\n{result.stderr}"
    return set(result.stdout.split())


def test_declared_tables_are_all_registered():
    """源码声明的表与 ``load_all_models()`` 注册出的表必须精确一致。

    双向断言：漏登记会丢表（迁移生成 DROP），多出来的表则说明扫描面漏了某种声明写法
    （或有人在源码外动态建表），两种情况都要有人看一眼。
    """
    declared = _scan_declared_tables()
    registered = _registered_tables()

    lines: list[str] = []
    missing = sorted(set(declared) - registered)
    if missing:
        lines.append("漏登记（源码有、metadata 无）——把下面文件所在模块加进 miles_server.registry._ORM_MODULES：")
        lines.extend(f"  {table}  <- {declared[table].relative_to(BACKEND_ROOT)}" for table in missing)
    extra = sorted(registered - set(declared))
    if extra:
        lines.append("多出（metadata 有、源码未声明）——动态建表，或 _declared_tables 漏了这种写法：")
        lines.extend(f"  {table}" for table in extra)

    assert not lines, f"源码声明 {len(declared)} 张表，注册后 metadata 有 {len(registered)} 张：\n" + "\n".join(lines)


def test_registry_entries_are_importable():
    """清单里不得残留改名/删除后的陈旧项（陈旧项不影响正确性，但会让清单失去可审计性）。"""
    broken: list[str] = []
    for module in _ORM_MODULES:
        try:
            importlib.import_module(module)
        except ImportError as exc:
            broken.append(f"  {module}: {exc}")
    assert not broken, "``_ORM_MODULES`` 里的模块无法导入：\n" + "\n".join(broken)
