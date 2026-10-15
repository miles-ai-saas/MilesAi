"""内置模型目录种子：退役项与 rerank 条目。"""

from miles_server.scripts.seed.model_catalog import BUILTIN_CATALOG


def _codes() -> set[str]:
    return {item["model_code"] for item in BUILTIN_CATALOG}


def test_catalog_excludes_retired_deepseek_compat():
    codes = _codes()
    assert "deepseek-reasoner" not in codes
    assert "deepseek-chat" not in codes
    assert "deepseek-v4-flash" not in codes
    assert "deepseek-flash" in codes
    assert "deepseek-v4-pro" in codes


def test_catalog_contains_latest_vendor_flagships():
    codes = _codes()
    assert "doubao-seed-evolving" in codes
    assert "doubao-seed-2-1-pro-260915" in codes
    assert "doubao-seedream-5-0-pro-260628" in codes
    assert "qwen3.8-max" in codes
    assert "qwen3.7-plus" in codes
    assert "wan2.7-image-pro" in codes
    assert "wan3.0-video" in codes


def test_catalog_contains_rerank_models():
    codes = _codes()
    assert "qwen3-rerank" in codes
    assert "gte-rerank-v2" in codes
