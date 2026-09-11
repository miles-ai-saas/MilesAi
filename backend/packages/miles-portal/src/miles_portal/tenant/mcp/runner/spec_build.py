"""RunSpec 的业务侧构造：MCP 服务配置 + 租户上下文 → RunSpec。

留在 portal 而非 exec：本函数依赖 McpService 与 TenantContext，属上层关注点；
exec 只保留运行器消费的 RunSpec 与校验。
"""

from typing import Literal

from miles_common.exceptions import BadRequestError
from miles_core.tenant import TenantContext
from miles_exec.mcp.spec import NetworkMode, RunSpec
from miles_portal.tenant.mcp.models import McpService


def build_run_spec(
    service: McpService,
    ctx: TenantContext,
    *,
    purpose: Literal["mcp_sync", "mcp_invoke", "script_exec"],
) -> RunSpec:
    """由 MCP 服务 ``connection_config`` 组装 RunSpec，超时夹取到 1..120 秒。"""
    cfg = service.connection_config or {}
    command = str(cfg.get("command") or "").strip()
    if not command:
        raise BadRequestError("STDIO 需填写启动命令 command")
    args_raw = cfg.get("args") or []
    if isinstance(args_raw, str):
        args = [a for a in args_raw.split("\n") if a.strip()]
    else:
        args = [str(a) for a in args_raw]
    timeout = int(cfg.get("timeout_sec") or 30)
    network_raw = str(cfg.get("network_mode") or "deny").lower()
    network_mode = NetworkMode.ALLOW if network_raw == "allow" else NetworkMode.DENY
    return RunSpec(
        tenant_id=service.tenant_id,
        service_id=service.id,
        actor_user_id=ctx.user_id,
        command=command,
        args=args,
        env={str(k): str(v) for k, v in (cfg.get("env") or {}).items()},
        max_runtime_sec=min(max(timeout, 1), 120),
        network_mode=network_mode,
        purpose=purpose,
    )
