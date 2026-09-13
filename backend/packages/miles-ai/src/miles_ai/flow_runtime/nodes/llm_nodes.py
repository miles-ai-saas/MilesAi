"""
画布 LLM 节点（``LLMCall``）。

典型上游：``PromptTemplate`` 输出已嵌入检索结果的 prompt。
``model_config_id`` 优先取节点配置，否则 ``RunContext.model_config_id``（Agent 对话注入）。

模型解析由运行入口注入的 ``RunContext.resolve_model`` 回调完成（见
``tenant.flows.services.run_context.make_flow_model_resolver``）；节点不再自行查询。
未配置模型或回调缺失时返回占位字符串 / 抛 ``BadRequestError``，便于调试与兜底。
支持 ``RunContext.media`` 附图（vision，base64 data URL）；附图字节经
``RunContext.media_reader``（L1 注入）读取。

媒体读取器守卫仅在本次运行确实携带附图时触发，因此无附件的匿名运行不再要求
``user_id``（有意放宽，原实现无条件构造租户上下文）。
"""

from typing import Any

from miles_ai.flow_runtime.context_utils import media_refs_from_run
from miles_ai.flow_runtime.types import RunContext
from miles_ai.integrations.chat.multimodal import build_user_message, resolve_media_refs
from miles_ai.integrations.langchain.chat_models import ainvoke_chat
from miles_common.exceptions import BadRequestError
from miles_common.schemas.media import MediaRefIn


async def llm_call(
    node_data: dict[str, Any],
    inputs: dict[str, Any],
    ctx: RunContext,
) -> str:
    """画布 LLMCall：经 ``ctx.resolve_model`` 解析模型后 ainvoke_chat（可选多模态 user content）。"""
    prompt = str(inputs.get("prompt") or inputs.get("input") or "").strip()
    include_run_media = node_data.get("include_run_media", True)
    media_refs: list[MediaRefIn] = []
    if include_run_media:
        media_refs = media_refs_from_run(ctx)

    if not prompt and not media_refs:
        raise BadRequestError("LLM 节点缺少输入")

    model_id = node_data.get("model_config_id") or ctx.model_config_id
    if not model_id:
        suffix = "\n\n[附图已忽略：未配置模型]" if media_refs else ""
        return f"[未配置模型，仅返回检索上下文]\n\n{prompt or '（无文本）'}{suffix}"

    if ctx.resolve_model is None:
        raise BadRequestError("运行上下文未提供模型解析回调")
    model = await ctx.resolve_model(str(model_id))

    temperature = float(node_data.get("temperature") or 0.7)
    max_tokens_raw = node_data.get("max_tokens")
    max_tokens = int(max_tokens_raw) if max_tokens_raw is not None else 2048

    max_media = int((ctx.agent_config or {}).get("max_media_per_turn", 10))
    media_parts: list[dict[str, Any]] = []
    if media_refs:
        if ctx.media_reader is None:
            raise BadRequestError("运行上下文未提供媒体读取器")
        media_parts = await resolve_media_refs(ctx.media_reader, media_refs, max_count=max_media)

    user_msg = build_user_message(
        query=prompt or "请根据附图回答。",
        media_parts=media_parts,
    )
    messages: list[dict[str, Any]] = []
    system = (ctx.system_prompt or "").strip()
    if system:
        messages.append({"role": "system", "content": system})
    messages.append(user_msg)

    usage_sink = ctx.usage_sink_factory(model) if ctx.usage_sink_factory is not None else None
    return await ainvoke_chat(
        model,
        messages,
        temperature=temperature,
        max_tokens=max_tokens,
        usage_sink=usage_sink,
    )
