"""从自由文本中粗提取「负责人：事项」形待办行。"""

import re

_LINE = re.compile(
    r"(?P<owner>[^\s：:，,]{1,16})[：:]\s*(?P<task>.+?)(?:[，,]\s*(?:截止|ddl|by)\s*(?P<due>.+))?$",
    re.IGNORECASE,
)


def run(params):
    text = str(params.get("text") or "")
    items = []
    for line in text.splitlines():
        line = line.strip().lstrip("-*• ").strip()
        if not line:
            continue
        m = _LINE.search(line)
        if m:
            items.append(
                {
                    "owner": m.group("owner"),
                    "task": m.group("task").strip(),
                    "due": (m.group("due") or "").strip() or "TBD",
                }
            )
    return {"action_items": items, "count": len(items)}
