"""智能体 HTTP 路由单例；各子模块挂载 path 到本对象。"""

from fastapi import APIRouter

from miles_portal.tenant.agents.ws import agent_chat_ws_router

router = APIRouter()
router.include_router(agent_chat_ws_router)
