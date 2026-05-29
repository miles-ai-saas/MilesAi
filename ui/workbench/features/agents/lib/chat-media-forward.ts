/**
 * 识图多轮：未上传新图时沿用上一轮用户消息中的附图。
 */

import type { ChatMediaIn } from "@/lib/types";
import type { ChatMessage, ChatMessageMedia } from "./chat-sessions";

export function lastUserMessageMedia(messages: ChatMessage[]): ChatMessageMedia[] {
  for (let i = messages.length - 1; i >= 0; i--) {
    const m = messages[i];
    if (m.role === "user" && m.media?.length) {
      return m.media;
    }
  }
  return [];
}

export function resolveOutgoingChatMedia(
  pending: ChatMediaIn[],
  messages: ChatMessage[],
  carryForward: boolean,
): { payload: ChatMediaIn[]; carriedFromPrevious: boolean } {
  if (pending.length > 0) {
    return { payload: pending, carriedFromPrevious: false };
  }
  if (!carryForward) {
    return { payload: [], carriedFromPrevious: false };
  }
  const prev = lastUserMessageMedia(messages);
  if (!prev.length) {
    return { payload: [], carriedFromPrevious: false };
  }
  return {
    payload: prev.map((m) => ({ attachment_id: m.attachment_id })),
    carriedFromPrevious: true,
  };
}

export function agentCarryForwardMediaEnabled(config: Record<string, unknown> | undefined | null): boolean {
  if (!config) return true;
  return config.carry_forward_media !== false;
}
