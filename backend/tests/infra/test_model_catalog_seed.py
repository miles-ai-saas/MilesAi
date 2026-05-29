"""内置模型目录种子：退役项与 rerank 条目。"""

from pathlib import Path


def test_catalog_excludes_retired_deepseek_compat():
    catalog_src = Path(__file__).resolve().parents[1] / "scripts" / "seed" / "model_catalog.py"
    text = catalog_src.read_text(encoding="utf-8")
    assert '"model_code": "deepseek-reasoner"' not in text
    assert '"model_code": "deepseek-chat"' not in text
    assert '"model_code": "deepseek-v4-flash"' in text


def test_catalog_contains_rerank_models():
    catalog_src = Path(__file__).resolve().parents[1] / "scripts" / "seed" / "model_catalog.py"
    text = catalog_src.read_text(encoding="utf-8")
    assert '"model_code": "qwen3-rerank"' in text
    assert '"model_code": "gte-rerank-v2"' in text
