"""钩子执行相关异常。"""

from app.common.exceptions import AppError


class HookBlockedError(AppError):
    """钩子返回 block，中止主链路。"""

    def __init__(self, message: str = "请求被钩子拦截", *, hook_name: str | None = None) -> None:
        self.hook_name = hook_name
        super().__init__(message, status_code=403, code=403)
