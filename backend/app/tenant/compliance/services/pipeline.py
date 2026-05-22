"""敏感词检测流水线。"""

from dataclasses import dataclass

from app.tenant.compliance.models import SensitiveAction


@dataclass(frozen=True)
class ScanMatch:
    word: str
    action: SensitiveAction


@dataclass(frozen=True)
class ScanResult:
    matches: tuple[ScanMatch, ...]

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
    def __init__(self, words: list[tuple[str, SensitiveAction]]) -> None:
        self._words = [(w.strip().lower(), a) for w, a in words if w.strip()]

    def scan(self, text: str) -> ScanResult:
        if not text or not self._words:
            return ScanResult(matches=())
        lower = text.lower()
        matches: list[ScanMatch] = []
        for word, action in self._words:
            if word in lower:
                matches.append(ScanMatch(word=word, action=action))
        return ScanResult(matches=tuple(matches))
