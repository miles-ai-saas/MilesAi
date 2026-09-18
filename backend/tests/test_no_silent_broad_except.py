"""守卫：宽泛 ``except`` 不得静默吞掉异常（须记日志、重抛或收窄类型）。

背景：``pytesseract`` pip 包与 ``tesseract`` **二进制**是两个独立依赖，slim 镜像常只
装前者。此时 ``image_to_string`` 抛 ``TesseractNotFoundError``（``OSError`` 子类），
曾被 ``except Exception`` 静默吞掉 —— 零日志，且占位文案还让人去「安装 pytesseract」，
把排查方向指反；占位文本又会被当作正文索引入库，检索质量静默下降。Whisper 模型下载
失败、ffmpeg 编解码器缺失同理。详见 ``tests/rag/test_parse_degradation_diagnosability.py``。

**判定「静默」**：handler 体仅由 ``pass`` / ``...`` / 字符串表达式（docstring）/
``return None`` 组成 —— 既无日志、无重抛，也无任何补救动作，故「吞掉」不留痕迹。
有日志（即使 ``debug``）、有 fd 兜底写入、有 return 非 None 值等，都**不算**静默。

**刻意只收宽泛类型**（bare / ``Exception`` / ``BaseException``）：窄类型的静默多为
有意的控制流（如以 ``except ValueError`` 判断「不是 UUID」、``except ImportError``
判定可选依赖），拦它收益低而误报高。

当前全仓宽泛静默基线为 **0**，故无需豁免清单；若确有正当情形，应补日志/重抛/收窄，
或把本规则扩展为带豁免表的形式。
"""

from __future__ import annotations

import ast
from pathlib import Path

from tests.paths import PACKAGES

#: 视为「宽泛」的异常类型点号名（含模块限定写法）。
_BROAD_EXCEPTIONS: frozenset[str] = frozenset({"Exception", "BaseException", "builtins.Exception", "builtins.BaseException"})


def _dotted(node: ast.expr) -> str | None:
    """把 ``a.b.c`` 形式的表达式还原为点号字符串；其余返回 None。"""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return None


def _iter_package_files() -> list[Path]:
    return sorted(p for p in PACKAGES.rglob("*.py") if "__pycache__" not in p.parts)


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8", errors="replace"))


def _is_broad(handler: ast.ExceptHandler) -> bool:
    """是否宽泛捕获：bare ``except`` 或匹配 ``Exception`` / ``BaseException``。"""
    if handler.type is None:
        return True
    exprs = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
    return bool({_dotted(e) for e in exprs} & _BROAD_EXCEPTIONS)


def _is_silent(body: list[ast.stmt]) -> bool:
    """handler 体是否「什么都没做」：无日志、无重抛、无补救动作。

    注意 ``raise`` **不属**静默 —— 重抛是把异常交出去，痕迹完整。判定采用
    「白名单式」穷举：只有全部语句都属于 ``pass`` / ``...`` / docstring /
    ``return None`` 才算静默，任何其他语句（含 ``raise``）一律不算。
    """
    for stmt in body:
        if isinstance(stmt, ast.Pass):
            continue
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
            continue  # docstring 或 ``...``
        if isinstance(stmt, ast.Return) and (stmt.value is None or (isinstance(stmt.value, ast.Constant) and stmt.value.value is None)):
            continue
        return False
    return True


def _collect_violations() -> tuple[list[str], int]:
    """返回 ``(违规位置列表, 扫到的宽泛 handler 总数)``。"""
    violations: list[str] = []
    total = 0
    for path in _iter_package_files():
        rel = path.relative_to(PACKAGES).as_posix()
        for node in ast.walk(_parse(path)):
            if not isinstance(node, ast.ExceptHandler) or not _is_broad(node):
                continue
            total += 1
            if _is_silent(node.body):
                violations.append(f"{rel}:{node.lineno}")
    return violations, total


def test_guard_surface_is_not_silently_empty():
    """守卫自身防呆：扫描面与宽泛 handler 面都不得为空，否则规则在静默失效。"""
    assert _iter_package_files(), "未扫到任何包内文件，守卫已失效"

    violations, total = _collect_violations()

    assert total > 0, "未扫到任何宽泛 except，AST 遍历疑似失效"
    assert len(violations) <= total


def test_detector_flags_silent_and_spares_logging_narrow_and_reraise():
    """检测器自检：静默要报；记日志 / 窄类型 / 重抛都不报。

    防两类退化：恒 False（守卫失效）与把 ``raise`` 误判为静默（会把全仓 8 处
    ``except Exception as exc: raise ... from exc`` 全部误报）。
    """
    tree = ast.parse(
        """
def silent():
    try:
        pass
    except Exception:
        pass

def logged():
    try:
        pass
    except Exception:
        logger.warning("x", exc_info=True)

def narrowed():
    try:
        pass
    except OSError:
        pass

def reraises():
    try:
        pass
    except Exception as exc:
        raise BadRequestError(str(exc)) from exc
"""
    )
    verdicts = [(_is_broad(n), _is_silent(n.body)) for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler)]

    assert verdicts == [
        (True, True),  # silent
        (True, False),  # logged
        (False, True),  # narrowed
        (True, False),  # reraises
    ]


def test_broad_except_never_swallows_silently():
    """宽泛 except 不得「什么都不做」；至少记日志（带 exc_info）、重抛或收窄类型。"""
    violations, _ = _collect_violations()

    assert not violations, (
        "宽泛 except 静默吞掉异常（无日志、无重抛、无补救动作）：\n  " + "\n  ".join(violations) + "\n请记日志（带 exc_info）、重抛，或收窄异常类型。"
    )
