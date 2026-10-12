"""评测规则打分。"""

from miles_portal.tenant.eval.services.scoring import score_with_rules


def test_exact_match():
    score, passed, detail = score_with_rules("Hello", {"exact": "Hello"})
    assert score == 1.0 and passed is True
    assert detail["method"] == "exact"


def test_exact_mismatch():
    score, passed, _ = score_with_rules("Hello", {"exact": "Hi"})
    assert score == 0.0 and passed is False


def test_contains():
    score, passed, detail = score_with_rules("答案包含关键词ABC", {"contains": "关键词"})
    assert score == 1.0 and passed is True
    assert detail["method"] == "contains"


def test_contains_all_missing():
    score, passed, detail = score_with_rules("只有A", {"contains_all": ["A", "B"]})
    assert score == 0.0 and passed is False
    assert detail["missing"] == ["B"]


def test_no_expected():
    score, passed, detail = score_with_rules("x", None)
    assert score is None and passed is None
    assert detail["method"] == "none"
