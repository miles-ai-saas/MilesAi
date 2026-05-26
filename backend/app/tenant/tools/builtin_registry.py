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
    {
        "slug": "skill_read_reference",
        "name": "读取技能参考",
        "description": "读取绑定技能包 references/ 或 assets/ 下的文本文件（按需加载，非默认注入）",
        "category_slug": "general",
        "version": "1.0.0",
        "require_confirmation": False,
        "skill_bound_only": True,
        "parameters": [
            {"name": "path", "type": "string", "description": "相对技能根的路径", "required": True},
            {"name": "max_chars", "type": "integer", "required": False, "default": 12000},
        ],
    },
    {
        "slug": "skill_run_script",
        "name": "执行技能脚本",
        "description": "在沙箱中执行绑定技能包 scripts/ 下的 Python 脚本（须定义 run(params)）",
        "category_slug": "general",
        "version": "1.0.0",
        "require_confirmation": True,
        "skill_bound_only": True,
        "parameters": [
            {"name": "path", "type": "string", "description": "scripts/ 下脚本路径", "required": True},
            {"name": "params", "type": "object", "description": "传入 run(params) 的参数字典", "required": False},
            {"name": "timeout_sec", "type": "integer", "required": False, "default": 30},
            {"name": "max_memory_mb", "type": "integer", "required": False, "default": 512},
        ],
    },
]

BUILTIN_SLUGS = {t["slug"] for t in BUILTIN_REGISTRY}
SKILL_BOUND_SLUGS = {t["slug"] for t in BUILTIN_REGISTRY if t.get("skill_bound_only")}


def get_builtin(slug: str) -> dict | None:
    for t in BUILTIN_REGISTRY:
        if t["slug"] == slug:
            return t
    return None
