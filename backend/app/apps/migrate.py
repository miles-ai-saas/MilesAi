import subprocess
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[2]
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
            "数据库迁移失败（alembic upgrade head）。"
            "请确认 PostgreSQL 已启动，且 backend/.env 中 POSTGRES_DB 与数据库实例一致。\n"
            f"{detail}"
        ) from None
