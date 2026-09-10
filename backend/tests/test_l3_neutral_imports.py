"""L3 反依赖守卫：已收敛模块源码中不得出现 ``app.tenant``。

对应 [layering.md](../../docs/architecture/layering.md) 的 engine DI 收敛记录：
``integrations/deepagents``、``flow_runtime/subflow``、``flow_runtime/nodes/compliance_nodes.py``、
``models/compliance`` 均已对 tenant 域清零，这里以源码扫描防止回归。
"""

from __future__ import annotations

from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1]
_APP_DIR = _BACKEND_DIR / "app"

# (显示名, 相对 app/ 的路径)
_CONVERGED: list[tuple[str, str]] = [
    ("integrations/deepagents", "integrations/deepagents"),
    ("flow_runtime/subflow", "flow_runtime/subflow"),
    ("flow_runtime/nodes/compliance_nodes.py", "flow_runtime/nodes/compliance_nodes.py"),
    ("models/compliance", "models/compliance"),
    ("models/media", "models/media"),
    ("integrations/generative", "integrations/generative"),
]


def _iter_py_files(target: Path) -> list[Path]:
    if target.is_file():
        return [target]
    return sorted(p for p in target.rglob("*.py") if "__pycache__" not in p.parts)


def test_converged_l3_modules_have_no_tenant_imports():
    """已收敛区不得再 import app.tenant（含惰性/TYPE_CHECKING 引用）。"""
    offenders: list[str] = []
    for label, rel in _CONVERGED:
        for path in _iter_py_files(_APP_DIR / rel):
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if "app.tenant" in line:
                    offenders.append(f"{label}: {path.relative_to(_BACKEND_DIR)}:{lineno}: {line.strip()}")
    assert not offenders, "已收敛 L3 模块出现 app.tenant 引用：\n" + "\n".join(offenders)
