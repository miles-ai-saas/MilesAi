"""Runner 独立配置：只读 MCP_RUNNER_*，避免沙箱依赖全局 core settings。"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class RunnerSettings(BaseSettings):
    """Runner 运行配置（环境变量优先；容器内由 compose 注入）。

    仅覆盖 runner 自身需要的 MCP_RUNNER_* 字段——不引入全局 Settings，
    否则 runner 镜像的依赖闭包会被 langchain / sqlalchemy / celery 等拖大。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    mcp_runner_token: str = ""
    mcp_runner_max_concurrent_per_tenant: int = 3
    mcp_runner_command_whitelist: str = "npx,node,python,python3"

    @property
    def mcp_runner_command_whitelist_set(self) -> frozenset[str]:
        """命令白名单集合（逗号分隔，忽略空白）。"""
        return frozenset(item.strip() for item in self.mcp_runner_command_whitelist.split(",") if item.strip())


@lru_cache
def get_runner_settings() -> RunnerSettings:
    """进程级缓存的 Runner 配置。"""
    return RunnerSettings()
