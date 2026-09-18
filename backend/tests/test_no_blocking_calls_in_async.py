"""守卫：async 函数内不得直调阻塞调用（须经 ``asyncio.to_thread`` 离线）。

背景：本项目对象存储 ``ObjectStorage`` 协议是**纯同步**实现（``s3.py`` 用
``minio.Minio`` 同步客户端），多模态解析器（Pillow / pytesseract / openai-whisper
/ ffmpeg）同样是同步且 CPU 或子进程密集。这些调用出现在 ``async def`` 里会阻塞
整个事件循环 —— 单次请求即可让同一 worker 上所有并发请求排队。

既有正确写法见 ``miles_core/utils/health_checks.py``（``await asyncio.to_thread(...)``）；
本守卫把该约定从「靠记得」变为「可执行」。

阻塞面分三类，尽量自动派生以减小静默过期风险：

1. ``ObjectStorage`` 协议的同步方法 —— **从 ``storage/base.py`` 的协议类体自动解析**，
   协议新增方法即自动纳入；
2. 声明为同步实现的重模块（``_BLOCKING_MODULES``）—— 模块内定义的函数名全部视为阻塞；
3. stdlib 阻塞原语（``subprocess.*`` / ``os.system`` 等）—— 名单稳定，不易腐化。

为防止守卫自身静默失效，``test_blocking_surface_is_not_silently_empty`` 断言：
派生面非空且与预期成员相符、名单内模块确实存在、阻塞面名字与 ``async def`` 定义无
歧义、扫描面文件数非零。
"""

from __future__ import annotations

import ast
from pathlib import Path

from tests.paths import PACKAGES

#: 声明为「同步阻塞实现」的模块：模块内定义的函数均视为阻塞。
#: 刻意**不**包含 ``rag/parse/media.py``（纯判定函数）与纯导出模块。
_BLOCKING_MODULES: dict[str, str] = {
    "miles-ai/src/miles_ai/rag/parse/image_parser.py": "Pillow 解码 + pytesseract OCR（外部二进制）",
    "miles-ai/src/miles_ai/rag/parse/audio_parser.py": "openai-whisper 模型加载与转写",
    "miles-ai/src/miles_ai/rag/parse/video_parser.py": "ffmpeg 抽帧抽音（subprocess）",
    "miles-ai/src/miles_ai/rag/parse/loaders.py": "多模态解析总入口，逐类转交同步解析器",
    "miles-ai/src/miles_ai/integrations/generative/video/cover.py": "ffmpeg 抽封面（subprocess）",
}

#: stdlib 阻塞原语（点号全名）。
_BLOCKING_STDLIB: frozenset[str] = frozenset(
    {
        "subprocess.run",
        "subprocess.Popen",
        "subprocess.call",
        "subprocess.check_call",
        "subprocess.check_output",
        "os.system",
        "os.popen",
        "time.sleep",
    }
)

#: 判定「已离线」的包装函数名：其调用实参内不作为直调处理。
_OFFLOAD_CALLS: frozenset[str] = frozenset({"to_thread", "run_in_executor"})

_STORAGE_PROTOCOL = PACKAGES / "miles-core" / "src" / "miles_core" / "infra" / "storage" / "base.py"

#: 派生结果必须具备的成员，防止协议改写后守卫静默退化为空集。
_REQUIRED_STORAGE_METHODS: frozenset[str] = frozenset({"upload_bytes", "download_bytes", "delete_object"})


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


def _storage_sync_methods() -> set[str]:
    """从 ``ObjectStorage`` 协议类体派生同步方法名（排除 property 与 dunder）。"""
    methods: set[str] = set()
    for node in ast.walk(_parse(_STORAGE_PROTOCOL)):
        if not isinstance(node, ast.ClassDef):
            continue
        for item in node.body:
            if not isinstance(item, ast.FunctionDef):
                continue
            if item.name.startswith("__"):
                continue
            if any(isinstance(dec, ast.Name) and dec.id == "property" for dec in item.decorator_list):
                continue
            methods.add(item.name)
    return methods


def _module_defined_names(rel_path: str) -> set[str]:
    """模块内定义的全部函数名（含私有；整个模块已被声明为阻塞实现）。"""
    path = PACKAGES / rel_path
    if not path.is_file():
        raise FileNotFoundError(f"阻塞模块名单已过期，文件不存在：{rel_path}")
    return {node.name for node in ast.walk(_parse(path)) if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)}


def _module_declared_names() -> set[str]:
    names: set[str] = set()
    for rel_path in _BLOCKING_MODULES:
        names |= _module_defined_names(rel_path)
    return names


def _async_defined_names() -> set[str]:
    names: set[str] = set()
    for path in _iter_package_files():
        for node in ast.walk(_parse(path)):
            if isinstance(node, ast.AsyncFunctionDef):
                names.add(node.name)
    return names


class _BlockingCallVisitor(ast.NodeVisitor):
    """在 async 作用域内查找未离线的阻塞调用。"""

    def __init__(self, rel_path: str, *, storage: set[str], declared: set[str]) -> None:
        self._rel_path = rel_path
        self._storage = storage
        self._declared = declared
        self._stack: list[tuple[str, bool]] = []
        self._offload_depth = 0
        self.violations: list[str] = []

    def _enter(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self._stack.append((node.name, isinstance(node, ast.AsyncFunctionDef)))
        self.generic_visit(node)
        self._stack.pop()

    visit_FunctionDef = _enter
    visit_AsyncFunctionDef = _enter

    def _reason(self, dotted: str, leaf: str) -> str | None:
        if dotted in _BLOCKING_STDLIB:
            return "stdlib 阻塞原语"
        if leaf in self._storage:
            return "同步对象存储方法"
        if leaf in self._declared:
            return "同步阻塞解析器"
        return None

    def visit_Call(self, node: ast.Call) -> None:
        dotted = _dotted(node.func)
        leaf = dotted.split(".")[-1] if dotted else None

        if leaf in _OFFLOAD_CALLS:
            # 包装函数实参内视为「已离线」，不作为直调
            self._offload_depth += 1
            self.generic_visit(node)
            self._offload_depth -= 1
            return

        if self._offload_depth == 0 and dotted:
            reason = self._reason(dotted, leaf or "")
            enclosing = [name for name, is_async in self._stack if is_async]
            if reason and enclosing:
                self.violations.append(f"{self._rel_path}:{node.lineno}  {dotted}()  [{reason}]  位于 async {enclosing[-1]}()")
        self.generic_visit(node)


def _collect_violations() -> list[str]:
    storage = _storage_sync_methods()
    declared = _module_declared_names()
    violations: list[str] = []
    for path in _iter_package_files():
        visitor = _BlockingCallVisitor(str(path.relative_to(PACKAGES)), storage=storage, declared=declared)
        visitor.visit(_parse(path))
        violations.extend(visitor.violations)
    return violations


def test_blocking_surface_is_not_silently_empty():
    """守卫自检：派生面与名单必须真实有效，否则本文件会静默变成空转。"""
    files = _iter_package_files()
    assert files, "扫描面为空（未发现任何包内 .py），守卫会静默通过"

    storage = _storage_sync_methods()
    assert storage, f"未能从 {_STORAGE_PROTOCOL} 解析出同步方法，守卫会静默失效"
    missing = _REQUIRED_STORAGE_METHODS - storage
    assert not missing, f"存储协议派生结果缺少预期方法 {sorted(missing)}，守卫可能已失效"

    declared = _module_declared_names()
    assert declared, "阻塞模块名单未解析出任何函数"

    ambiguous = (storage | declared) & _async_defined_names()
    assert not ambiguous, f"以下名字既有同步阻塞实现又有 async 定义，按名字匹配会误伤/漏判，请改用限定名匹配：{sorted(ambiguous)}"


def test_async_functions_do_not_call_blocking_apis_directly():
    """async 内直调同步存储 / 同步解析器 / 阻塞原语，应全部经 ``to_thread`` 离线。"""
    violations = _collect_violations()
    assert not violations, "async 函数内出现直调阻塞调用（会阻塞事件循环），请用 ``await asyncio.to_thread(...)`` 包装：\n" + "\n".join(sorted(violations))
