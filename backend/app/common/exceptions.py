"""统一业务异常，避免路由层散落 HTTPException。"""


class AppError(Exception):
    """业务异常基类；handlers 映射为 JSON 与 HTTP status_code。"""

    def __init__(
        self,
        message: str,
        *,
        code: int | None = None,
        status_code: int = 400,
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.code = code if code is not None else status_code
        super().__init__(message)


class BadRequestError(AppError):
    """参数校验失败（HTTP 400）。"""

    def __init__(self, message: str = "请求参数错误") -> None:
        super().__init__(message, status_code=400)


class UnauthorizedError(AppError):
    """未认证或凭证失效（HTTP 401）。"""

    def __init__(self, message: str = "未授权") -> None:
        super().__init__(message, status_code=401)


class ForbiddenError(AppError):
    """已认证但无权限（HTTP 403）。"""

    def __init__(self, message: str = "无权访问") -> None:
        super().__init__(message, status_code=403)


class NotFoundError(AppError):
    """目标资源不存在（HTTP 404）。"""

    def __init__(self, message: str = "资源不存在") -> None:
        super().__init__(message, status_code=404)


class ConflictError(AppError):
    """资源冲突，如唯一约束被占用（HTTP 409）。"""

    def __init__(self, message: str = "资源冲突") -> None:
        super().__init__(message, status_code=409)
