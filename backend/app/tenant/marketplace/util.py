"""市场打包用内置 RAG 流程模板加载。"""

import json
from pathlib import Path


def load_rag_graph_template() -> dict:
    """读取 flow_runtime/templates/rag_flow.json 作为一键上架默认画布。"""
    path = Path(__file__).resolve().parents[2] / "flow_runtime" / "templates" / "rag_flow.json"
    return json.loads(path.read_text(encoding="utf-8"))
