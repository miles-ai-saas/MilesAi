"""
画布 I/O 节点。

TextInput
---------
流程入口，从 ``RunContext.inputs`` 或节点 ``input_value`` 读取（常用 key ``query``）。

TextOutput
----------
取上游汇聚的第一个非空值作为 ``RunResult.output``；
典型链：TextInput → KnowledgeSearch → PromptTemplate → LLMCall → TextOutput。
"""

from typing import Any

from app.flow_runtime.types import RunContext


async def text_input(
    node_data: dict[str, Any],
    inputs: dict[str, Any],
    ctx: RunContext,
) -> str:
    """从 RunContext.inputs 或节点默认值读取入口文本。"""
    key = node_data.get("input_key") or "query"
    if key in ctx.inputs:
        return str(ctx.inputs[key])
    return str(node_data.get("input_value") or ctx.inputs.get("query", ""))


async def static_response(
    node_data: dict[str, Any],
    inputs: dict[str, Any],
    ctx: RunContext,
) -> str:
    """固定文案兜底（无命中 / 低分分支）。"""
    template = str(
        node_data.get("text")
        or "抱歉，未在知识库中找到与您问题相关的资料，请换个问法或联系管理员。"
    )
    query = str(inputs.get("query") or ctx.inputs.get("query", ""))
    return (
        template.replace("{{用户提问}}", query)
        .replace("{{query}}", query)
    )


async def text_output(
    node_data: dict[str, Any],
    inputs: dict[str, Any],
    ctx: RunContext,
) -> str:
    """取上游第一个非空输出作为流程终点。"""
    for v in inputs.values():
        if v is not None:
            return str(v)
    return ""
