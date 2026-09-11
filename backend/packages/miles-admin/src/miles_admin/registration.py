"""运营后台 API 注册：路由与域内依赖。"""

from __future__ import annotations

from fastapi import FastAPI

from miles_admin.router import admin_router


def register_admin(app: FastAPI) -> None:
    """挂载运营端 API（/api/admin/v1）。"""
    app.include_router(admin_router)
