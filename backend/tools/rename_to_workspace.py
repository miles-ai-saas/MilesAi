#!/usr/bin/env python3
"""一次性 codemod：把 app.* 引用改写为 miles_* 包路径。

同时改写 import 语句与字符串字面量中的点分模块路径
（如 patch 目标、celery 任务名、include 列表）。

用法：
  cd backend
  .venv/bin/python tools/rename_to_workspace.py --dry-run
  .venv/bin/python tools/rename_to_workspace.py --apply

注意：本脚本为一次性 codemod，已在 Task 2.2 执行完毕；`app.workers.app`
一条当时为人工修正（映射到 `miles_worker.app`），保留此处仅为记录，**勿直接重跑**。
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]

# 旧前缀 → 新前缀；按长度降序生效（最长优先，避免被短前缀截断）。
RULES: list[tuple[str, str]] = [
    ("app.tenant.agents.views.open_chat", "miles_openapi.views.open_chat"),
    # 注意：app.tenant.agents.deps_api_auth **不映射到 openapi**——它是 portal 与
    # openapi 共享的鉴权依赖，归属留 portal（Task 1.8 修正），走通用 app.tenant 规则。
    ("app.openapi", "miles_openapi"),
    ("app.tenant.mcp.runner.spec", "miles_exec.mcp.spec"),
    ("app.tenant.mcp.constants", "miles_exec.mcp.constants"),
    ("app.tenant.mcp.rpc", "miles_exec.mcp.rpc"),
    ("app.tenant.tools.script_validate", "miles_exec.sandbox.validate"),
    ("app.admin.app_ops.services.risk_enforce", "miles_core.risk.enforce"),
    ("app.admin.models.risk", "miles_core.models.risk"),
    ("app.models.registry", "miles_server.registry"),
    ("app.common.pagination", "miles_core.pagination"),
    ("app.common.url_security", "miles_core.url_security"),
    ("app.common.handlers", "miles_core.web.handlers"),
    ("app.utils.redis_keys", "miles_common.redis_keys"),
    ("app.utils.health_checks", "miles_core.utils.health_checks"),
    ("app.utils.idgen", "miles_common.idgen"),
    ("app.utils.orm", "miles_core.utils.orm"),
    ("app.workers.app", "miles_worker.app"),
    ("app.runner.script_exec", "miles_exec.sandbox.script_exec"),
    ("app.runner.session", "miles_exec.sandbox.session"),
    ("app.runner.limits", "miles_runner.limits"),
    ("app.runner.main", "miles_runner.main"),
    ("app.runner", "miles_runner"),
    ("app.flow_runtime", "miles_ai.flow_runtime"),
    ("app.integrations", "miles_ai.integrations"),
    ("app.middlewares", "miles_core.web.middlewares"),
    ("app.marketplace", "miles_portal.marketplace"),
    ("app.deletion", "miles_portal.deletion"),
    ("app.infra", "miles_core.infra"),
    ("app.models", "miles_core.models"),
    ("app.tenant", "miles_portal.tenant"),
    ("app.admin", "miles_admin"),
    ("app.common", "miles_common"),
    ("app.core", "miles_core"),
    ("app.exec", "miles_exec"),
    ("app.rag", "miles_ai.rag"),
    ("app.apps", "miles_server.apps"),
    ("app.main", "miles_server.main"),
    ("app.workers", "miles_worker"),
    ("app.utils", "miles_core.utils"),
]

_RULES = sorted(RULES, key=lambda r: len(r[0]), reverse=True)
_MAP = dict(_RULES)
_ALT = "|".join(re.escape(old) for old, _ in _RULES)
# 模块路径前缀：前一字符不是标识符/点，后一字符不是标识符（避免 app.tenantx / xapp.tenant）。
# 必须用 (?:...) 分组，否则 | 的优先级会让 (?<!...) 只作用于首个分支、(?!...) 只作用于末个分支。
_RE = re.compile(rf"(?<![\w.])(?:{_ALT})(?![\w])")

# 说明：
# 1) 规则按长度降序匹配，故 `app.workers.app` 先于 `app.workers` 命中，前者映射到
#    miles_worker.app（投递方），后者映射到 miles_worker（任务实现包）。
# 2) 同一 regex 同时作用于 import 语句与字符串字面量（patch 目标、celery 任务名、
#    include 列表），因此任务名会一致地变为 miles_worker.tasks.*。
#
# ⚠️ 事故记录（2026-09-11，合并后手动起 worker 时发现）：
#    第 2 条「顺手改掉字符串字面量」正是事故根源——任务名是**线级协议**，不是模块
#    路径。codemod 把 `app.workers.tasks.*` 一致改成 `miles_worker.tasks.*` 后，投递
#    方与注册方仍自洽（故全量 pytest 绿灯），但 broker 中在途消息全部
#    `KeyError: 'app.workers.tasks...'`。此后任务名已统一为与目录无关的
#    `milesai.tasks.*` 并由 tests/miles_worker/test_celery_task_names.py 冻结。
#    **本工具为一次性 codemod，已完成使命，勿再重跑**；如确需重跑，务必先把
#    `milesai.tasks.*` 与其它协议字符串加入白名单，勿让其进入 regex 射程。

# 本工具自身（backend/tools/）必须排除：RULES 里全是 app.* 字面量，否则会把自己改烂。
# 注意：只能排除 backend 顶层的 tools/，不能按目录名全局排除——业务目录里也有
# `tools/`（如 miles_portal/tenant/tools、tests/miles_portal/tenant/tools），那些必须改写。
SKIP_PARTS = {".venv", "__pycache__", "milesai.egg-info", ".ruff_cache", ".pytest_cache", "node_modules", "tools"}

# 真正对所有层级生效的忽略目录（不含 "tools"）。
_SKIP_ANY = SKIP_PARTS - {"tools"}


def rewrite(text: str) -> str:
    """改写文本中的 app.* 模块路径（含字符串字面量）。"""
    return _RE.sub(lambda m: _MAP[m.group(0)], text)


# `scripts` 是原 backend 根级包（无 app. 前缀），codemod 的 app.* 规则覆盖不到；
# 用「仅匹配 import 语句」的定向正则，避免误伤普通字符串里的 "scripts.xxx"。
_RE_SCRIPTS = re.compile(r"(?<![\w.])(from|import)([ \t]+)scripts(?=[.\s])")


def rewrite_scripts_imports(text: str) -> str:
    """把 ``from scripts.x import`` / ``import scripts`` 改为 ``miles_server.scripts.*``。"""
    return _RE_SCRIPTS.sub(lambda m: f"{m.group(1)}{m.group(2)}miles_server.scripts", text)


def iter_files() -> list[Path]:
    """待改写文件：backend 下全部 .py（含 tests/packages/alembic/tools-已排除）。"""
    out: list[Path] = []
    for p in sorted(BACKEND.rglob("*.py")):
        rel = p.relative_to(BACKEND)
        # 仅排除 backend 顶层的 tools/（本 codemod 工具自身）。
        if rel.parts and rel.parts[0] == "tools":
            continue
        if any(part in _SKIP_ANY for part in rel.parts):
            continue
        out.append(p)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    if not (args.apply or args.dry_run):
        ap.error("需要 --dry-run 或 --apply")

    changed = 0
    for path in iter_files():
        src = path.read_text(encoding="utf-8")
        new = rewrite_scripts_imports(rewrite(src))
        if new != src:
            changed += 1
            rel = path.relative_to(BACKEND)
            if args.apply:
                path.write_text(new, encoding="utf-8")
            print(f"{'改写' if args.apply else '将改写'} {rel}")
    print(f"\n共 {changed} 个文件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
