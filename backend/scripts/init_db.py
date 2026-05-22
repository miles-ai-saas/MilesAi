#!/usr/bin/env python3
"""兼容入口：请优先使用 python cli.py init-db"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.db_ops import run_init_db_sync


def main() -> None:
    parser = argparse.ArgumentParser(description="MilesAi DB migrate + seed")
    parser.add_argument("--migrate-only", action="store_true")
    parser.add_argument("--seed-only", action="store_true")
    args = parser.parse_args()
    run_init_db_sync(migrate=not args.seed_only, seed=not args.migrate_only)


if __name__ == "__main__":
    main()
