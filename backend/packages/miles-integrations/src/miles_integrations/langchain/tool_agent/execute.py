"""单次 tool_call 执行与生成类工具去重。"""

from __future__ import annotations

import json

from miles_common.exceptions import BadRequestError
from miles_core.models.agent.chat_io import ChatArtifact, ChatResponse, PendingToolCall
from miles_integrations.langchain.tool_agent.artifacts import artifacts_from_tool_output
from miles_integrations.langchain.tool_agent.confirm import _pending_job_entry
from miles_integrations.langchain.tool_agent.tool_contract import ToolConfirmationSignal, ToolExecutor

# 同轮内允许多次调用的生成类工具（其余工具按需重复调用是合法的）
_GENERATIVE_SLUGS = frozenset({"generate_image", "generate_video"})

def _dedupe_generative_tool_calls(tool_calls: list, messages: list[dict]) -> list:
    """同一轮内 ``generate_image`` / ``generate_video`` 只保留首次调用。

    避免 LLM 因多张参考图而发起多次 tool_call 导致生成数量翻倍；被合并的调用
    会回一条 tool 消息告知 LLM，否则它会持续重复调用。
    """
    deduplicated: list = []
    seen: set[str] = set()
    for tc in tool_calls:
        slug = tc.function.name
        if slug in _GENERATIVE_SLUGS:
            if slug in seen:
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": f"工具 {slug} 已执行，本次重复调用自动合并。",
                    }
                )
                continue
            seen.add(slug)
        deduplicated.append(tc)
    return deduplicated


async def _execute_tool_call(
    tc,
    *,
    tool_executor: ToolExecutor,
    messages: list[dict],
    steps: list[dict],
    artifacts: list[ChatArtifact],
    knowledge_hits: list[dict],
) -> ChatResponse | None:
    """执行单个 tool_call，并把 tool 结果回填 ``messages``。

    返回非 ``None`` 表示应立即结束对话并回复该响应；返回 ``None`` 表示继续
    执行同轮的其他 tool_call。工具元数据解析出非业务异常时按原样抛出。
    """
    slug = tc.function.name
    try:
        args = json.loads(tc.function.arguments or "{}")
    except json.JSONDecodeError:
        args = {}

    try:
        meta = await tool_executor.meta(slug)
    except BadRequestError as exc:
        steps.append({"type": "tool_call", "slug": slug, "status": "error", "error": str(exc)})
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tc.id,
                "content": f"工具不存在: {slug}",
            }
        )
        return ChatResponse(
            answer=(
                f"智能体尝试调用工具「{slug}」，但该工具未找到。\n\n"
                "可能原因：\n"
                "1. 工具 slug 配置有误\n"
                "2. 自定义工具已被删除或禁用\n"
                "3. 内置工具 slug 拼写错误\n\n"
                "请在智能体「能力」步骤中检查 tool_slugs 配置，并确认工具仍在「平台工具」中。"
            ),
            steps=steps,
            artifacts=artifacts,
        )
    except Exception:
        steps.append({"type": "tool_call", "slug": slug, "status": "error", "error": "工具元数据解析失败"})
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tc.id,
                "content": f"工具解析失败: {slug}",
            }
        )
        raise

    if meta["require_confirmation"]:
        try:
            await tool_executor.invoke(slug, args, confirmed=False)
        except ToolConfirmationSignal as exc:
            pending = PendingToolCall(
                slug=exc.slug,
                name=exc.tool_name,
                description=exc.tool_description,
                params=exc.params,
            )
            # 生图工具的确认描述已在 policy 中生成，直接展示
            description_text = ""
            if exc.tool_description and slug == "generate_image":
                description_text = f"\n\n{exc.tool_description}"
            return ChatResponse(
                answer=(
                    f"智能体请求调用工具「{exc.tool_name}」，需要您确认后才会执行。"
                    f"{description_text}\n\n"
                    f"参数：```json\n{json.dumps(exc.params, ensure_ascii=False, indent=2)}\n```\n\n"
                    "请在对话中点击「确认执行」继续。"
                ),
                steps=steps + [{"type": "tool_confirmation_required", "slug": slug}],
                pending_tool=pending,
            )

    try:
        output = await tool_executor.invoke(slug, args, confirmed=True)
    except ToolConfirmationSignal:
        raise
    except BadRequestError as exc:
        steps.append({"type": "tool_call", "slug": slug, "status": "error", "error": str(exc)})
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tc.id,
                "content": str(exc),
            }
        )
        if slug in _GENERATIVE_SLUGS:
            artifacts.append(
                ChatArtifact(
                    kind="image" if slug == "generate_image" else "video",
                    status="failed",
                    error_message=str(exc),
                    caption=str(exc),
                )
            )
        return ChatResponse(
            answer=f"工具「{slug}」执行失败：{exc}",
            steps=steps,
            artifacts=artifacts,
        )

    pending_job_id = output.get("generative_job_id") if isinstance(output, dict) and output.get("status") == "pending" else None
    if pending_job_id:
        job_kind = str(output.get("kind") or "video")
        steps.append(
            {
                "type": "generative_job",
                "slug": slug,
                "job_id": pending_job_id,
                "kind": output.get("kind") or "video",
                "status": "pending",
            }
        )
        default_msg = "图片生成任务已提交，完成后将自动展示预览。" if job_kind == "image" else "视频生成任务已提交，完成后将自动展示预览。"
        pending_out = dict(output) if isinstance(output, dict) else {}
        pending_out.setdefault("status", "pending")
        pending_out.setdefault("kind", job_kind)
        pending_out.setdefault("generative_job_id", pending_job_id)
        artifacts.extend(artifacts_from_tool_output(pending_out))
        return ChatResponse(
            answer=str(output.get("message") or default_msg),
            steps=steps,
            artifacts=artifacts,
            generative_jobs=[_pending_job_entry(pending_job_id, job_kind)],
        )

    artifacts.extend(artifacts_from_tool_output(output))
    if slug == "knowledge_search" and isinstance(output, dict) and isinstance(output.get("hits"), list):
        knowledge_hits.extend(output["hits"])
    steps.append({"type": "tool_call", "slug": slug, "status": "success"})
    messages.append(
        {
            "role": "tool",
            "tool_call_id": tc.id,
            "content": json.dumps(output, ensure_ascii=False),
        }
    )
    return None


def _assistant_tool_call_message(message, tool_calls: list) -> dict:
    """模型返回的 assistant 消息 → 续接多轮所需的 OpenAI ``tool_calls`` 结构。"""
    return {
        "role": "assistant",
        "content": message.content or "",
        "tool_calls": [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in tool_calls
        ],
    }
