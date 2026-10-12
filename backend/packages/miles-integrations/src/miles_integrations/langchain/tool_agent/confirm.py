"""工具确认续接与正文模拟调用自救助。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from miles_core.models.agent.chat_io import ChatArtifact, ChatRequest, ChatResponse
from miles_integrations.langchain.tool_agent.artifacts import artifacts_from_tool_output
from miles_integrations.langchain.tool_agent.parse import (
    _GENERATIVE_INTENT_PHRASES,
    _extract_tool_params_from_text,
)
from miles_integrations.langchain.tool_agent.tool_contract import ToolExecutor

# 确认续接时合成的 tool_call id（供后续 assistant/tool 消息配对）
_CONFIRM_TOOL_CALL_ID = "pending_confirm_1"


def _pending_job_entry(job_id: object, kind: object) -> dict:
    """构造前端轮询用的 ``generative_jobs`` 条目（id / kind / status）。"""
    return {"id": job_id, "kind": kind, "status": "pending"}


@dataclass
class _ConfirmedToolSeed:
    """确认后续接：工具已执行，需注入 messages 后继续 LLM（可经 on_delta 真流）。"""

    slug: str
    params: dict
    output: Any
    artifacts: list[ChatArtifact] = field(default_factory=list)
    steps: list[dict] = field(default_factory=list)
    knowledge_hits: list[dict] = field(default_factory=list)


def _seed_confirmed_tool_messages(messages: list[dict], seed: _ConfirmedToolSeed) -> None:
    """把确认执行的工具结果写成 assistant tool_calls + tool，供下一轮 LLM 综合。"""
    args = json.dumps(seed.params, ensure_ascii=False)
    messages.append(
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": _CONFIRM_TOOL_CALL_ID,
                    "type": "function",
                    "function": {"name": seed.slug, "arguments": args},
                }
            ],
        }
    )
    if isinstance(seed.output, (dict, list)):
        content = json.dumps(seed.output, ensure_ascii=False)
    else:
        content = str(seed.output)
    messages.append(
        {
            "role": "tool",
            "tool_call_id": _CONFIRM_TOOL_CALL_ID,
            "content": content,
        }
    )


async def _resume_confirmed_tool(
    body: ChatRequest, tool_executor: ToolExecutor
) -> ChatResponse | _ConfirmedToolSeed | None:
    """处理「用户点击确认后」的续接请求。

    - 非续接 → ``None``
    - 执行失败 / 异步生成 pending → 终态 ``ChatResponse``（短答，无 LLM）
    - 同步成功 → ``_ConfirmedToolSeed``，由主循环注入 messages 后继续 LLM（``on_delta`` 真流）
    """
    if not (body.tool_confirmed and body.pending_tool_slug):
        return None

    slug = body.pending_tool_slug
    try:
        confirm_params = dict(body.pending_tool_params or {})
        if slug == "generate_image":
            from miles_integrations.generative.request_prefs import resolve_image_n

            confirm_params["n"] = resolve_image_n(confirm_params.get("n"))
        output = await tool_executor.invoke(slug, confirm_params, confirmed=True)
    except Exception as exc:
        return ChatResponse(
            answer=f"工具执行失败：{exc}",
            steps=[{"type": "tool_execute", "slug": slug, "status": "error", "error": str(exc)}],
        )

    confirm_artifacts = artifacts_from_tool_output(output) if isinstance(output, dict) else []
    if isinstance(output, dict) and output.get("status") == "pending" and output.get("generative_job_id"):
        job_kind = str(output.get("kind") or "image")
        confirm_message = str(output.get("message") or "")
        default_msg = (
            "图片生成任务已提交，完成后将自动展示预览。"
            if job_kind == "image"
            else "视频生成任务已提交，完成后将自动展示预览。"
        )
        return ChatResponse(
            answer=confirm_message or default_msg,
            steps=[
                {
                    "type": "tool_execute",
                    "slug": slug,
                    "status": "success",
                },
                {
                    "type": "generative_job",
                    "slug": slug,
                    "job_id": output.get("generative_job_id"),
                    "kind": job_kind,
                    "status": "pending",
                },
            ],
            artifacts=confirm_artifacts,
            generative_jobs=[_pending_job_entry(output.get("generative_job_id", ""), job_kind)],
        )

    knowledge_hits: list[dict] = []
    if slug == "knowledge_search" and isinstance(output, dict) and isinstance(output.get("hits"), list):
        knowledge_hits.extend(output["hits"])

    return _ConfirmedToolSeed(
        slug=slug,
        params=confirm_params,
        output=output,
        artifacts=confirm_artifacts,
        steps=[{"type": "tool_execute", "slug": slug, "status": "success"}],
        knowledge_hits=knowledge_hits,
    )

async def _recover_from_tool_simulation(
    content: str,
    *,
    tool_names: list[str],
    tools_by_name: dict,
    tool_executor: ToolExecutor,
    messages: list[dict],
    steps: list[dict],
    body: ChatRequest,
) -> ChatResponse | None:
    """LLM 在正文里「模拟」了工具调用（而非真正发起 tool_call）时的自救助。

    返回非 ``None`` 表示应终止并回复该响应；返回 ``None`` 表示已向 ``messages``
    追加纠正提示，调用方应进入下一轮重试。
    """
    extracted = _extract_tool_params_from_text(content, tools_by_name)
    if extracted:
        slug, params = extracted
        try:
            meta = await tool_executor.meta(slug)
        except Exception:
            meta = None
        if meta and not meta.get("require_confirmation"):
            try:
                output = await tool_executor.invoke(slug, params, confirmed=True)
            except Exception as exc:
                steps.append({"type": "tool_simulation_corrected", "message": f"提取 JSON 参数后执行 {slug} 失败: {exc}，追加纠正提示"})
                messages.append({"role": "assistant", "content": content})
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "你刚才输出的 JSON 无法被系统正确解析执行。"
                            "请直接通过 function calling 机制（tool_use）调用工具，"
                            "而不是在文字中输出 JSON 参数。"
                            "如需生图，请发起真正的 tool_call。"
                        ),
                    }
                )
                return None
            exec_artifacts = artifacts_from_tool_output(output) if isinstance(output, dict) else []
            exec_jobs: list[dict] = []
            exec_message = str(output.get("message") if isinstance(output, dict) else output) or f"已执行工具 {slug}"
            if isinstance(output, dict) and output.get("status") == "pending":
                exec_jobs.append(_pending_job_entry(output.get("generative_job_id", ""), output.get("kind", "image")))
            steps.append({"type": "tool_simulation_extracted", "slug": slug, "message": "从 LLM 文本输出中提取 JSON 参数并直接执行了工具"})
            return ChatResponse(
                answer=exec_message,
                steps=steps,
                artifacts=exec_artifacts,
                generative_jobs=exec_jobs,
            )

    # 提取失败：判断是否为「表达了生成意图但没给 JSON」的兜底场景
    is_intent_only = any(phrase in content for phrase in _GENERATIVE_INTENT_PHRASES)
    image_tool = next((name for name in tool_names if "image" in name and "video" not in name), None)
    if is_intent_only and image_tool is not None:
        # LLM 表达了生图意图但没有 JSON → 用用户原始 query 作为 prompt 直接生图
        fallback_query = body.query.strip()
        if not fallback_query:
            steps.append({"type": "tool_simulation_no_query", "message": "LLM 表达了生成意图但无法提取参数，且用户 query 为空"})
            return ChatResponse(answer="请描述您想要生成的图片内容。", steps=steps)
        try:
            meta = await tool_executor.meta(image_tool)
        except Exception:
            meta = None
        if meta and not meta.get("require_confirmation"):
            try:
                output = await tool_executor.invoke(image_tool, {"prompt": fallback_query}, confirmed=True)
            except Exception as exc:
                steps.append({"type": "tool_simulation_corrected", "message": f"用原始 query 兜底执行 {image_tool} 失败: {exc}"})
                messages.append({"role": "assistant", "content": content})
                messages.append(
                    {
                        "role": "user",
                        "content": "请直接通过 function calling 调用 generate_image 工具。",
                    }
                )
                return None
            exec_artifacts = artifacts_from_tool_output(output) if isinstance(output, dict) else []
            exec_jobs: list[dict] = []
            exec_message = str(output.get("message") if isinstance(output, dict) else output) or "已开始生成图片"
            if isinstance(output, dict) and output.get("status") == "pending":
                exec_jobs.append(_pending_job_entry(output.get("generative_job_id", ""), output.get("kind", "image")))
            steps.append(
                {
                    "type": "tool_simulation_intent_fallback",
                    "slug": image_tool,
                    "message": "LLM 表达了生成意图但无 JSON，用原始 query 作为 prompt 兜底执行",
                    "fallback_query_preview": fallback_query[:200],
                }
            )
            return ChatResponse(
                answer=exec_message,
                steps=steps,
                artifacts=exec_artifacts,
                generative_jobs=exec_jobs,
            )

    # 其他提取失败：回退到纠正提示重试
    steps.append({"type": "tool_simulation_corrected", "message": "LLM 在文字中模拟了工具调用，已追加纠正提示"})
    messages.append({"role": "assistant", "content": content})
    messages.append(
        {
            "role": "user",
            "content": (
                "你刚才在文字中描述了工具调用，但并未真正发起 function call。"
                "请直接通过 tool_use 机制调用工具，不要用文字描述调用过程。"
                "如需生图，立即调用 generate_image 工具并传入参数。"
            ),
        }
    )
    return None
