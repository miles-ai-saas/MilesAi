/** 从流程 steps / 对话 steps 提取待轮询的 generative job。 */

import type { ChatArtifact, GenerativeJobOut } from "./types";

export function effectiveArtifactStatus(a: {
  status?: string | null;
  attachment_id?: string | null;
}): "pending" | "running" | "success" | "failed" | "cancelled" {
  if (a.status === "pending" || a.status === "running" || a.status === "success" || a.status === "failed" || a.status === "cancelled") {
    return a.status;
  }
  if (a.attachment_id) return "success";
  return "pending";
}

export function generativeJobToArtifacts(job: GenerativeJobOut): ChatArtifact[] {
  const base = {
    job_id: job.id,
    progress_percent: job.progress_percent ?? null,
    progress_message: job.progress_message ?? null,
    error_message: job.error_message ?? null,
  };
  const kind = job.kind === "image" ? "image" : "video";

  if (job.status === "pending" || job.status === "running") {
    return [{ kind, status: job.status, ...base }];
  }
  if (job.status === "cancelled" || job.status === "failed") {
    return [{ kind, status: job.status, ...base }];
  }
  if (job.status !== "success" || !job.result) return [];

  const resultKind = (job.result.kind as string) || kind;
  const mime = (job.result.mime_type as string) ?? undefined;
  const rawIds = job.result.attachment_ids;
  const ids =
    Array.isArray(rawIds) && rawIds.length > 0
      ? rawIds.map((id) => String(id))
      : job.result.attachment_id
        ? [String(job.result.attachment_id)]
        : [];
  const rawMids = job.result.media_asset_ids;
  const mids =
    Array.isArray(rawMids) && rawMids.length > 0
      ? rawMids.map((id) => String(id))
      : job.result.media_asset_id
        ? [String(job.result.media_asset_id)]
        : [];

  if (!ids.length) {
    return [{ kind: resultKind, status: "success", caption: "生成完成", ...base }];
  }
  return ids.map((attachment_id, i) => ({
    kind: resultKind,
    attachment_id,
    mime_type: mime,
    caption: "生成完成",
    status: "success" as const,
    media_asset_id: mids[i] ?? mids[0] ?? null,
    ...base,
  }));
}

/** 按 job_id 替换：终态多图时删除同 job 旧卡再插入新列表 */
export function replaceArtifactsForJob(prev: ChatArtifact[], jobId: string, nextForJob: ChatArtifact[]): ChatArtifact[] {
  const rest = prev.filter((a) => a.job_id !== jobId);
  return [...rest, ...nextForJob];
}

export function patchArtifactsForJobProgress(
  prev: ChatArtifact[],
  jobId: string,
  patch: Partial<ChatArtifact>,
): ChatArtifact[] {
  let found = false;
  const mapped = prev.map((a) => {
    if (a.job_id !== jobId) return a;
    found = true;
    return { ...a, ...patch };
  });
  if (found) return mapped;
  return [
    ...prev,
    {
      kind: patch.kind || "video",
      job_id: jobId,
      status: patch.status || "running",
      ...patch,
    },
  ];
}

export type PendingGenerativeJob = {
  jobId: string;
  kind: "video" | "image";
};

export function extractPendingGenerativeJobs(steps: Record<string, unknown>[] | undefined | null): PendingGenerativeJob[] {
  if (!steps?.length) return [];
  const out: PendingGenerativeJob[] = [];
  const seen = new Set<string>();

  for (const s of steps) {
    const gj = s.generative_job;
    if (gj && typeof gj === "object") {
      const raw = gj as Record<string, unknown>;
      const id = raw.job_id;
      const status = raw.status;
      if (typeof id === "string" && status === "pending" && !seen.has(id)) {
        seen.add(id);
        const kind = raw.kind === "image" ? "image" : "video";
        out.push({ jobId: id, kind });
      }
    }
    if (s.type === "generative_job" && s.status === "pending") {
      const id = s.job_id;
      if (typeof id === "string" && !seen.has(id)) {
        seen.add(id);
        const kind = s.kind === "image" ? "image" : "video";
        out.push({ jobId: id, kind });
      }
    }
  }
  return out;
}
