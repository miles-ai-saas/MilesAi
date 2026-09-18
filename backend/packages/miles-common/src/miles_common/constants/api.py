"""平台对外 API 契约中的共享常量。"""

#: 智能体开放调用（``/api/v1/open/*``）的 API Key 请求头名。
#:
#: 单一判据：FastAPI 依赖读取（``deps_api_auth``）、A2A 出站携带（``a2a.client``）、
#: 对外 Agent Card 的 ``securitySchemes`` 声明（``a2a.server``）都引用它 —— 三处各自
#: 硬编码会让「Card 声明的鉴权头」与「实际鉴权头」静默漂移。
AGENT_API_KEY_HEADER = "X-API-Key"
