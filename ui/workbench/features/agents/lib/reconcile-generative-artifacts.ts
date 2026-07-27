/**
 * 会话加载时校正仍显示 pending/running 的生图卡片：
 * 任务实际已成功时，本地若未写回会一直显示「排队中」。
 */

import { api } from "@/lib/api";
import { generativeJobToArtifacts } from "@/lib/generative-jobs";
import { effectiveArtifactStatus } from "@/lib/generative-jobs";
import {
  getSession,
  replaceJobArtifactsInSession,
  updateSession,
  type ChatMessage,
  type ChatMessageArtifact,
} from "@/features/agents/lib/chat-sessions";

const PENDING_SUBMIT_RE = /生图任务已提交|生视频任务已提交|完成后将自动展示/;

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

function patchMessagesForJob(
  messages: ChatMessage[],
  jobId: string,
  nextArts: ChatMessageArtifact[],
): ChatMessage[] {
  let touched = false;
  const next = messages.map((m) => {
    if (!m.artifacts?.some((a) => a.job_id === jobId)) return m;
    touched = true;
    const succeeded = nextArts.some((a) => a.status === "success");
    const content =
      m.role === "assistant" && succeeded && PENDING_SUBMIT_RE.test(m.content) ? "生成完成" : m.content;
    return {
      ...m,
      content,
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
      nextUi = patchMessagesForJob(nextUi, jobId, nextArts);

      // 正文「已提交」占位一并写回 localStorage
      const stored = getSession(agentId, sessionId);
      if (stored) {
        const patchedStore = patchMessagesForJob(stored.messages, jobId, nextArts);
        if (patchedStore !== stored.messages) {
          updateSession(agentId, sessionId, { messages: patchedStore });
        }
      }
    } catch {
      /* 离线或 job 已删：保留本地展示 */
    }
  }

  return nextUi;
}
