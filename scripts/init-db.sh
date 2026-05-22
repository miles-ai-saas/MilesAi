#!/usr/bin/env bash
# 项目根目录：数据库迁移 + 全量种子
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend"
python cli.py init-db "$@"
