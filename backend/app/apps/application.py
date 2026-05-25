"""FastAPI 应用工厂：CORS、链路追踪、路由挂载与启动期迁移 / LangGraph checkpoint。"""

import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.apps.migrate import run_migrations
from app.apps.routers import admin_router, api_router
from app.common.handlers import exception_handlers
from app.core.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.integrations.langgraph.checkpointer import init_langgraph_checkpointer, shutdown_langgraph_checkpointer

    # 启动时只做 schema 迁移；业务种子由 cli.py init-db 单独执行
    run_migrations()
    # 初始化 RAG / DeepAgents 共用 checkpointer（redis | memory），见 langgraph.checkpointer
    app.state.langgraph_checkpoint = await init_langgraph_checkpointer()
    yield
    await shutdown_langgraph_checkpointer()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        description=settings.APP_DESCRIPTION,
        openapi_url="/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        swagger_ui_oauth2_redirect_url="/docs/oauth2-redirect",
        exception_handlers=exception_handlers,
        debug=settings.DEBUG,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def add_trace_id(request: Request, call_next):
        trace_id = request.headers.get("X-Trace-Id", str(uuid.uuid4()))
        request.state.trace_id = trace_id
        response = await call_next(request)
        response.headers["X-Trace-Id"] = trace_id
        return response

    app.include_router(api_router)
    app.include_router(admin_router)
    return app
