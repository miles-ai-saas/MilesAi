"use client";

import { useCallback, useMemo, useState, type Dispatch, type SetStateAction } from "react";
import type { ChatMessage, ChatMessageArtifact } from "@/features/agents/lib/chat-sessions";
import { replaceJobArtifactsInSession } from "@/features/agents/lib/chat-sessions";
import { useGenerativeJobPoll } from "@/hooks/use-generative-job-poll";
import {
  generativeJobToArtifacts,
  extractPendingGenerativeJobs,
  replaceArtifactsForJob,
  patchArtifactsForJobProgress,
} from "@/lib/generative-jobs";
import type { ChatAgentResult, ChatArtifact, GenerativeJobOut } from "@/lib/types";

export type GenerativePollJob = { jobId: string; kind: string };

function applyToLastAssistant(
  prev: ChatMessage[],
  updater: (arts: ChatMessageArtifact[]) => ChatMessageArtifact[],
): ChatMessage[] {
  if (!prev.length) return prev;
  const lastIdx = prev.length - 1;
  if (prev[lastIdx].role !== "assistant") return prev;
  const next = [...prev];
  next[lastIdx] = {
    ...prev[lastIdx],
    artifacts: updater([...(prev[lastIdx].artifacts ?? [])]),
  };
  return next;
}

/** 兼容旧逻辑：按 attachment 去重 append；有 job_id 时用替换 */
export function mergeArtifactsIntoLastAssistant(prev: ChatMessage[], artifacts: ChatArtifact[]): ChatMessage[] {
  if (!artifacts.length || !prev.length) return prev;
  return applyToLastAssistant(prev, (merged) => {
    let arts = merged;
    const byJob = new Map<string, ChatArtifact[]>();
    const plain: ChatArtifact[] = [];
    for (const a of artifacts) {
      if (a.job_id) {
        const list = byJob.get(a.job_id) ?? [];
        list.push(a);
        byJob.set(a.job_id, list);
      } else {
        plain.push(a);
      }
    }
    for (const [jobId, list] of byJob) {
      arts = replaceArtifactsForJob(arts, jobId, list);
    }
    for (const a of plain) {
      if (a.attachment_id && arts.some((m) => m.attachment_id === a.attachment_id)) continue;
      arts = [...arts, a];
    }
    return arts;
  });
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

export function mapResponseArtifacts(res: ChatAgentResult): ChatMessageArtifact[] | undefined {
  return res.artifacts?.map((a) => ({
    kind: a.kind,
    attachment_id: a.attachment_id,
    mime_type: a.mime_type,
    caption: a.caption,
    status: a.status,
    job_id: a.job_id,
    media_asset_id: a.media_asset_id,
    progress_percent: a.progress_percent,
    progress_message: a.progress_message,
    error_message: a.error_message,
  }));
}

type Params = {
  setMessages: Dispatch<SetStateAction<ChatMessage[]>>;
  wsClientRef: React.MutableRefObject<{ connected?: boolean; cancelGenerativeJob: (id: string) => void } | null>;
  selectedAgent: string;
  conversationId: string;
};

function ChatGenerativeStatusBanner({
  message,
  progressPercent,
  canCancel,
  onCancel,
}: {
  message: string;
  progressPercent?: number | null;
  canCancel?: boolean;
  onCancel?: () => void;
}) {
  return (
    <div className="rounded-lg border border-amber-200/80 bg-amber-50/90 px-3 py-2 text-xs text-amber-900">
      <div className="flex items-center justify-between gap-2">
        <span>{message}</span>
        {canCancel && onCancel ? (
          <button type="button" className="btn-sm-ghost shrink-0 text-xs text-amber-900" onClick={onCancel}>
            取消
          </button>
        ) : null}
      </div>
      {progressPercent != null ? (
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-amber-200/60">
          <div className="h-full rounded-full bg-amber-600 transition-all duration-300" style={{ width: `${progressPercent}%` }} />
        </div>
      ) : null}
    </div>
  );
}

export function useAgentsChatGenerativeStatus({ setMessages, wsClientRef, selectedAgent, conversationId }: Params) {
  const [pollJobs, setPollJobs] = useState<GenerativePollJob[]>([]);
  const [wsGenerativeMsg, setWsGenerativeMsg] = useState<string | null>(null);
  const [wsGenerativeProgress, setWsGenerativeProgress] = useState<number | null>(null);
  const [wsActiveJobIds, setWsActiveJobIds] = useState<string[]>([]);

  const persistJobArts = useCallback(
    (jobId: string, arts: ChatMessageArtifact[]) => {
      if (!selectedAgent || !conversationId || !arts.length) return;
      replaceJobArtifactsInSession(selectedAgent, conversationId, jobId, arts);
    },
    [conversationId, selectedAgent],
  );

  const applyJobToMessages = useCallback(
    (job: GenerativeJobOut) => {
      const nextArts = generativeJobToArtifacts(job);
      if (!nextArts.length) return;
      setMessages((prev) => applyToLastAssistant(prev, (arts) => replaceArtifactsForJob(arts, job.id, nextArts)));
      persistJobArts(job.id, nextArts);
    },
    [persistJobArts, setMessages],
  );

  const {
    statusMsg: generativePollMsg,
    progressPercent: generativeProgress,
    cancelJob: cancelGenerativeJob,
    canCancel: canCancelGenerative,
  } = useGenerativeJobPoll(pollJobs, (artifacts) => {
    setMessages((prev) => mergeArtifactsIntoLastAssistant(prev, artifacts));
    const byJob = new Map<string, typeof artifacts>();
    for (const a of artifacts) {
      if (!a.job_id) continue;
      const list = byJob.get(a.job_id) ?? [];
      list.push(a);
      byJob.set(a.job_id, list);
    }
    for (const [jobId, list] of byJob) {
      if (!selectedAgent || !conversationId) continue;
      replaceJobArtifactsInSession(selectedAgent, conversationId, jobId, list);
    }
    setPollJobs([]);
  });

  const handleWsGenerativeJob = useCallback(
    (job: GenerativeJobOut, phase: "queued" | "progress" | "done") => {
      setWsActiveJobIds((prev) => (prev.includes(job.id) ? prev : [...prev, job.id]));
      if (job.progress_percent != null) setWsGenerativeProgress(job.progress_percent);
      const label = job.progress_message || "生成中…";
      setWsGenerativeMsg(job.progress_percent != null ? `${label}（${job.progress_percent}%）` : label);

      if (phase === "queued" || phase === "progress") {
        setMessages((prev) =>
          applyToLastAssistant(prev, (arts) =>
            patchArtifactsForJobProgress(arts, job.id, {
              kind: job.kind === "image" ? "image" : "video",
              status: job.status === "pending" ? "pending" : "running",
              progress_percent: job.progress_percent,
              progress_message: job.progress_message,
            }),
          ),
        );
      }

      if (phase === "done") {
        setWsActiveJobIds((prev) => prev.filter((id) => id !== job.id));
        applyJobToMessages(job);
        if (job.status === "success") {
          setWsGenerativeMsg(null);
          setWsGenerativeProgress(null);
        } else if (job.status === "failed") {
          setWsGenerativeMsg(job.error_message ?? "生成失败");
        } else if (job.status === "cancelled") {
          setWsGenerativeMsg("任务已取消");
        }
      }
    },
    [applyJobToMessages, setMessages],
  );

  const applyResponseGenerativeJobs = useCallback((res: ChatAgentResult, useWsJobs: boolean) => {
    const pendingJobs = collectPendingGenerativeJobs(res);
    if (!useWsJobs) {
      setPollJobs(pendingJobs);
      return;
    }
    setPollJobs([]);
    const pendingIds = collectPendingGenerativeJobIds(res);
    setWsActiveJobIds(pendingIds);
    if (pendingIds.length) {
      setWsGenerativeMsg(`正在生成（${pendingIds.length} 个任务）…`);
    }
  }, []);

  /** 响应 artifacts + 缺失 job 的 pending 占位 */
  const artifactsFromResponse = useCallback((res: ChatAgentResult): ChatMessageArtifact[] => {
    const fromRes = mapResponseArtifacts(res) ?? [];
    const existingJobIds = new Set(fromRes.map((a) => a.job_id).filter(Boolean));
    const placeholders: ChatMessageArtifact[] = [];
    for (const j of collectPendingGenerativeJobs(res)) {
      if (!existingJobIds.has(j.jobId)) {
        placeholders.push({ kind: j.kind, job_id: j.jobId, status: "pending" });
      }
    }
    return [...fromRes, ...placeholders];
  }, []);


  const cancelJobById = useCallback(
    (jobId: string) => {
      if (wsClientRef.current?.connected) {
        wsClientRef.current.cancelGenerativeJob(jobId);
      } else {
        void cancelGenerativeJob(jobId);
      }
      setMessages((prev) =>
        applyToLastAssistant(prev, (arts) =>
          patchArtifactsForJobProgress(arts, jobId, { status: "cancelled", progress_message: "已取消" }),
        ),
      );
      setWsActiveJobIds((prev) => prev.filter((id) => id !== jobId));
    },
    [cancelGenerativeJob, setMessages, wsClientRef],
  );

  const handleCancelGenerative = useCallback(() => {
    if (wsActiveJobIds.length && wsClientRef.current?.connected) {
      for (const id of wsActiveJobIds) {
        wsClientRef.current.cancelGenerativeJob(id);
        setMessages((prev) =>
          applyToLastAssistant(prev, (arts) =>
            patchArtifactsForJobProgress(arts, id, { status: "cancelled", progress_message: "已取消" }),
          ),
        );
      }
      setWsGenerativeMsg("已请求取消…");
      setWsActiveJobIds([]);
    } else {
      for (const j of pollJobs) void cancelGenerativeJob(j.jobId);
    }
  }, [cancelGenerativeJob, pollJobs, setMessages, wsActiveJobIds, wsClientRef]);

  const handleGenerativeJobRetried = useCallback(
    (job: GenerativeJobOut) => {
      applyJobToMessages(job);
      setWsActiveJobIds((prev) => (prev.includes(job.id) ? prev : [...prev, job.id]));
      if (!wsClientRef.current?.connected) {
        setPollJobs((prev) => (prev.some((p) => p.jobId === job.id) ? prev : [...prev, { jobId: job.id, kind: job.kind }]));
      }
    },
    [applyJobToMessages, wsClientRef],
  );

  const generativeStatusMessage = wsGenerativeMsg ?? generativePollMsg;
  const generativeProgressValue = generativeProgress ?? wsGenerativeProgress;

  const generativeStatusEl = useMemo(
    () =>
      generativeStatusMessage ? (
        <ChatGenerativeStatusBanner
          message={generativeStatusMessage}
          progressPercent={generativeProgressValue}
          canCancel={canCancelGenerative || wsActiveJobIds.length > 0}
          onCancel={handleCancelGenerative}
        />
      ) : null,
    [canCancelGenerative, generativeProgressValue, generativeStatusMessage, handleCancelGenerative, wsActiveJobIds.length],
  );

  return {
    handleWsGenerativeJob,
    applyResponseGenerativeJobs,
    artifactsFromResponse,
    generativeStatusEl,
    cancelJobById,
    handleGenerativeJobRetried,
  };
}
