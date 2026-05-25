"""内置工具注册表（不入库，由代码维护）。"""

BUILTIN_REGISTRY: list[dict] = [
    {
        "slug": "calculator",
        "name": "计算器",
        "description": "安全计算数学表达式",
        "category_slug": "general",
        "version": "1.0.0",
        "require_confirmation": False,
        "parameters": [
            {"name": "expression", "type": "string", "description": "数学表达式", "required": True},
        ],
    },
    {
        "slug": "http_request",
        "name": "HTTP 请求",
        "description": "发起 HTTP 请求",
        "category_slug": "integration",
        "version": "1.0.0",
        "require_confirmation": False,
        "parameters": [
            {"name": "url", "type": "string", "required": True},
            {"name": "method", "type": "string", "required": False, "default": "GET"},
        ],
    },
    {
        "slug": "knowledge_search",
        "name": "知识库检索",
        "description": "在指定知识库中语义检索",
        "category_slug": "data",
        "version": "1.0.0",
        "require_confirmation": False,
        "parameters": [
            {"name": "query", "type": "string", "required": True},
            {"name": "kb_id", "type": "string", "required": True},
            {"name": "limit", "type": "integer", "required": False, "default": 5},
        ],
    },
    {
        "slug": "get_current_datetime",
        "name": "获取当前时间",
        "description": "获取当前的日期时间",
        "category_slug": "general",
        "version": "1.0.0",
        "require_confirmation": False,
        "parameters": [
            {
                "name": "timezone",
                "type": "string",
                "description": "IANA 时区，默认 UTC",
                "required": False,
            },
        ],
    },
]

BUILTIN_SLUGS = {t["slug"] for t in BUILTIN_REGISTRY}


def get_builtin(slug: str) -> dict | None:
    for t in BUILTIN_REGISTRY:
        if t["slug"] == slug:
            return t
    return None
