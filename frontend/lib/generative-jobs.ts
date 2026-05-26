/** 从流程 steps / 对话 steps 提取待轮询的 generative job。 */

import type { ChatArtifact, GenerativeJobOut } from "./types";

export function generativeJobToArtifacts(job: GenerativeJobOut): ChatArtifact[] {
  if (job.status !== "success" || !job.result) return [];
  const kind = (job.result.kind as string) || "video";
  const mime = (job.result.mime_type as string) ?? undefined;
  const rawIds = job.result.attachment_ids;
  const ids =
    Array.isArray(rawIds) && rawIds.length > 0
      ? rawIds.map((id) => String(id))
      : job.result.attachment_id
        ? [String(job.result.attachment_id)]
        : [];
  return ids.map((attachment_id) => ({
    kind,
    attachment_id,
    mime_type: mime,
    caption: "生成完成",
  }));
}

export type PendingGenerativeJob = {
  jobId: string;
  kind: "video" | "image";
};

export function extractPendingGenerativeJobs(
  steps: Record<string, unknown>[] | undefined | null,
): PendingGenerativeJob[] {
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
