/**
 * 会话加载时校正仍显示 pending/running 的生图卡片：
 * 任务实际已成功时，本地若未写回会一直显示「排队中」。
 */

import { api } from "@/lib/api";
import { effectiveArtifactStatus, generativeJobToArtifacts } from "@/lib/generative-jobs";
import {
  replaceJobArtifactsInSession,
  type ChatMessage,
  type ChatMessageArtifact,
} from "@/features/agents/lib/chat-sessions";

function collectInFlightJobIds(messages: ChatMessage[]): string[] {
  const ids: string[] = [];
  const seen = new Set<string>();
  for (const m of messages) {
    for (const a of m.artifacts ?? []) {
      if (!a.job_id || seen.has(a.job_id)) continue;
      const status = effectiveArtifactStatus(a);
      if (status === "pending" || status === "running") {
        seen.add(a.job_id);
        ids.push(a.job_id);
      }
    }
  }
  return ids;
}

function applyJobToUiMessages(messages: ChatMessage[], jobId: string, nextArts: ChatMessageArtifact[]): ChatMessage[] {
  let touched = false;
  const next = messages.map((m) => {
    if (!m.artifacts?.some((a) => a.job_id === jobId)) return m;
    touched = true;
    return {
      ...m,
      artifacts: [...m.artifacts.filter((a) => a.job_id !== jobId), ...nextArts],
    };
  });
  return touched ? next : messages;
}

/** 查询进行中 job 的真实状态并写回本地 + 返回校正后的 UI 消息。 */
export async function reconcileInFlightGenerativeArtifacts(
  agentId: string,
  sessionId: string,
  uiMessages: ChatMessage[],
): Promise<ChatMessage[]> {
  const jobIds = collectInFlightJobIds(uiMessages);
  if (!jobIds.length) return uiMessages;

  let nextUi = uiMessages;
  for (const jobId of jobIds.slice(0, 12)) {
    try {
      const job = await api.getGenerativeJob(jobId);
      if (job.status === "pending" || job.status === "running") continue;
      const nextArts = generativeJobToArtifacts(job) as ChatMessageArtifact[];
      if (!nextArts.length) continue;
      replaceJobArtifactsInSession(agentId, sessionId, jobId, nextArts);
      nextUi = applyJobToUiMessages(nextUi, jobId, nextArts);
    } catch {
      /* 离线或 job 已删：保留本地展示 */
    }
  }

  return nextUi;
}
