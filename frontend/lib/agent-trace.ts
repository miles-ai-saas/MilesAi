/**
 * 从 `chat-sessions` 消息列表提取可浏览的 Trace 轮次（链路 §5）。
 * 与右侧 `AgentTracePanel`、`agent-steps` 展示配合。
 */

import type { ChatMessage } from "@/lib/chat-sessions";

/** 单次助手回复对应的 Trace 记录（含触发它的用户问题）。 */
export type AgentTraceTurn = {
  turnIndex: number;
  messageIndex: number;
  userQuery: string;
  assistantPreview: string;
  steps: Record<string, unknown>[];
  traceId?: string;
};

export function listTraceTurns(messages: ChatMessage[]): AgentTraceTurn[] {
  const turns: AgentTraceTurn[] = [];
  for (let i = 0; i < messages.length; i += 1) {
    const msg = messages[i];
    if (msg.role !== "assistant") continue;

    let userQuery = "";
    for (let j = i - 1; j >= 0; j -= 1) {
      if (messages[j].role === "user") {
        userQuery = messages[j].content;
        break;
      }
    }

    turns.push({
      turnIndex: turns.length,
      messageIndex: i,
      userQuery,
      assistantPreview: msg.content.slice(0, 80) + (msg.content.length > 80 ? "…" : ""),
      steps: msg.steps ?? [],
      traceId: msg.traceId,
    });
  }
  return turns;
}

export function defaultTraceTurnIndex(turns: AgentTraceTurn[]): number {
  return turns.length > 0 ? turns.length - 1 : 0;
}

export async function copyText(text: string): Promise<boolean> {
  if (!text || typeof navigator === "undefined") return false;
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}
