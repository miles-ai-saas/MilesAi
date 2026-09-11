"""API 启动时自动执行 Alembic upgrade head（种子数据不在此执行）。"""

import subprocess
import sys
from pathlib import Path


def find_backend_root() -> Path:
    """定位 backend 根（含 alembic.ini）：从 cwd 逐级上溯，找不到则回退到包外五级。

    本文件位于 ``packages/miles-server/src/miles_server/apps/migrate.py``，
    故 backend 根是 ``parents[5]``（0=apps 1=miles_server 2=src 3=miles-server 4=packages）。
    """
    for base in (Path.cwd(), Path(__file__).resolve()):
        for candidate in (base, *base.parents):
            if (candidate / "alembic.ini").is_file():
                return candidate
    return Path(__file__).resolve().parents[5]


_BACKEND_DIR = find_backend_root()
_ALEMBIC_INI = _BACKEND_DIR / "alembic.ini"


def run_migrations() -> None:
    """在 backend 目录下执行 alembic，并显式指定 alembic.ini 路径。"""
    if not _ALEMBIC_INI.exists():
        raise FileNotFoundError(f"未找到 Alembic 配置: {_ALEMBIC_INI}")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            str(_ALEMBIC_INI),
            "upgrade",
            "head",
        ],
        cwd=str(_BACKEND_DIR),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(
            f"数据库迁移失败（alembic upgrade head）。请确认 PostgreSQL 已启动，且 backend/.env 中 POSTGRES_DB 与数据库实例一致。\n{detail}"
        ) from None
