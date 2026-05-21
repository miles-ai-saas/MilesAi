import json
from pathlib import Path


def load_rag_graph_template() -> dict:
    path = Path(__file__).resolve().parents[2] / "flow_runtime" / "templates" / "rag_flow.json"
    return json.loads(path.read_text(encoding="utf-8"))
