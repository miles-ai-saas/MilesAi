"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { subscribeGenerativeJobStream } from "@/lib/generative-job-stream";
import { canCancelGenerativeJob, canRetryGenerativeJob, isGenerativeJobTerminal } from "@/lib/generative-job-labels";
import type { GenerativeJobOut } from "@/lib/types";

type Params = {
  open: boolean;
  jobId: string | null;
  onChanged?: () => void;
};

export function useGenerativeJobDetailDialog({ open, jobId, onChanged }: Params) {
  const [job, setJob] = useState<GenerativeJobOut | null>(null);
  const [msg, setMsg] = useState("");
  const [acting, setActing] = useState(false);
  const [loading, setLoading] = useState(false);
  const [sseFailed, setSseFailed] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const applyJob = useCallback((row: GenerativeJobOut) => {
    setJob(row);
    setMsg("");
  }, []);

  const reload = useCallback(async () => {
    if (!jobId) return;
    setLoading(true);
    try {
      applyJob(await api.getGenerativeJob(jobId));
    } catch (e) {
      setJob(null);
      setMsg(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [jobId, applyJob]);

  useEffect(() => {
    if (!open || !jobId) {
      setJob(null);
      setMsg("");
      abortRef.current?.abort();
      abortRef.current = null;
      return;
    }
    void reload();
  }, [open, jobId, reload]);

  useEffect(() => {
    if (!open || !jobId) {
      setSseFailed(false);
    }
  }, [open, jobId]);

  useEffect(() => {
    if (!open || !jobId || !job || isGenerativeJobTerminal(job.status)) {
      abortRef.current?.abort();
      abortRef.current = null;
      return;
    }
    const ac = new AbortController();
    abortRef.current = ac;
    void subscribeGenerativeJobStream(
      jobId,
      (row) => {
        applyJob(row);
        if (isGenerativeJobTerminal(row.status)) {
          onChanged?.();
        }
      },
      ac.signal,
    ).catch(() => setSseFailed(true));
    return () => ac.abort();
  }, [open, jobId, job?.status, applyJob, onChanged]);

  const onCancel = async () => {
    if (!jobId) return;
    setActing(true);
    try {
      applyJob(await api.cancelGenerativeJob(jobId));
      onChanged?.();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "取消失败");
    } finally {
      setActing(false);
    }
  };

  const onRetry = async () => {
    if (!jobId) return;
    setActing(true);
    try {
      applyJob(await api.retryGenerativeJob(jobId));
      setSseFailed(false);
      onChanged?.();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "重试失败");
    } finally {
      setActing(false);
    }
  };

  const celeryTaskHref = job?.celery_task_record_id ? `/workbench/tasks?category=celery&task=${encodeURIComponent(job.celery_task_record_id)}` : null;
  const prompt = job?.params && typeof job.params.prompt === "string" ? job.params.prompt : "";

  return {
    job,
    msg,
    acting,
    loading,
    sseFailed,
    reload,
    onCancel,
    onRetry,
    celeryTaskHref,
    prompt,
    canRetry: job ? canRetryGenerativeJob(job.status) : false,
    canCancel: job ? canCancelGenerativeJob(job.status) : false,
  };
}

export type GenerativeJobDetailDialogVm = ReturnType<typeof useGenerativeJobDetailDialog>;
