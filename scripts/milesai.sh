#!/usr/bin/env bash
# 项目根目录：转发到后端统一 CLI（milesai）；优先使用 backend/.venv 中的入口。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend"
if [ -x ".venv/bin/milesai" ]; then
  exec .venv/bin/milesai "$@"
fi
exec python -m miles_server.cli "$@"
