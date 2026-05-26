"""敏感词检测流水线（子串匹配，大小写不敏感）。"""

from dataclasses import dataclass

from app.tenant.compliance.models import SensitiveAction


@dataclass(frozen=True)
class ScanMatch:
    """单条敏感词命中。"""

    word: str  # 命中的词
    action: SensitiveAction  # 处置动作（warn / block）


@dataclass(frozen=True)
class ScanResult:
    """一次扫描的汇总结果。"""

    matches: tuple[ScanMatch, ...]  # 全部命中项

    @property
    def has_block(self) -> bool:
        return any(m.action == SensitiveAction.BLOCK for m in self.matches)

    @property
    def has_warn(self) -> bool:
        return any(m.action == SensitiveAction.WARN for m in self.matches)

    @property
    def worst_action(self) -> SensitiveAction | None:
        if self.has_block:
            return SensitiveAction.BLOCK
        if self.has_warn:
            return SensitiveAction.WARN
        return None


class CompliancePipeline:
    """内存词表扫描；BLOCK 优先于 WARN。"""

    def __init__(self, words: list[tuple[str, SensitiveAction]]) -> None:
        self._words = [(w.strip().lower(), a) for w, a in words if w.strip()]

    def scan(self, text: str) -> ScanResult:
        """扫描文本，返回所有命中词及动作。"""
        if not text or not self._words:
            return ScanResult(matches=())
        lower = text.lower()
        matches: list[ScanMatch] = []
        for word, action in self._words:
            if word in lower:
                matches.append(ScanMatch(word=word, action=action))
        return ScanResult(matches=tuple(matches))
