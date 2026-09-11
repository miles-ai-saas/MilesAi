"""HTTP 工具 URL/headers 模板替换。"""


def apply_template(template: str, params: dict) -> str:
    """将 ``{{key}}`` 占位符替换为 params；未提供的占位符保持原样。"""
    out = template
    for k, v in params.items():
        out = out.replace(f"{{{{{k}}}}}", str(v))
    return out
