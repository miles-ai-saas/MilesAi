#!/usr/bin/env bash
# 在 backend 目录执行数据库迁移
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
exec python -m alembic -c alembic.ini "$@"
