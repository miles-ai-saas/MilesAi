#!/usr/bin/env python3
"""检查迁移是否真正落库：表数量 + alembic_version。"""
import asyncio
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings

REQUIRED_TABLES = {
    "alembic_version",
    "sys_tenants",
    "sys_users",
    "sys_roles",
    "sys_permissions",
    "kb_bases",
    "kb_documents",
    "agt_agents",
    "flow_flows",
    "aud_logs",
}


async def main() -> int:
    settings = get_settings()
    print(f"连接: {settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}")
    print(f"用户: {settings.postgres_user}")

    engine = create_async_engine(settings.database_url)
    async with engine.connect() as conn:
        tables = (
            await conn.execute(
                text(
                    "SELECT tablename FROM pg_tables "
                    "WHERE schemaname = 'public' ORDER BY tablename"
                )
            )
        ).scalars().all()
        version = (
            await conn.execute(text("SELECT version_num FROM alembic_version"))
        ).scalar_one_or_none()

    await engine.dispose()

    print(f"\nalembic_version: {version or '(无)'}")
    print(f"业务表数量: {len(tables)}")
    missing = REQUIRED_TABLES - set(tables)
    if missing:
        print(f"缺少核心表: {sorted(missing)}")
        print("\n建议执行:")
        print("  python cli.py init-db")
        return 1

    print("核心表齐全，迁移已生效。")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
