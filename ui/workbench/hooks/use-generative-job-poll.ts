"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { generativeJobToArtifacts } from "@/lib/generative-jobs";
import { subscribeGenerativeJobStream } from "@/lib/generative-job-stream";
import type { ChatArtifact, GenerativeJobOut } from "@/lib/types";

const POLL_MS = 4000;
const MAX_POLLS = 90;

type JobPollTarget = { jobId: string; kind: string };

const TERMINAL = new Set(["success", "failed", "cancelled"]);

export function useGenerativeJobPoll(jobs: JobPollTarget[], onComplete?: (artifacts: ChatArtifact[]) => void) {
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [progressPercent, setProgressPercent] = useState<number | null>(null);
  const [activeJobIds, setActiveJobIds] = useState<string[]>([]);
  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;

  const cancelJob = useCallback(async (jobId: string) => {
    try {
      await api.cancelGenerativeJob(jobId);
      setStatusMsg("已请求取消…");
    } catch (e) {
      setStatusMsg(e instanceof Error ? e.message : "取消失败");
    }
  }, []);

  useEffect(() => {
    if (!jobs.length) {
      setStatusMsg(null);
      setProgressPercent(null);
      setActiveJobIds([]);
      return;
    }

    const controllers = jobs.map(() => new AbortController());
    const pending = new Set(jobs.map((j) => j.jobId));
    setActiveJobIds([...pending]);

    const finishJob = (jobId: string, artifacts: ChatArtifact[], msg: string | null) => {
      pending.delete(jobId);
      setActiveJobIds([...pending]);
      if (artifacts.length && onCompleteRef.current) {
        onCompleteRef.current(artifacts);
      }
      if (msg) setStatusMsg(msg);
      if (pending.size === 0 && !msg?.includes("失败") && !msg?.includes("取消")) {
        setStatusMsg(null);
        setProgressPercent(null);
      }
    };

    const handleJob = (job: GenerativeJobOut) => {
      if (job.progress_percent != null) setProgressPercent(job.progress_percent);
      const label = job.progress_message || "生成中…";
      setStatusMsg(job.progress_percent != null ? `${label}（${job.progress_percent}%）` : label);
      if (job.status === "success") {
        finishJob(job.id, generativeJobToArtifacts(job), null);
      } else if (job.status === "failed") {
        finishJob(job.id, generativeJobToArtifacts(job), job.error_message ?? "生成失败");
      } else if (job.status === "cancelled") {
        finishJob(job.id, generativeJobToArtifacts(job), "任务已取消");
      }
    };

    jobs.forEach((target, i) => {
      const jobId = target.jobId;
      void (async () => {
        try {
          await subscribeGenerativeJobStream(jobId, handleJob, controllers[i].signal);
        } catch {
          /* SSE 不可用时回退轮询 */
          let ticks = 0;
          const poll = async () => {
            if (controllers[i].signal.aborted || !pending.has(jobId)) return;
            ticks += 1;
            try {
              const job = await api.getGenerativeJob(jobId);
              handleJob(job);
              if (TERMINAL.has(job.status)) return;
            } catch {
              /* ignore */
            }
            if (ticks >= MAX_POLLS) {
              finishJob(jobId, [], "生成超时，请在「任务中心」或稍后刷新查看");
              return;
            }
            window.setTimeout(() => void poll(), POLL_MS);
          };
          void poll();
        }
      })();
    });

    const hasVideo = jobs.some((j) => j.kind === "video");
    const hasImage = jobs.some((j) => j.kind === "image");
    const label = hasVideo && hasImage ? "媒体" : hasImage ? "图片" : "视频";
    setStatusMsg(`正在生成${label}（${pending.size} 个任务）…`);

    return () => {
      controllers.forEach((c) => c.abort());
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobs.map((j) => j.jobId).join(",")]);

  return {
    statusMsg,
    progressPercent,
    activeJobIds,
    cancelJob,
    canCancel: activeJobIds.length > 0,
  };
}
