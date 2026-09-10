"""中立域合规流水线单测（纯算法，无 ORM/DB）。"""

from app.models.compliance.constants import SensitiveAction
from app.models.compliance.pipeline import CompliancePipeline


def test_scan_hits_and_block_priority() -> None:
    """命中多个词时 BLOCK 优先于 WARN。"""
    pipeline = CompliancePipeline(
        [
            ("foo", SensitiveAction.WARN),
            ("bar", SensitiveAction.BLOCK),
        ]
    )
    result = pipeline.scan("FOO bar")

    assert len(result.matches) == 2
    assert result.has_block is True
    assert result.has_warn is True
    assert result.worst_action is SensitiveAction.BLOCK


def test_scan_case_insensitive_and_strip() -> None:
    """词表词面大小写不敏感、空白裁剪。"""
    pipeline = CompliancePipeline([(" Foo ", SensitiveAction.WARN)])
    result = pipeline.scan("xfooX")

    assert len(result.matches) == 1
    assert result.matches[0].word == "foo"
    assert result.worst_action is SensitiveAction.WARN


def test_scan_empty_text_and_empty_words() -> None:
    """空文本或空词表返回空结果。"""
    for result in (
        CompliancePipeline([("foo", SensitiveAction.WARN)]).scan(""),
        CompliancePipeline([]).scan("abc"),
    ):
        assert result.matches == ()
        assert result.has_block is False
        assert result.has_warn is False
        assert result.worst_action is None


def test_shim_equivalence() -> None:
    """tenant 侧路径与中立域指向同一对象。"""
    from app.models.compliance.pipeline import CompliancePipeline as NeutralPipeline
    from app.tenant.compliance.services.pipeline import CompliancePipeline as ShimPipeline

    assert NeutralPipeline is ShimPipeline

    from app.models.compliance.constants import SensitiveAction as NeutralAction
    from app.tenant.compliance.models import SensitiveAction as ShimAction

    assert NeutralAction is ShimAction
