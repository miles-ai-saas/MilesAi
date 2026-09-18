"""守卫：宽泛 ``except`` 不得静默吞掉异常（须记日志、重抛或收窄类型）。

背景：``pytesseract`` pip 包与 ``tesseract`` **二进制**是两个独立依赖，slim 镜像常只
装前者。此时 ``image_to_string`` 抛 ``TesseractNotFoundError``（``OSError`` 子类），
曾被 ``except Exception`` 静默吞掉 —— 零日志，且占位文案还让人去「安装 pytesseract」，
把排查方向指反；占位文本又会被当作正文索引入库，检索质量静默下降。Whisper 模型下载
失败、ffmpeg 编解码器缺失同理。详见 ``tests/rag/test_parse_degradation_diagnosability.py``。

**判定「静默」**：handler 体仅由 ``pass`` / ``...`` / 字符串表达式（docstring）/
``return None`` 组成 —— 既无日志、无重抛，也无任何补救动作，故「吞掉」不留痕迹。
有日志（即使 ``debug``）、有 fd 兜底写入、有 return 非 None 值等，都**不算**静默。

**分两档**：

1. 宽泛类型（bare / ``Exception`` / ``BaseException``）**一律不得**静默：handler 体
   必须有日志、重抛或补救动作。全仓基线为 **0**，故无需豁免清单。
2. 窄类型（``except ValueError`` 判「不是 UUID」、``except ImportError`` 判可选依赖等）
   允许静默 —— 那是有意的控制流，拦它收益低而误报高 —— 但**必须在 handler 体内注明
   ``# 静默可接受：<理由>``**。理由缺失即违规：否则读者无法区分「刻意设计」与「漏写
   处理」，注释也会随重构逐条流失。

两档都只认「有没有写理由」，不评价理由质量（长度、关键词等）—— 那是 code review 的事，
机器只保证「此处静默是被人想过的」。
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

from tests.paths import PACKAGES

#: 视为「宽泛」的异常类型点号名（含模块限定写法）。
_BROAD_EXCEPTIONS: frozenset[str] = frozenset({"Exception", "BaseException", "builtins.Exception", "builtins.BaseException"})

#: 窄类型静默 handler 必须携带的理由注释前缀。
_SILENT_MARKER = "静默可接受"


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


def _indent(line: str) -> int:
    """行首空格数。"""
    return len(line) - len(line.lstrip())


def _has_silent_marker(lines: list[str], handler: ast.ExceptHandler) -> bool:
    """handler 体内是否写有 ``# 静默可接受：<理由>``。

    只沿 handler 体首条语句往上读**连续的注释行**，且要求这些行缩进比 ``except`` 行更深
    （即确实落在 handler 体内）。否则 ``try`` 块末尾的注释、或 ``except X: pass`` 单行写法
    上方碰巧存在的注释，都会被误认成理由。
    """
    first = handler.body[0]
    if first.lineno <= handler.lineno:  # ``except X: pass`` 单行写法，体内写不下注释
        return False

    base_indent = _indent(lines[handler.lineno - 1])
    idx = first.lineno - 2
    while idx >= 0:
        stripped = lines[idx].strip()
        if not stripped.startswith("#") or _indent(lines[idx]) <= base_indent:
            return False
        if stripped.lstrip("#").strip().startswith(_SILENT_MARKER):
            return True
        idx -= 1
    return False


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


@dataclass
class _Scan:
    """一次全仓扫描的结果。"""

    broad_handlers: int = 0
    """宽泛 handler 总数（含已记日志/重抛的），用于守卫自检扫描面非空。"""

    broad_silent: list[str] = field(default_factory=list)
    """宽泛且静默 —— 违规。"""

    narrow_silent: int = 0
    """窄类型且静默的 handler 总数（含已注明理由的），用于守卫自检扫描面非空。"""

    narrow_unmarked: list[str] = field(default_factory=list)
    """窄类型、静默、且未注明理由 —— 违规。"""


def _scan() -> _Scan:
    """扫描全部包内文件，按两档规则收集违规位置。"""
    result = _Scan()
    for path in _iter_package_files():
        rel = path.relative_to(PACKAGES).as_posix()
        source = path.read_text(encoding="utf-8", errors="replace")
        lines = source.splitlines()
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.ExceptHandler):
                continue
            silent = _is_silent(node.body)
            if _is_broad(node):
                result.broad_handlers += 1
                if silent:
                    result.broad_silent.append(f"{rel}:{node.lineno}")
            elif silent:
                result.narrow_silent += 1
                if not _has_silent_marker(lines, node):
                    result.narrow_unmarked.append(f"{rel}:{node.lineno}")
    return result


def test_guard_surface_is_not_silently_empty():
    """守卫自身防呆：扫描面、宽泛 handler 面、窄类型静默面都不得为空，否则规则在静默失效。"""
    assert _iter_package_files(), "未扫到任何包内文件，守卫已失效"

    result = _scan()

    assert result.broad_handlers > 0, "未扫到任何宽泛 except，AST 遍历疑似失效"
    assert result.narrow_silent > 0, "未扫到任何窄类型静默 except，AST 遍历疑似失效"
    assert len(result.broad_silent) <= result.broad_handlers
    assert len(result.narrow_unmarked) <= result.narrow_silent


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


def test_marker_detector_requires_marker_inside_handler_body():
    """理由标注检测器自检：只有「handler 体内的理由注释」才算。

    覆盖三类误认风险：无标注、注释在 handler 之外（``try`` 块末尾）、``except X: pass``
    单行写法（体内根本写不下注释）。
    """
    source = """
def marked():
    try:
        pass
    except ValueError:
        # 静默可接受：不是 UUID 即「未设置」
        pass

def unmarked():
    try:
        pass
    except ValueError:
        pass

def comment_outside_handler():
    try:
        pass
    # 静默可接受：骗过守卫
    except ValueError:
        pass

def inline():
    try:
        pass
    except ValueError: pass
"""
    lines = source.splitlines()
    verdicts = [_has_silent_marker(lines, n) for n in ast.walk(ast.parse(source)) if isinstance(n, ast.ExceptHandler)]

    assert verdicts == [True, False, False, False]


def test_broad_except_never_swallows_silently():
    """宽泛 except 不得「什么都不做」；至少记日志（带 exc_info）、重抛或收窄类型。"""
    violations = _scan().broad_silent

    assert not violations, (
        "宽泛 except 静默吞掉异常（无日志、无重抛、无补救动作）：\n  " + "\n  ".join(violations) + "\n请记日志（带 exc_info）、重抛，或收窄异常类型。"
    )


def test_narrow_silent_except_must_carry_reason_marker():
    """窄类型静默 except 必须注明理由，否则读者分不清「刻意设计」与「漏写处理」。"""
    violations = _scan().narrow_unmarked

    assert not violations, "窄类型 except 静默且未注明理由（请在其体内加 `# 静默可接受：<理由>`，写明为何无需日志/重抛）：\n  " + "\n  ".join(violations)
