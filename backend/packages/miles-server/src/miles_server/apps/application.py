"""FastAPI 应用工厂：CORS、链路追踪、路由挂载与启动期迁移 / LangGraph checkpoint。"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from miles_admin.registration import register_admin
from miles_core.config import get_settings
from miles_core.logging import setup_logging
from miles_core.web.handlers import exception_handlers
from miles_core.web.middlewares import register_http_middlewares
from miles_openapi.registration import register_open
from miles_portal.registration import register_portal
from miles_server.apps.migrate import run_migrations


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期钩子：启动时初始化日志 / OTel、执行 schema 迁移并建 LangGraph checkpointer，关闭时逆序释放。"""
    from miles_ai.integrations.langgraph.checkpointer import (
        init_langgraph_checkpointer,
        shutdown_langgraph_checkpointer,
    )
    from miles_core.infra.otel import setup_otel, shutdown_otel

    setup_logging()
    setup_otel(get_settings(), app=app)
    # 启动时只做 schema 迁移；业务种子由 `milesai init-db` 单独执行
    run_migrations()
    # 初始化 RAG / DeepAgents 共用 checkpointer（redis | memory），见 langgraph.checkpointer
    app.state.langgraph_checkpoint = await init_langgraph_checkpointer()
    yield
    await shutdown_langgraph_checkpointer()
    shutdown_otel()


def create_app() -> FastAPI:
    """构造 FastAPI 应用：装配 CORS、HTTP 中间件、统一异常处理并挂载 open / portal / admin 路由。"""
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        description=settings.APP_DESCRIPTION,
        openapi_url="/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        swagger_ui_oauth2_redirect_url="/docs/oauth2-redirect",
        exception_handlers=exception_handlers,
        # 勿将 settings.debug 传给 FastAPI：True 时 Starlette 返回明文 traceback，
        # 会绕过 miles_core.web.handlers 的统一 {code, message, data, trace_id} 信封。
        debug=False,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r".*",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Trace-Id"],
    )
    register_http_middlewares(app)

    register_open(app)
    register_portal(app)
    register_admin(app)
    return app
