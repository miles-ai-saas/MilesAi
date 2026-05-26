#!/usr/bin/env python3
"""MilesAi 统一 CLI：API / Worker 启动与运维脚本。

在 backend 目录执行:
  python cli.py serve
  python cli.py worker
  python cli.py migrate
  python cli.py init-db
  python cli.py seed all
  python cli.py verify-db
  python cli.py backfill-media-assets [--dry-run] [--tenant-id UUID]

安装 editable 后也可: milesai serve
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path

import click

_BACKEND_ROOT = Path(__file__).resolve().parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

def _seed_choices() -> list[str]:
    from scripts.db_ops import SEED_TARGETS

    return ["all", *sorted(SEED_TARGETS)]


@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
    invoke_without_command=True,
)
@click.version_option(package_name="milesai", prog_name="milesai")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """MilesAi 统一命令行入口（API、Worker、迁移与种子）。"""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@cli.command()
@click.option("--host", default=None, help="监听地址（默认读配置 api_host）")
@click.option("--port", type=int, default=None, help="端口（默认读配置 api_port）")
@click.option("--reload/--no-reload", default=None, help="热重载；未指定时跟随 settings.debug")
def serve(host: str | None, port: int | None, reload: bool | None) -> None:
    """启动 FastAPI (uvicorn)。"""
    import uvicorn

    from app.core.config import get_settings
    from app.core.logging import setup_logging

    setup_logging()
    settings = get_settings()
    if reload is None:
        reload = settings.debug

    uvicorn.run(
        "app.main:app",
        host=host or settings.api_host,
        port=port or settings.api_port,
        reload=reload,
        factory=False,
    )


@cli.command()
@click.option(
    "-Q",
    "--queues",
    default="parse,default",
    show_default=True,
    help="监听队列，逗号分隔",
)
@click.option("-l", "--loglevel", default="info", show_default=True, help="日志级别")
@click.option("-c", "--concurrency", type=int, default=None, help="并发进程数")
def worker(queues: str, loglevel: str, concurrency: int | None) -> None:
    """启动 Celery Worker。"""
    cmd = [
        sys.executable,
        "-m",
        "celery",
        "-A",
        "app.workers.app",
        "worker",
        "-Q",
        queues,
        "-l",
        loglevel,
    ]
    if concurrency is not None:
        cmd.extend(["-c", str(concurrency)])
    raise SystemExit(subprocess.call(cmd))


@cli.command()
@click.option("-l", "--loglevel", default="info", show_default=True, help="日志级别")
def beat(loglevel: str) -> None:
    """启动 Celery Beat（智能体定时任务扫描）。"""
    cmd = [
        sys.executable,
        "-m",
        "celery",
        "-A",
        "app.workers.app",
        "beat",
        "-l",
        loglevel,
    ]
    raise SystemExit(subprocess.call(cmd))


@cli.command()
def migrate() -> None:
    """执行 Alembic upgrade head。"""
    from scripts.db_ops import run_migrate

    run_migrate()


@cli.command("init-db")
@click.option("--migrate-only", is_flag=True, help="仅执行迁移")
@click.option("--seed-only", is_flag=True, help="仅写入种子（需已有表）")
def init_db(migrate_only: bool, seed_only: bool) -> None:
    """数据库迁移 + 全量种子。"""
    if migrate_only and seed_only:
        raise click.UsageError("不能同时指定 --migrate-only 与 --seed-only")

    from scripts.db_ops import run_init_db_sync

    run_init_db_sync(migrate=not seed_only, seed=not migrate_only)


@cli.command()
@click.argument(
    "target",
    type=click.Choice(_seed_choices(), case_sensitive=False),
)
def seed(target: str) -> None:
    """写入种子数据（target: all / tenant / compliance / …）。"""
    from scripts.db_ops import run_seed_sync

    run_seed_sync(target.lower() if target != "all" else "all")


@cli.command("verify-db")
def verify_db() -> None:
    """检查迁移版本与核心表是否齐全。"""
    from scripts.verify_db import main as verify_main

    raise SystemExit(asyncio.run(verify_main()))


@cli.command("backfill-media-assets")
@click.option("--tenant-id", default=None, help="仅处理指定租户 UUID")
@click.option("--dry-run", is_flag=True, help="只统计将创建条数，不写库")
@click.option("--limit", type=int, default=None, help="最多处理附件条数")
def backfill_media_assets(
    tenant_id: str | None,
    dry_run: bool,
    limit: int | None,
) -> None:
    """为历史生成附件补写 media_assets 登记。"""
    from uuid import UUID

    from scripts.backfill_media_assets import run_backfill_media_assets

    tid = UUID(tenant_id) if tenant_id else None
    stats = asyncio.run(
        run_backfill_media_assets(tenant_id=tid, dry_run=dry_run, limit=limit)
    )
    mode = "dry-run" if dry_run else "committed"
    click.echo(
        f">>> backfill-media-assets ({mode}): "
        f"scanned={stats['scanned']} created={stats['created']} "
        f"skipped={stats['skipped']} errors={stats['errors']}"
    )


def main() -> None:
    cli(standalone_mode=True)


if __name__ == "__main__":
    main()
