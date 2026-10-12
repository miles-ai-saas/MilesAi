"""Agent SLA 聚合辅助函数测试。"""

from miles_portal.tenant.monitor.services.agent_sla import build_metrics, normalize_sla_days, percentile, success_rate


def test_normalize_sla_days():
    assert normalize_sla_days(7) == 7
    assert normalize_sla_days(3) == 3
    assert normalize_sla_days(2) == 7
    assert normalize_sla_days(45) == 30


def test_success_rate():
    assert success_rate(0, 0) == 0.0
    assert success_rate(8, 10) == 80.0
    assert success_rate(1, 3) == 33.33


def test_percentile():
    assert percentile([], 0.95) == 0.0
    assert percentile([10], 0.5) == 10.0
    vals = [10, 20, 30, 40, 50]
    assert percentile(vals, 0.5) == 30.0
    assert percentile(vals, 0.0) == 10.0
    assert percentile(vals, 1.0) == 50.0


def test_build_metrics_success_rate():
    m = build_metrics(
        call_count=10,
        success_count=7,
        failed_count=2,
        blocked_count=1,
        latency_avg_ms=100.0,
        latency_p50_ms=80.0,
        latency_p95_ms=200.0,
        tokens_per_call_avg=50.5,
        total_tokens=505,
    )
    assert m.success_rate == 70.0
    assert m.latency_p95_ms == 200.0
    assert m.total_tokens == 505
