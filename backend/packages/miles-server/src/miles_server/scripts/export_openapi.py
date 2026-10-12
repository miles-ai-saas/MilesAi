"""导出/校验 FastAPI OpenAPI 快照（无需起 uvicorn）。

离线交付：``--write`` 更新仓库契约；``--out PATH`` 导出到任意路径供内网分发。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from miles_server.apps.migrate import find_backend_root

ROOT = find_backend_root()
SNAPSHOT = ROOT / "openapi" / "openapi.snapshot.json"

# 与 tests/conftest 对齐，避免 LiteLLM 预加载 Bedrock schema 时打 WARNING
os.environ.setdefault("LITELLM_LOG", "ERROR")


def dump_schema() -> str:
    """构建应用并序列化 OpenAPI JSON（排序键，便于 diff）。"""
    from miles_server.apps.application import create_app

    schema = create_app().openapi()
    return json.dumps(schema, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description="导出/校验 FastAPI OpenAPI 快照（无需起 uvicorn）。")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--check", action="store_true", help="与仓库快照比对（默认）")
    g.add_argument("--write", action="store_true", help="写入 openapi/openapi.snapshot.json")
    g.add_argument(
        "--out",
        type=Path,
        metavar="PATH",
        help="导出到指定路径（离线包用；不更新仓库快照）",
    )
    args = p.parse_args()

    text = dump_schema()
    if args.out is not None:
        out = args.out.expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"wrote {out}")
        return 0
    if args.write:
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_text(text, encoding="utf-8")
        print(f"wrote {SNAPSHOT}")
        return 0

    if not SNAPSHOT.exists():
        print(f"missing snapshot: {SNAPSHOT}; run with --write", file=sys.stderr)
        return 1
    current = SNAPSHOT.read_text(encoding="utf-8")
    if current != text:
        print(
            "OpenAPI snapshot drift. Run: python -m miles_server.scripts.export_openapi --write",
            file=sys.stderr,
        )
        return 1
    print("OpenAPI snapshot OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
