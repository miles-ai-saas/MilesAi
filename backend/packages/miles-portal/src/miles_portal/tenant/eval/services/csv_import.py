"""评测用例 CSV 解析与批量导入。

表头（大小写不敏感，顺序可变）：

``query``（必填）, ``name``, ``expected_mode``, ``expected_value``

``expected_mode`` ∈ ``exact`` / ``contains`` / ``contains_all`` / ``rubric`` / ``none``（空）。
``contains_all`` 的 ``expected_value`` 用 ``|`` 分隔多项。
"""

from __future__ import annotations

import csv
import io
from typing import Any

from miles_common.exceptions import BadRequestError

_ALLOWED_MODES = frozenset({"exact", "contains", "contains_all", "rubric", "none", ""})


def _norm_header(cell: str) -> str:
    return (cell or "").strip().lower().replace(" ", "_")


def build_expected(mode: str, value: str) -> dict | None:
    mode = (mode or "").strip().lower()
    value = (value or "").strip()
    if not mode or mode == "none":
        return None
    if mode == "contains_all":
        parts = [p.strip() for p in value.split("|") if p.strip()]
        return {"contains_all": parts} if parts else None
    if mode in ("exact", "contains", "rubric"):
        return {mode: value} if value else None
    raise BadRequestError(f"不支持的 expected_mode: {mode}")


def parse_eval_cases_csv(text: str, *, max_rows: int = 500) -> list[dict[str, Any]]:
    """解析 CSV 文本为用例草稿列表 ``{query,name,expected}``。"""
    raw = (text or "").strip()
    if not raw:
        raise BadRequestError("CSV 内容为空")
    # 去掉 UTF-8 BOM
    if raw.startswith("\ufeff"):
        raw = raw[1:]

    reader = csv.DictReader(io.StringIO(raw))
    if not reader.fieldnames:
        raise BadRequestError("CSV 缺少表头")

    field_map = {_norm_header(h): h for h in reader.fieldnames if h is not None}
    if "query" not in field_map:
        raise BadRequestError("CSV 表头须包含 query 列")

    rows: list[dict[str, Any]] = []
    for i, row in enumerate(reader, start=2):
        if len(rows) >= max_rows:
            raise BadRequestError(f"单次最多导入 {max_rows} 条")
        query = (row.get(field_map["query"]) or "").strip()
        if not query:
            continue
        name_key = field_map.get("name")
        mode_key = field_map.get("expected_mode") or field_map.get("mode")
        value_key = field_map.get("expected_value") or field_map.get("expected")
        # 简写：直接有 contains / exact / rubric 列
        expected: dict | None = None
        if mode_key or value_key:
            mode = (row.get(mode_key) or "contains").strip().lower() if mode_key else "contains"
            value = (row.get(value_key) or "").strip() if value_key else ""
            if mode not in _ALLOWED_MODES:
                raise BadRequestError(f"第 {i} 行 expected_mode 无效: {mode}")
            expected = build_expected(mode, value)
        else:
            for key in ("contains", "exact", "rubric"):
                col = field_map.get(key)
                if col and (row.get(col) or "").strip():
                    expected = {key: (row.get(col) or "").strip()}
                    break
            if expected is None and field_map.get("contains_all"):
                col = field_map["contains_all"]
                parts = [p.strip() for p in (row.get(col) or "").split("|") if p.strip()]
                if parts:
                    expected = {"contains_all": parts}

        name = (row.get(name_key) or "").strip() if name_key else ""
        rows.append(
            {
                "query": query,
                "name": name or None,
                "expected": expected,
            }
        )

    if not rows:
        raise BadRequestError("CSV 中没有有效的 query 行")
    return rows
