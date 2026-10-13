"""按计划依次调用外部 A2A Peer。"""

from __future__ import annotations

from miles_portal.tenant.a2a.client import invoke_a2a_peer
from miles_portal.tenant.a2a.models import A2aPeerBinding, A2aPlanTrigger, AgentA2aPeerRef


async def execute_a2a_calls(
    refs: list[AgentA2aPeerRef] | list[A2aPeerBinding],
    plan_items: list[dict],
    *,
    steps: list[dict],
) -> list[str]:
    """
    按 plan 依次 ``invoke_a2a_peer``，收集外部回答文本块。

    失败项记入 ``steps``（``a2a_error``），不中断后续 peer；供 ``augment_response_with_a2a`` 综合。
    """
    blocks: list[str] = []
    ref_by_peer = {str(r.peer_id): r for r in refs if r.peer}

    for item in plan_items:
        pid = str(item.get("peer_id", ""))
        ref = ref_by_peer.get(pid)
        if not ref or not ref.peer:
            steps.append({"type": "a2a_skip", "reason": "非法 peer_id", "peer_id": pid})
            continue
        task = str(item.get("task", ""))
        try:
            answer = await invoke_a2a_peer(ref.peer, task)
            name = ref.peer.card_display_name or ref.peer.name
            steps.append(
                {
                    "type": "a2a_peer",
                    "peer_id": pid,
                    "peer_name": name,
                    "role_hint": ref.role_hint,
                    "trigger": item.get("trigger", A2aPlanTrigger.PLAN.value),
                    "task": task[:300],
                    "output_preview": answer[:500],
                }
            )
            blocks.append(f"【外部 A2A · {name}】\n{answer}")
        except Exception as exc:
            steps.append(
                {
                    "type": "a2a_error",
                    "peer_id": pid,
                    "peer_name": ref.peer.name,
                    "error": str(exc)[:300],
                }
            )
    return blocks
