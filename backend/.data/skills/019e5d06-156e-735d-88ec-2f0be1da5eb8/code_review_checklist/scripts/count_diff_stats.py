"""统计 diff 文本行数（增/删粗算）。"""


def run(params):
    diff = str(params.get("diff") or "")
    added = deleted = 0
    for line in diff.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            added += 1
        elif line.startswith("-"):
            deleted += 1
    return {"added_lines": added, "deleted_lines": deleted, "total": added + deleted}
