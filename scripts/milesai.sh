#!/usr/bin/env bash
# 项目根目录：转发到 backend/cli.py
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend"
exec python cli.py "$@"
