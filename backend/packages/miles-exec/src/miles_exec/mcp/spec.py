"""RunSpec：Runner 唯一接受的运行指令。"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from miles_common.exceptions import BadRequestError

_SHELL_METACHAR_RE = re.compile(r"[;|&$`<>\n\r]")
_ENV_KEY_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")
_DEFAULT_COMMAND_WHITELIST = frozenset({"npx", "node", "python", "python3"})
#: 默认允许的 npx 包（官方 MCP 服务器）；``*`` 表示放行任意包。
_DEFAULT_NPX_PACKAGE_WHITELIST = frozenset(
    {
        "@modelcontextprotocol/server-filesystem",
        "@modelcontextprotocol/server-memory",
        "@modelcontextprotocol/server-everything",
        "@modelcontextprotocol/server-fetch",
        "@modelcontextprotocol/server-sequential-thinking",
    }
)
_SCOPED_PKG_RE = re.compile(r"^(@[^/]+/[^@]+)(?:@.+)?$")
_PLAIN_PKG_RE = re.compile(r"^([A-Za-z0-9._-]+)(?:@.+)?$")


# Runner 容器网络开关。
class NetworkMode(StrEnum):
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


def normalize_npx_package_name(raw: str) -> str:
    """去掉版本后缀，得到可比对的包名（``@scope/name`` 或 ``name``）。"""
    s = (raw or "").strip()
    if not s:
        return s
    if s.startswith("@"):
        m = _SCOPED_PKG_RE.match(s)
        return m.group(1) if m else s
    m = _PLAIN_PKG_RE.match(s)
    return m.group(1) if m else s


def extract_npx_packages(args: list[str]) -> list[str]:
    """从 ``npx`` args 提取包名（``-p/--package`` 或首个非 flag 位置参数）。"""
    out: list[str] = []
    skip_next = False
    for arg in args:
        if skip_next:
            name = normalize_npx_package_name(arg)
            if name:
                out.append(name)
            break
        if arg in ("-p", "--package"):
            skip_next = True
            continue
        if arg.startswith("-"):
            continue
        name = normalize_npx_package_name(arg)
        if name:
            out.append(name)
        break
    return out


def parse_npx_package_whitelist(raw: str | None) -> frozenset[str]:
    """解析逗号分隔白名单；空串回落默认官方包列表。"""
    if raw is None:
        return _DEFAULT_NPX_PACKAGE_WHITELIST
    items = {c.strip() for c in raw.split(",") if c.strip()}
    return frozenset(items) if items else _DEFAULT_NPX_PACKAGE_WHITELIST


def validate_run_spec(
    spec: RunSpec,
    *,
    command_whitelist: frozenset[str] | None = None,
    npx_package_whitelist: frozenset[str] | None = None,
) -> None:
    """校验 RunSpec；非法时抛 BadRequestError。

    ``npx`` 另校验包名白名单（供应链护栏）；白名单含 ``*`` 时放行任意包。
    """
    allowed = command_whitelist or _DEFAULT_COMMAND_WHITELIST
    cmd = (spec.command or "").strip()
    if cmd not in allowed:
        raise BadRequestError(f"命令不在白名单: {cmd}")
    if cmd == "npx":
        packages = extract_npx_packages(list(spec.args or []))
        if not packages:
            raise BadRequestError("npx 须指定 npm 包名")
        allowed_pkgs = npx_package_whitelist if npx_package_whitelist is not None else _DEFAULT_NPX_PACKAGE_WHITELIST
        if "*" not in allowed_pkgs:
            for pkg in packages:
                if pkg not in allowed_pkgs:
                    raise BadRequestError(f"npx 包不在白名单: {pkg}")
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
