#!/usr/bin/env bash
# 清空 public schema 后重新迁移（开发环境慎用）
set -euo pipefail
cd "$(dirname "$0")/.."

echo ">>> 当前库配置来自 backend/.env"
python -c "from app.core.config import get_settings; s=get_settings(); print(f'  {s.database_url}')"

echo ">>> 降级到 base"
python -m alembic -c alembic.ini downgrade base

echo ">>> 升级到 head"
python -m alembic -c alembic.ini upgrade head

echo ">>> 校验"
python scripts/verify_db.py
