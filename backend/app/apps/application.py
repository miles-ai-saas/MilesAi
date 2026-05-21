import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.admin.seeds.admin_seed import seed_admin_ops
from app.app_tenant.seeds.compliance_seed import seed_compliance
from app.app_tenant.seeds.marketplace_seed import seed_marketplace
from app.app_tenant.seeds.seed import seed_database
from app.apps.migrate import run_migrations
from app.apps.routers import admin_router, api_router
from app.common.handlers import register_exception_handlers
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.ai_stack.langgraph.checkpointer import init_langgraph_checkpointer, shutdown_langgraph_checkpointer

    run_migrations()
    async with AsyncSessionLocal() as session:
        await seed_database(session)
        await seed_compliance(session)
        await seed_marketplace(session)
        await seed_admin_ops(session)
        await session.commit()
    app.state.langgraph_checkpoint = await init_langgraph_checkpointer()
    yield
    await shutdown_langgraph_checkpointer()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

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

    register_exception_handlers(app)
    app.include_router(api_router)
    app.include_router(admin_router)
    return app
