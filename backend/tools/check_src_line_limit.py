#!/usr/bin/env python3
"""门禁：``packages/*/src`` 下业务 ``.py`` 单文件不得 ≥ ``LIMIT`` 行。

与 ``backend/README.md``「单文件体量」约定对齐。存量超标文件列入
``ALLOWLIST``，新增超标或扩大 allowlist 外体积一律失败。
"""

from __future__ import annotations

import sys
from pathlib import Path

LIMIT = 500

#: 相对 ``backend/`` 的路径。拆分后应从本表移除。
ALLOWLIST: frozenset[str] = frozenset(
    {
        # 种子目录数据偏长，按脚本豁免口径保留。
        "packages/miles-server/src/miles_server/scripts/seed/model_catalog.py",
    }
)

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    offenders: list[tuple[int, str]] = []
    allow_violations: list[tuple[int, str]] = []
    stale_allow: list[str] = []

    for path in sorted(ROOT.glob("packages/*/src/**/*.py")):
        rel = path.relative_to(ROOT).as_posix()
        # 与 README 一致：版本脚本不扫；种子数据文件可在 allowlist。
        if "/alembic/" in rel:
            continue
        lines = sum(1 for _ in path.open(encoding="utf-8", errors="replace"))
        if lines < LIMIT:
            if rel in ALLOWLIST:
                stale_allow.append(rel)
            continue
        if rel in ALLOWLIST:
            allow_violations.append((lines, rel))
        else:
            offenders.append((lines, rel))

    missing_allow = sorted(rel for rel in ALLOWLIST if not (ROOT / rel).is_file())

    ok = True
    if offenders:
        ok = False
        print(f"ERROR: 以下源文件 ≥ {LIMIT} 行且不在 ALLOWLIST（须拆分后再合入）：", file=sys.stderr)
        for n, rel in sorted(offenders, reverse=True):
            print(f"  {n:5d}  {rel}", file=sys.stderr)

    if stale_allow:
        ok = False
        print("ERROR: ALLOWLIST 中下列文件已低于上限，请从 tools/check_src_line_limit.py 移除：", file=sys.stderr)
        for rel in stale_allow:
            print(f"  {rel}", file=sys.stderr)

    if missing_allow:
        ok = False
        print("ERROR: ALLOWLIST 路径不存在：", file=sys.stderr)
        for rel in missing_allow:
            print(f"  {rel}", file=sys.stderr)

    if allow_violations:
        print(f"NOTE: 存量超标（allowlist，共 {len(allow_violations)}）：")
        for n, rel in sorted(allow_violations, reverse=True):
            print(f"  {n:5d}  {rel}")

    if ok and not allow_violations:
        print(f"OK: 无 ≥ {LIMIT} 行源文件")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
