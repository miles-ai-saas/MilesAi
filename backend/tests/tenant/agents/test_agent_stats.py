"""智能体统计聚合辅助函数测试。"""

from app.tenant.agents.services.stats import _avg_rounds, _day_range, _normalize_days, _series_from_map


def test_normalize_days():
    assert _normalize_days(7) == 7
    assert _normalize_days(10) == 10
    assert _normalize_days(2) == 7
    assert _normalize_days(100) == 90


def test_day_range_length():
    assert len(_day_range(7)) == 7
    assert len(_day_range(3)) == 3


def test_avg_rounds():
    assert _avg_rounds(0, 0) == 0.0
    assert _avg_rounds(10, 4) == 2.5


def test_series_from_map():
    series = _series_from_map(["2026-05-28", "2026-05-29"], {"2026-05-29": 3})
    assert series[0].value == 0
    assert series[1].value == 3
