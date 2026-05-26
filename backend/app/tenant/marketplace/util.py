"""
市场打包用内置 RAG 流程模板加载。

``load_rag_graph_template`` 读取 ``flow_runtime/templates/rag_flow.json``；
结构说明见同目录 ``templates/README.md``。
"""

import json
from pathlib import Path


def load_rag_graph_template(*, variant: str = "default") -> dict:
    """
    读取内置 RAG 画布模板。

    ``variant``: ``default`` → ``rag_flow.json``；``with_grade`` → ``rag_flow_with_grade.json``。
    """
    name = "rag_flow_with_grade.json" if variant == "with_grade" else "rag_flow.json"
    path = Path(__file__).resolve().parents[2] / "flow_runtime" / "templates" / name
    return json.loads(path.read_text(encoding="utf-8"))
