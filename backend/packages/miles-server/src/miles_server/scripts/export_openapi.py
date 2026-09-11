"""导出/校验 FastAPI OpenAPI 快照（无需起 uvicorn）。"""

from __future__ import annotations

import argparse
import json
import os
import sys

from miles_server.apps.migrate import find_backend_root

ROOT = find_backend_root()
SNAPSHOT = ROOT / "openapi" / "openapi.snapshot.json"

# 与 tests/conftest 对齐，避免 LiteLLM 预加载 Bedrock schema 时打 WARNING
os.environ.setdefault("LITELLM_LOG", "ERROR")


def dump_schema() -> str:
    from miles_server.apps.application import create_app

    schema = create_app().openapi()
    return json.dumps(schema, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description="导出/校验 FastAPI OpenAPI 快照（无需起 uvicorn）。")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--check", action="store_true", help="与仓库快照比对（默认）")
    g.add_argument("--write", action="store_true", help="写入 openapi/openapi.snapshot.json")
    args = p.parse_args()

    text = dump_schema()
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
