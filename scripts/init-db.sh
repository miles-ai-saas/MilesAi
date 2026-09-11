#!/usr/bin/env bash
# 项目根目录：数据库迁移 + 全量种子；优先使用 backend/.venv 中的 milesai 入口。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend"
if [ -x ".venv/bin/milesai" ]; then
  exec .venv/bin/milesai init-db "$@"
fi
exec python -m miles_server.cli init-db "$@"
