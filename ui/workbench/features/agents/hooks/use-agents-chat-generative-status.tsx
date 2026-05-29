"use client";

import { useCallback, useMemo, useState, type Dispatch, type SetStateAction } from "react";
import type { ChatMessage } from "@/features/agents/lib/chat-sessions";
import { useGenerativeJobPoll } from "@/hooks/use-generative-job-poll";
import { generativeJobToArtifacts } from "@/lib/generative-jobs";
import {
  collectPendingGenerativeJobIds,
  collectPendingGenerativeJobs,
  mergeArtifactsIntoLastAssistant,
  type GenerativePollJob,
} from "@/features/agents/lib/agents-chat-helpers";
import type { ChatAgentResult, GenerativeJobOut } from "@/lib/types";

type Params = {
  setMessages: Dispatch<SetStateAction<ChatMessage[]>>;
  wsClientRef: React.MutableRefObject<{ connected?: boolean; cancelGenerativeJob: (id: string) => void } | null>;
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

export function useAgentsChatGenerativeStatus({ setMessages, wsClientRef }: Params) {
  const [pollJobs, setPollJobs] = useState<GenerativePollJob[]>([]);
  const [wsGenerativeMsg, setWsGenerativeMsg] = useState<string | null>(null);
  const [wsGenerativeProgress, setWsGenerativeProgress] = useState<number | null>(null);
  const [wsActiveJobIds, setWsActiveJobIds] = useState<string[]>([]);

  const mergeGenerativeArtifacts = useCallback(
    (artifacts: Parameters<typeof mergeArtifactsIntoLastAssistant>[1]) => {
      if (!artifacts.length) return;
      setMessages((prev) => mergeArtifactsIntoLastAssistant(prev, artifacts));
    },
    [setMessages],
  );

  const {
    statusMsg: generativePollMsg,
    progressPercent: generativeProgress,
    cancelJob: cancelGenerativeJob,
    canCancel: canCancelGenerative,
  } = useGenerativeJobPoll(pollJobs, (artifacts) => {
    setMessages((prev) => mergeArtifactsIntoLastAssistant(prev, artifacts));
    setPollJobs([]);
  });

  const handleWsGenerativeJob = useCallback(
    (job: GenerativeJobOut, phase: "queued" | "progress" | "done") => {
      setWsActiveJobIds((prev) => (prev.includes(job.id) ? prev : [...prev, job.id]));
      if (job.progress_percent != null) setWsGenerativeProgress(job.progress_percent);
      const label = job.progress_message || "生成中…";
      setWsGenerativeMsg(job.progress_percent != null ? `${label}（${job.progress_percent}%）` : label);
      if (phase === "done") {
        setWsActiveJobIds((prev) => prev.filter((id) => id !== job.id));
        if (job.status === "success") {
          mergeGenerativeArtifacts(generativeJobToArtifacts(job));
          setWsGenerativeMsg(null);
          setWsGenerativeProgress(null);
        } else if (job.status === "failed") {
          setWsGenerativeMsg(job.error_message ?? "生成失败");
        } else if (job.status === "cancelled") {
          setWsGenerativeMsg("任务已取消");
        }
      }
    },
    [mergeGenerativeArtifacts],
  );

  const applyResponseGenerativeJobs = useCallback((res: ChatAgentResult, useWsJobs: boolean) => {
    if (!useWsJobs) {
      setPollJobs(collectPendingGenerativeJobs(res));
      return;
    }
    setPollJobs([]);
    const pendingIds = collectPendingGenerativeJobIds(res);
    setWsActiveJobIds(pendingIds);
    if (pendingIds.length) {
      setWsGenerativeMsg(`正在生成（${pendingIds.length} 个任务）…`);
    }
  }, []);

  const handleCancelGenerative = useCallback(() => {
    if (wsActiveJobIds.length && wsClientRef.current?.connected) {
      for (const id of wsActiveJobIds) {
        wsClientRef.current.cancelGenerativeJob(id);
      }
      setWsGenerativeMsg("已请求取消…");
    } else {
      for (const j of pollJobs) void cancelGenerativeJob(j.jobId);
    }
  }, [cancelGenerativeJob, pollJobs, wsActiveJobIds, wsClientRef]);

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
    generativeStatusEl,
  };
}
