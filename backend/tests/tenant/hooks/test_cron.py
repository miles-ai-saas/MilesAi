"""Cron 工具单元测试。"""

import pytest

from miles_common.cron import compute_next_run, describe_cron, validate_cron


def test_validate_cron_accepts_five_part_expr():
    assert validate_cron("0 8 * * 1-5") == "0 8 * * 1-5"


def test_validate_cron_rejects_wrong_part_count():
    with pytest.raises(ValueError, match="5 段"):
        validate_cron("0 8 * *")


def test_validate_cron_rejects_invalid_expr():
    with pytest.raises(ValueError, match="无效"):
        validate_cron("99 99 * * *")


def test_describe_cron_every_hour():
    assert describe_cron("0 * * * *") == "每小时整点执行"


def test_describe_cron_weekday_morning():
    assert describe_cron("0 8 * * 1-5") == "工作日 08:00 执行"


def test_compute_next_run_returns_future():
    from datetime import datetime, timezone

    base = datetime(2026, 5, 25, 7, 30, tzinfo=timezone.utc)
    nxt = compute_next_run("0 8 * * *", base)
    assert nxt.hour == 8
    assert nxt > base
