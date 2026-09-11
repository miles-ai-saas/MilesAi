"""内置 web_search 工具：DuckDuckGo Instant Answer API。

免 API Key，适合企业内部知识/百科查询场景。
返回三部分：摘要（Abstract）、相关主题（RelatedTopics）、信息框（Infobox）。
"""

import httpx
from miles_core.url_security import validate_outbound_url

_DDG_API = "https://api.duckduckgo.com/"


def search(query: str, max_results: int = 5) -> dict:
    """调用 DuckDuckGo Instant Answer API，返回摘要与相关主题。"""
    validate_outbound_url(_DDG_API)
    try:
        resp = httpx.get(
            _DDG_API,
            params={"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"},
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        return {"error": f"搜索请求失败: {exc}", "results": []}

    results: list[dict] = []

    abstract = (data.get("AbstractText") or "").strip()
    if abstract:
        source = data.get("AbstractURL") or ""
        results.append({"title": data.get("Heading") or query, "snippet": abstract, "url": source})

    for topic in data.get("RelatedTopics", []):
        if len(results) >= max_results:
            break
        text = (topic.get("Text") or "").strip()
        url = topic.get("FirstURL") or ""
        if text:
            results.append({"title": "", "snippet": text, "url": url})

    infobox = data.get("Infobox", {})
    if infobox and len(results) < max_results:
        content_parts = []
        for item in infobox.get("content", []):
            label = item.get("label", "")
            value = item.get("value", "")
            if label and value:
                content_parts.append(f"{label}: {value}")
        if content_parts:
            results.append(
                {
                    "title": infobox.get("meta", {}).get("value", ""),
                    "snippet": "; ".join(content_parts),
                    "url": "",
                }
            )

    return {"results": results[:max_results]}
