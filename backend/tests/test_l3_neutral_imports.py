"""L3 反依赖守卫：已收敛模块源码中不得出现 ``app.tenant``。

对应 [layering.md](../../docs/architecture/layering.md) 的 engine DI 收敛记录：
``integrations`` 与 ``flow_runtime`` 两整棵子树（含 ``integrations/deepagents``、
``flow_runtime/subflow``、``flow_runtime/nodes/compliance_nodes.py`` 等具体模块）
以及 ``models/compliance``、``models/media`` 均已对 tenant 域清零；
这里以源码扫描（覆盖全部 ``integrations/**`` 与 ``flow_runtime/**``）防止回归。
已接入 CI 门禁（``.github/workflows/lint.yml`` 的 ``L3 reverse-dependency guard`` 步骤）。
"""

from __future__ import annotations

from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1]
_APP_DIR = _BACKEND_DIR / "app"

# (显示名, 相对 app/ 的路径)
_CONVERGED: list[tuple[str, str]] = [
    ("integrations", "integrations"),
    ("flow_runtime", "flow_runtime"),
    ("integrations/deepagents", "integrations/deepagents"),
    ("flow_runtime/subflow", "flow_runtime/subflow"),
    ("flow_runtime/nodes/compliance_nodes.py", "flow_runtime/nodes/compliance_nodes.py"),
    ("models/compliance", "models/compliance"),
    ("models/media", "models/media"),
    ("integrations/generative", "integrations/generative"),
    ("integrations/chat", "integrations/chat"),
]

# 出现任一子串即判定为 tenant 依赖（含 ``from app import tenant`` / ``import app.tenant`` 别名写法）。
_FORBIDDEN_SUBSTRINGS: tuple[str, ...] = (
    "app.tenant",
    "from app import tenant",
    "import app.tenant",
)


def _iter_py_files(target: Path) -> list[Path]:
    if target.is_file():
        return [target]
    return sorted(p for p in target.rglob("*.py") if "__pycache__" not in p.parts)


def test_converged_l3_modules_have_no_tenant_imports():
    """已收敛区不得再 import app.tenant（含惰性/TYPE_CHECKING 引用）。

    扫描范围覆盖全部 ``integrations/**`` 与 ``flow_runtime/**``。
    """
    offenders: list[str] = []
    for label, rel in _CONVERGED:
        for path in _iter_py_files(_APP_DIR / rel):
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if any(fragment in line for fragment in _FORBIDDEN_SUBSTRINGS):
                    offenders.append(f"{label}: {path.relative_to(_BACKEND_DIR)}:{lineno}: {line.strip()}")
    assert not offenders, "已收敛 L3 模块出现 app.tenant 引用：\n" + "\n".join(offenders)
