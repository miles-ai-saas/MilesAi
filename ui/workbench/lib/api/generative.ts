import type { GenerativeJobsMeta } from "../generative-job-labels";
import type { ApiResponse } from "../types";
import { get, getPage, post, put, patch, http, unwrap } from "./client";
import { appendTagIds } from "./query";
import { buildPageQuery, DEFAULT_PAGE_SIZE } from "../pagination";

export const generativeApi = {
  getGenerativeJobsMeta: () =>
    get<import("../generative-job-labels").GenerativeJobsMeta>("/generative/jobs/meta"),

  listGenerativeJobs: (
    page = 1,
    size = DEFAULT_PAGE_SIZE,
    opts?: { status?: string; kind?: string },
  ) => {
    const q = new URLSearchParams(buildPageQuery(page, size));
    if (opts?.status) q.set("status", opts.status);
    if (opts?.kind) q.set("kind", opts.kind);
    return getPage<import("../types").GenerativeJobOut>(`/generative/jobs?${q.toString()}`);
  },

  getGenerativeJob: (jobId: string) =>
    get<import("../types").GenerativeJobOut>(`/generative/jobs/${jobId}`),

  cancelGenerativeJob: (jobId: string) =>
    http
      .post<ApiResponse<import("../types").GenerativeJobOut>>(
        `/generative/jobs/${jobId}/cancel`,
      )
      .then((r) => unwrap(r.data)),

  batchCancelGenerativeJobs: (jobIds: string[]) =>
    http
      .post<
        ApiResponse<{ cancelled: import("../types").GenerativeJobOut[]; skipped: string[] }>
      >("/generative/jobs/batch-cancel", { job_ids: jobIds })
      .then((r) => unwrap(r.data)),

  retryGenerativeJob: (jobId: string) =>
    http
      .post<ApiResponse<import("../types").GenerativeJobOut>>(
        `/generative/jobs/${jobId}/retry`,
      )
      .then((r) => unwrap(r.data)),

  submitGenerativeVideoJob: (body: {
    prompt: string;
    duration?: number;
    resolution?: string;
    image_attachment_id?: string;
    last_frame_attachment_id?: string;
    model_config_id?: string;
  }) =>
    http
      .post<ApiResponse<import("../types").GenerativeJobOut>>("/generative/jobs/video", body)
      .then((r) => unwrap(r.data)),

  listMediaAssets: (
    page = 1,
    size = DEFAULT_PAGE_SIZE,
    opts?: { kind?: string; source?: string; has_kb_document?: boolean },
  ) => {
    const q = new URLSearchParams(buildPageQuery(page, size));
    if (opts?.kind) q.set("kind", opts.kind);
    if (opts?.source) q.set("source", opts.source);
    if (opts?.has_kb_document !== undefined) {
      q.set("has_kb_document", String(opts.has_kb_document));
    }
    return getPage<import("../types").MediaAsset>(`/media-assets?${q.toString()}`);
  },

  getMediaAsset: (id: string) => get<import("../types").MediaAsset>(`/media-assets/${id}`),

  updateMediaAsset: (id: string, body: { title?: string; tags?: string[] }) =>
    http.patch<ApiResponse<import("../types").MediaAsset>>(`/media-assets/${id}`, body).then((r) =>
      unwrap(r.data),
    ),

  deleteMediaAsset: (id: string) =>
    http.delete(`/media-assets/${id}`).then(() => undefined),

  promoteMediaAssetToKb: (
    id: string,
    body: { kb_id: string; filename?: string; run_parse?: boolean },
  ) =>
    http
      .post<ApiResponse<import("../types").MediaAsset>>(`/media-assets/${id}/promote-to-kb`, body)
      .then((r) => unwrap(r.data)),

  // --- 各域枚举元数据：backend tenant/*/meta.py → GET */meta → hooks/use-*-meta → lib/*-labels（见 lib/enum-meta.ts、docs/guides/hooks.md §9）---
};
