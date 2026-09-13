"""标准 5 段 Cron 校验与 next_run 计算（Celery crontab / croniter）。"""

from __future__ import annotations

from datetime import UTC, datetime

from croniter import croniter


def validate_cron(cron: str) -> str:
    """校验并规范化 5 段 Cron 表达式。"""
    expr = " ".join(cron.split())
    parts = expr.split(" ")
    if len(parts) != 5:
        raise ValueError("Cron 表达式须为 5 段：分 时 日 月 周")
    try:
        croniter(expr)
    except (ValueError, KeyError) as exc:
        raise ValueError(f"无效的 Cron 表达式: {exc}") from exc
    return expr


def compute_next_run(cron: str, base: datetime | None = None) -> datetime:
    """计算下次执行时间（UTC）。"""
    expr = validate_cron(cron)
    ref = base or datetime.now(UTC)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=UTC)
    return croniter(expr, ref).get_next(datetime)


def describe_cron(cron: str) -> str:
    """生成简短中文描述（供列表展示）。"""
    expr = validate_cron(cron)
    minute, hour, dom, month, dow = expr.split(" ")

    if minute.startswith("*/"):
        interval = minute[2:]
        if hour == "*" and dom == "*" and month == "*" and dow == "*":
            return f"每 {interval} 分钟执行"
    if minute == "0" and hour == "*" and dom == "*" and month == "*" and dow == "*":
        return "每小时整点执行"
    if minute == "0" and hour.startswith("*/") and dom == "*" and month == "*" and dow == "*":
        return f"每 {hour[2:]} 小时执行"
    if dom == "*" and month == "*" and dow == "1-5" and minute.isdigit() and hour.isdigit():
        return f"工作日 {hour.zfill(2)}:{minute.zfill(2)} 执行"
    if dom == "*" and month == "*" and dow == "*" and minute.isdigit() and hour.isdigit():
        return f"每天 {hour.zfill(2)}:{minute.zfill(2)} 执行"
    if dom == "1" and month == "*" and dow == "*" and minute == "0" and hour == "0":
        return "每月 1 号零点执行"
    if dow == "1" and dom == "*" and month == "*" and minute.isdigit() and hour.isdigit():
        return f"每周一 {hour.zfill(2)}:{minute.zfill(2)} 执行"

    dow_labels = {
        "0": "周日",
        "1": "周一",
        "2": "周二",
        "3": "周三",
        "4": "周四",
        "5": "周五",
        "6": "周六",
    }
    if dom == "*" and month == "*" and dow in dow_labels and minute.isdigit() and hour.isdigit():
        return f"每{dow_labels[dow]} {hour.zfill(2)}:{minute.zfill(2)} 执行"

    return f"Cron: {expr}"
