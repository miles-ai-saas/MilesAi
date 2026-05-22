#!/usr/bin/env python3
"""兼容入口：python cli.py seed model-catalog"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from scripts.db_ops import run_seed_sync

if __name__ == "__main__":
    run_seed_sync("model-catalog")
