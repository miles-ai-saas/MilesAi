import type { ChatAgentResult, ChatArtifact } from "@/lib/types";
import type { ChatMessage } from "@/features/agents/lib/chat-sessions";
import { extractPendingGenerativeJobs } from "@/lib/generative-jobs";

export type GenerativePollJob = { jobId: string; kind: string };

export function mergeArtifactsIntoLastAssistant(prev: ChatMessage[], artifacts: ChatArtifact[]): ChatMessage[] {
  if (!artifacts.length || !prev.length) return prev;
  const lastIdx = prev.length - 1;
  if (prev[lastIdx].role !== "assistant") return prev;
  const merged = [...(prev[lastIdx].artifacts ?? [])];
  for (const a of artifacts) {
    if (!merged.some((m) => m.attachment_id === a.attachment_id)) {
      merged.push({
        kind: a.kind,
        attachment_id: a.attachment_id,
        mime_type: a.mime_type ?? undefined,
      });
    }
  }
  const next = [...prev];
  next[lastIdx] = { ...prev[lastIdx], artifacts: merged };
  return next;
}

export function collectPendingGenerativeJobs(res: ChatAgentResult): GenerativePollJob[] {
  return [
    ...extractPendingGenerativeJobs(res.steps).map((j) => ({
      jobId: j.jobId,
      kind: j.kind,
    })),
    ...(res.generative_jobs ?? []).filter((j) => j.status === "pending").map((j) => ({ jobId: j.id, kind: j.kind })),
  ];
}

export function collectPendingGenerativeJobIds(res: ChatAgentResult): string[] {
  return [
    ...extractPendingGenerativeJobs(res.steps).map((j) => j.jobId),
    ...(res.generative_jobs ?? []).filter((j) => j.status === "pending").map((j) => j.id),
  ];
}

export function mapResponseArtifacts(res: ChatAgentResult) {
  return res.artifacts?.map((a) => ({
    kind: a.kind,
    attachment_id: a.attachment_id,
    mime_type: a.mime_type,
  }));
}
