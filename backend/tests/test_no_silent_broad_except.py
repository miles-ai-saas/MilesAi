"""守卫：宽泛 ``except`` 不得静默吞掉异常（须记日志、重抛或收窄类型）。

背景：``pytesseract`` pip 包与 ``tesseract`` **二进制**是两个独立依赖，slim 镜像常只
装前者。此时 ``image_to_string`` 抛 ``TesseractNotFoundError``（``OSError`` 子类），
曾被 ``except Exception`` 静默吞掉 —— 零日志，且占位文案还让人去「安装 pytesseract」，
把排查方向指反；占位文本又会被当作正文索引入库，检索质量静默下降。Whisper 模型下载
失败、ffmpeg 编解码器缺失同理。详见 ``tests/miles_ai/rag/test_parse_degradation_diagnosability.py``。

**判定「静默」**：handler 体仅由 ``pass`` / ``...`` / 字符串表达式（docstring）/
``return None`` / ``continue`` / ``break`` 组成 —— 既无日志、无重抛，也无任何补救动作，
故「吞掉」不留痕迹。``continue`` 与 ``break`` 与 ``pass`` 等价：都是「跳过、不留痕」，
把 ``pass`` 改写成 ``continue`` 不该能绕过本守卫。有日志（即使 ``debug``）、有 fd
兜底写入、有 return 非 None 值等，都**不算**静默。

**分三档**：

1. 宽泛类型（bare / ``Exception`` / ``BaseException``）**一律不得**静默：handler 体
   必须有日志、重抛或补救动作。全仓基线为 **0**，故无需豁免清单。
2. 宽泛类型若**打了日志却不重抛**，该日志必须带 ``exc_info``（或改用 ``logger.exception``）。
   只要求「有日志」是不够的：``logger.debug("Redis 不可用")`` 既无消息也无堆栈，默认
   INFO 级下生产不可见，于是宽泛捕获的真实原因（序列化错误、下游 bug）会被永久归因为
   「Redis 不可用」。**注意**：不记日志、而是把 ``str(exc)`` 塞进结构化返回值的情形
   （健康探测 ``return False``、``return {"ok": False, "message": ...}``）**不属**此档 ——
   那些诊断出口不在日志，逐个补堆栈只会让轮询型探测刷屏。
3. 窄类型（``except ValueError`` 判「不是 UUID」、``except ImportError`` 判可选依赖等）
   允许静默 —— 那是有意的控制流，拦它收益低而误报高 —— 但**必须在 handler 体内注明
   ``# 静默可接受：<理由>``**。理由缺失即违规：否则读者无法区分「刻意设计」与「漏写
   处理」，注释也会随重构逐条流失。

另：``contextlib.suppress(<宽泛异常>)`` 是 ``except <宽泛异常>: pass`` 的语法糖，故与第 1 档同判据 ——
只扫 ``try/except`` 的话，一行改写即可绕过整个守卫。

三档都只认「有没有留下痕迹/理由」，不评价其质量（长度、关键词等）—— 那是 code review
的事，机器只保证「此处异常是被人想过的」。
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

#: 视为「日志调用」的方法名（``logger.<level>(...)``）。
_LOGGER_LEVELS: frozenset[str] = frozenset({"debug", "info", "warning", "warn", "error", "critical", "exception", "log"})

#: ``contextlib.suppress`` 的点号名 —— 它是 ``try/except/pass`` 的语法糖，同一判据须一并覆盖。
_SUPPRESS_NAMES: frozenset[str] = frozenset({"contextlib.suppress"})


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
    ``return None`` / ``continue`` / ``break`` 才算静默，任何其他语句（含 ``raise``）
    一律不算。``continue`` / ``break`` 归入白名单，是因为它们与 ``pass`` 一样只是
    「跳过、不留痕」——否则把 ``pass`` 改写成一个 ``continue`` 就能绕过守卫。
    """
    for stmt in body:
        if isinstance(stmt, ast.Pass):
            continue
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
            continue  # docstring 或 ``...``
        if isinstance(stmt, ast.Return) and (stmt.value is None or (isinstance(stmt.value, ast.Constant) and stmt.value.value is None)):
            continue
        if isinstance(stmt, (ast.Continue, ast.Break)):
            continue
        return False
    return True


def _logs(body: list[ast.stmt]) -> bool:
    """handler 体内是否调用了日志方法（``logger.<level>(...)``）。"""
    return any(
        isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in _LOGGER_LEVELS
        for node in ast.walk(ast.Module(body=body, type_ignores=[]))
    )


def _traceability(body: list[ast.stmt]) -> str | None:
    """handler 体是否留下**可解读**的痕迹，返回痕迹类型；否则 None。

    三种算数：重抛（堆栈完整交给上层）、``logger.exception(...)``、任意日志调用带
    ``exc_info`` 关键字。显式 ``exc_info=False`` 不算 —— 那正是「记了但没堆栈」。
    """
    for node in ast.walk(ast.Module(body=body, type_ignores=[])):
        if isinstance(node, ast.Raise):
            return "重抛"
        if isinstance(node, ast.Attribute) and node.attr == "exception":
            return "logger.exception"
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg == "exc_info" and not (isinstance(kw.value, ast.Constant) and kw.value.value is False):
                    return "exc_info"
    return None


def _suppress_aliases(tree: ast.Module) -> set[str]:
    """模块内 ``from contextlib import suppress [as X]`` 引入的名字。

    只认这个来源，是为了不把碰巧同名的无关函数（如自定义 ``suppress(...)``）误判成糖。
    """
    aliases = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "contextlib":
            aliases.update(alias.asname or alias.name for alias in node.names if alias.name == "suppress")
    return aliases


def _broad_suppress(node: ast.With | ast.AsyncWith, names: set[str]) -> bool:
    """``with [contextlib.]suppress(<宽泛异常>)`` —— 等价于 ``except <宽泛异常>: pass``。

    逐个位置参数检查：``suppress(ValueError, OSError)`` 是多参数形式（不是元组）。
    """
    for item in node.items:
        expr = item.context_expr
        if not isinstance(expr, ast.Call) or _dotted(expr.func) not in names:
            continue
        for arg in expr.args:
            exprs = arg.elts if isinstance(arg, ast.Tuple) else [arg]
            if any(_dotted(e) in _BROAD_EXCEPTIONS for e in exprs):
                return True
    return False


@dataclass
class _Scan:
    """一次全仓扫描的结果。"""

    broad_handlers: int = 0
    """宽泛 handler 总数（含已记日志/重抛的），用于守卫自检扫描面非空。"""

    broad_silent: list[str] = field(default_factory=list)
    """宽泛且静默 —— 违规。"""

    broad_untraceable: list[str] = field(default_factory=list)
    """宽泛、打了日志但不重抛、且日志无 ``exc_info`` —— 违规。"""

    narrow_silent: int = 0
    """窄类型且静默的 handler 总数（含已注明理由的），用于守卫自检扫描面非空。"""

    narrow_unmarked: list[str] = field(default_factory=list)
    """窄类型、静默、且未注明理由 —— 违规。"""

    broad_suppress: list[str] = field(default_factory=list)
    """``contextlib.suppress(<宽泛异常>)`` —— 违规（``except`` 静默的语法糖写法）。"""


def _scan() -> _Scan:
    """扫描全部包内文件，按两档规则收集违规位置。"""
    result = _Scan()
    for path in _iter_package_files():
        rel = path.relative_to(PACKAGES).as_posix()
        source = path.read_text(encoding="utf-8", errors="replace")
        lines = source.splitlines()
        tree = ast.parse(source)
        suppress_names = _suppress_aliases(tree) | _SUPPRESS_NAMES
        for node in ast.walk(tree):
            if isinstance(node, (ast.With, ast.AsyncWith)):
                if _broad_suppress(node, suppress_names):
                    result.broad_suppress.append(f"{rel}:{node.lineno}")
                continue
            if not isinstance(node, ast.ExceptHandler):
                continue
            silent = _is_silent(node.body)
            if _is_broad(node):
                result.broad_handlers += 1
                if silent:
                    result.broad_silent.append(f"{rel}:{node.lineno}")
                elif _logs(node.body) and _traceability(node.body) is None:
                    result.broad_untraceable.append(f"{rel}:{node.lineno}")
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
    assert len(result.broad_untraceable) <= result.broad_handlers
    assert len(result.narrow_unmarked) <= result.narrow_silent
    assert len(result.broad_suppress) <= result.broad_handlers


def test_detector_flags_silent_and_spares_logging_narrow_and_reraise():
    """检测器自检：静默要报；记日志 / 窄类型 / 重抛都不报。

    防三类退化：恒 False（守卫失效）、把 ``raise`` 误判为静默（会把全仓 8 处
    ``except Exception as exc: raise ... from exc`` 全部误报）、以及漏把
    ``continue`` / ``break`` 算作静默（那样把 ``pass`` 改成 ``continue`` 即可绕过）。
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

def skips_item():
    for _ in items:
        try:
            pass
        except Exception:
            continue

def breaks_loop():
    for _ in items:
        try:
            pass
        except Exception:
            break
"""
    )
    verdicts = [(_is_broad(n), _is_silent(n.body)) for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler)]

    assert verdicts == [
        (True, True),  # silent
        (True, False),  # logged
        (False, True),  # narrowed
        (True, False),  # reraises
        (True, True),  # continue：与 pass 等价，跳过不留痕
        (True, True),  # break：同上
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


def test_traceability_detector_spares_exc_info_exception_and_reraise():
    """痕迹检测器自检：``exc_info`` / ``logger.exception`` / 重抛算有痕迹；``exc_info=False`` 不算。"""
    source = """
def plain():
    try:
        pass
    except Exception:
        logger.warning("x")

def with_exc_info():
    try:
        pass
    except Exception:
        logger.warning("x", exc_info=True)

def with_exception():
    try:
        pass
    except Exception:
        logger.exception("x")

def with_exc_info_false():
    try:
        pass
    except Exception:
        logger.warning("x", exc_info=False)

def reraises():
    try:
        pass
    except Exception as exc:
        raise BadRequestError(str(exc)) from exc

def structured_return():
    try:
        pass
    except Exception as exc:
        return {"error": str(exc)}
"""
    handlers = [n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.ExceptHandler)]

    assert [(_logs(n.body), _traceability(n.body)) for n in handlers] == [
        (True, None),  # plain：日志无堆栈 —— 违规
        (True, "exc_info"),
        (True, "logger.exception"),
        (True, None),  # 显式 exc_info=False：等于没堆栈 —— 违规
        (False, "重抛"),  # 重抛无需日志
        (False, None),  # 无日志、结构化返回值承载诊断 —— 不在本档
    ]


def test_broad_contextlib_suppress_is_also_a_silent_swallow():
    """``contextlib.suppress(Exception)`` 是 ``except Exception: pass`` 的糖，同样不得用。

    否则「宽泛 except 不得静默」的判据一行改写即可绕过。
    """
    violations = _scan().broad_suppress

    assert not violations, (
        "contextlib.suppress 吞掉宽泛异常，等价于静默 except：\n  "
        + "\n  ".join(violations)
        + "\n请收窄到具体异常类型，或改用 try/except 并记日志（带 exc_info）。"
    )


def test_broad_suppress_detector_needs_contextlib_origin():
    """糖检测器自检：``contextlib.suppress`` 与 ``from contextlib import suppress`` 都认；
    宽泛类型要报、窄类型放过；未被 contextlib 引入的同名函数不得误判。"""
    source = """
import contextlib
from contextlib import suppress

def dotted_broad():
    with contextlib.suppress(Exception):
        pass

def imported_broad():
    with suppress(BaseException):
        pass

def imported_narrow():
    with suppress(asyncio.CancelledError):
        pass

def dotted_narrow():
    with contextlib.suppress(ValueError, OSError):
        pass
"""
    # 去掉 ``from contextlib import suppress`` 后，同名函数不得再被算作糖
    unrelated = """
def unrelated_same_name():
    with suppress(Exception):
        pass
"""
    assert _suppress_verdicts(source) == [True, True, False, False]
    assert _suppress_verdicts(unrelated) == [False], "碰巧同名的无关函数被误判为 contextlib 糖"


def _suppress_verdicts(source: str) -> list[bool]:
    """对一段源码里的每个 ``with`` 判定是否为宽泛 suppress。"""
    tree = ast.parse(source)
    names = _suppress_aliases(tree) | _SUPPRESS_NAMES
    return [_broad_suppress(n, names) for n in ast.walk(tree) if isinstance(n, (ast.With, ast.AsyncWith))]


def test_broad_except_logging_must_carry_traceback():
    """宽泛 except 若打了日志却不重抛，日志必须带 ``exc_info``（或改用 ``logger.exception``）。"""
    violations = _scan().broad_untraceable

    assert not violations, (
        "宽泛 except 打了日志但无堆栈，且未重抛 —— 痕迹不可解读（默认 INFO 级下 debug 甚至不可见）：\n  "
        + "\n  ".join(violations)
        + "\n请给该日志加 exc_info=True / 改用 logger.exception，或重抛（from exc）。"
    )


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
