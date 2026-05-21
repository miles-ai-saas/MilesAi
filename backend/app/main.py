"""ASGI 入口：uvicorn app.main:app"""

from app.apps.application import create_app

app = create_app()
