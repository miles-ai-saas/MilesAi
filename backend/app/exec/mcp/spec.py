"""RunSpec：Runner 唯一接受的运行指令。"""

from __future__ import annotations

import re
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.common.exceptions import BadRequestError

_SHELL_METACHAR_RE = re.compile(r"[;|&$`<>\\n\r]")
_ENV_KEY_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")
_DEFAULT_COMMAND_WHITELIST = frozenset({"npx", "node", "python", "python3"})


# Runner 容器网络开关。
class NetworkMode(str, Enum):
    DENY = "deny"
    ALLOW = "allow"


# 一次 Runner 调用的完整指令（命令、资源上限、网络模式）。
class RunSpec(BaseModel):
    tenant_id: UUID
    service_id: UUID
    actor_user_id: UUID | None = None
    command: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    cwd: str | None = None
    max_runtime_sec: int = 30
    max_memory_mb: int = 512
    network_mode: NetworkMode = NetworkMode.DENY
    purpose: Literal["mcp_sync", "mcp_invoke", "script_exec"] = "mcp_sync"

    @field_validator("args")
    @classmethod
    def validate_args(cls, v: list[str]) -> list[str]:
        """校验 args 数量/长度，并拒绝 shell 元字符与 ``..`` 路径片段。"""
        if len(v) > 32:
            raise ValueError("args 数量不能超过 32")
        for i, arg in enumerate(v):
            if len(arg) > 512:
                raise ValueError(f"args[{i}] 过长")
            if _SHELL_METACHAR_RE.search(arg):
                raise ValueError(f"args[{i}] 含非法 shell 元字符")
            if ".." in arg and not arg.startswith("@"):
                raise ValueError(f"args[{i}] 含非法路径片段")
        return v


def validate_run_spec(spec: RunSpec, *, command_whitelist: frozenset[str] | None = None) -> None:
    """校验 RunSpec；非法时抛 BadRequestError。"""
    allowed = command_whitelist or _DEFAULT_COMMAND_WHITELIST
    cmd = (spec.command or "").strip()
    if cmd not in allowed:
        raise BadRequestError(f"命令不在白名单: {cmd}")
    if spec.max_runtime_sec < 1 or spec.max_runtime_sec > 120:
        raise BadRequestError("max_runtime_sec 须在 1..120")
    if spec.max_memory_mb < 128 or spec.max_memory_mb > 2048:
        raise BadRequestError("max_memory_mb 须在 128..2048")
    for k, v in spec.env.items():
        if not _ENV_KEY_RE.match(k):
            raise BadRequestError(f"环境变量键非法: {k}")
        if len(str(v)) > 4096:
            raise BadRequestError(f"环境变量 {k} 值过长")
    if spec.cwd is not None:
        raise BadRequestError("MVP 不支持自定义 cwd")
