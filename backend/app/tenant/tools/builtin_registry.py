"""
内置工具注册表（不入库，由代码维护）。

``generative_only``：仅当智能体 ``enable_generative_tools`` 时出现在工具列表；
``generate_video`` 默认 ``require_confirmation=False``（开启生视频即同意直接调用；可取消进行中任务）。
"""

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
        "description": "在已绑定知识库中语义检索（可传 kb_id 或 kb_ids；省略则用智能体绑定知识库）",
        "category_slug": "data",
        "version": "1.1.0",
        "require_confirmation": False,
        "parameters": [
            {"name": "query", "type": "string", "required": True},
            {"name": "kb_id", "type": "string", "required": False},
            {"name": "limit", "type": "integer", "required": False, "default": 5},
        ],
    },
    # P2: 语音合成（TTS）— DashScope CosyVoice，生成 WAV 附件
    {
        "slug": "generate_speech",
        "name": "语音合成",
        "description": "将文本转为语音（TTS），支持音色、语速调节",
        "category_slug": "general",
        "version": "1.0.0",
        "require_confirmation": False,
        "generative_only": True,
        "parameters": [
            {"name": "text", "type": "string", "description": "语音合成文本（最长 1000 字符）", "required": True},
            {"name": "voice", "type": "string", "required": False, "default": "longxiaochun"},
            {"name": "speech_rate", "type": "number", "required": False, "default": 1.0},
            {"name": "model_config_id", "type": "string", "description": "tts 模型配置 UUID，可选", "required": False},
        ],
    },
    {
        "slug": "generate_video",
        "name": "生视频",
        "description": "文生视频、图生视频或首尾帧生视频（万相/豆包）；通常需 1–5 分钟，调用后异步排队",
        "category_slug": "general",
        "version": "1.1.0",
        "require_confirmation": False,
        "generative_only": True,
        "parameters": [
            {"name": "prompt", "type": "string", "description": "视频描述", "required": True},
            {
                "name": "duration",
                "type": "integer",
                "description": "时长（秒），通常 5–10",
                "required": False,
                "default": 5,
            },
            {
                "name": "resolution",
                "type": "string",
                "description": "720P 或 1080P",
                "required": False,
                "default": "720P",
            },
            {
                "name": "image_attachment_id",
                "type": "string",
                "description": "首帧图片 attachment_id（图生视频 / 首尾帧）",
                "required": False,
            },
            {
                "name": "last_frame_attachment_id",
                "type": "string",
                "description": "尾帧图片 attachment_id（首尾帧生视频，须与首帧同传）",
                "required": False,
            },
            {
                "name": "model_config_id",
                "type": "string",
                "description": "video_gen 模型配置 UUID，可选",
                "required": False,
            },
        ],
    },
    {
        "slug": "generate_image",
        "name": "生图",
        "description": "根据文字描述生成图片；可选参考图实现图生图。n 为多张时表示多张独立单图（非组图拼贴）。默认 1 张，最多 4 张；≥3 张或高分辨率需用户确认。",
        "category_slug": "general",
        "version": "1.4.0",
        "require_confirmation": False,
        "generative_only": True,
        "parameters": [
            {
                "name": "prompt",
                "type": "string",
                "description": "单幅画面描述。n>1 时仍描述「一张独立成片」的内容；除非用户明确要求组图/宫格/拼接，禁止写四宫格、分镜拼贴。",
                "required": True,
            },
            {
                "name": "size",
                "type": "string",
                "description": "尺寸，如 1024x1024；图生图时豆包可用 adaptive",
                "required": False,
                "default": "1024x1024",
            },
            {
                "name": "image_attachment_id",
                "type": "string",
                "description": "参考图附件 UUID（图生图 / SeedEdit）",
                "required": False,
            },
            {
                "name": "n",
                "type": "integer",
                "description": "生成张数，默认 1。表示彼此独立的完整单图张数，不是一张里的格子数。1–4，≥3 需确认。",
                "required": False,
                "default": 1,
            },
            {
                "name": "model_config_id",
                "type": "string",
                "description": "image_gen 模型配置 UUID，可选",
                "required": False,
            },
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
    # P2: 网页搜索 — 免 API Key，DuckDuckGo Instant Answer
    {
        "slug": "web_search",
        "name": "网页搜索",
        "description": "使用 DuckDuckGo 搜索网页，返回摘要与相关链接",
        "category_slug": "data",
        "version": "1.0.0",
        "require_confirmation": False,
        "parameters": [
            {"name": "query", "type": "string", "description": "搜索关键词", "required": True},
            {"name": "max_results", "type": "integer", "required": False, "default": 5},
        ],
    },
    # P2: 代码执行 — Runner 隔离子进程，30s/256MB 限制
    {
        "slug": "code_execution",
        "name": "代码执行",
        "description": "在沙箱中执行 Python 代码片段（须符合安全校验）",
        "category_slug": "general",
        "version": "1.0.0",
        "require_confirmation": True,
        "parameters": [
            {"name": "code", "type": "string", "description": "Python 代码片段", "required": True},
            {"name": "timeout", "type": "integer", "required": False, "default": 30},
            {"name": "memory", "type": "integer", "required": False, "default": 256},
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
GENERATIVE_SLUGS = {t["slug"] for t in BUILTIN_REGISTRY if t.get("generative_only")}


def get_builtin(slug: str) -> dict | None:
    """按 slug 查找内置工具元数据（名称、参数 schema、确认策略等）。"""
    for t in BUILTIN_REGISTRY:
        if t["slug"] == slug:
            return t
    return None
