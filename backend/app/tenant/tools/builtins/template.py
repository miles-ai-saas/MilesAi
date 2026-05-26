"""HTTP 工具 URL/headers 模板替换。"""


def apply_template(template: str, params: dict) -> str:
    out = template
    for k, v in params.items():
        out = out.replace(f"{{{{{k}}}}}", str(v))
    return out
