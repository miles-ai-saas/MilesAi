import type { Attachment } from "../types";
import type { ApiResponse } from "../types";
import { get, getPage, post, put, patch, http, unwrap } from "./client";
import { appendTagIds } from "./query";
import { buildPageQuery, DEFAULT_PAGE_SIZE } from "../pagination";

export const attachmentsApi = {
  listAttachments: (page = 1, size = DEFAULT_PAGE_SIZE, opts?: { purpose?: string; resource_type?: string; resource_id?: string }) => {
    const q = new URLSearchParams(buildPageQuery(page, size));
    if (opts?.purpose) q.set("purpose", opts.purpose);
    if (opts?.resource_type) q.set("resource_type", opts.resource_type);
    if (opts?.resource_id) q.set("resource_id", opts.resource_id);
    return getPage<Attachment>(`/attachments?${q.toString()}`);
  },

  uploadAttachment: async (file: File, opts?: { purpose?: string; resource_type?: string; resource_id?: string }) => {
    const form = new FormData();
    form.append("file", file);
    if (opts?.purpose) form.append("purpose", opts.purpose);
    if (opts?.resource_type) form.append("resource_type", opts.resource_type);
    if (opts?.resource_id) form.append("resource_id", opts.resource_id);
    const res = await http.post<ApiResponse<Attachment>>("/attachments", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return unwrap(res.data);
  },

  getAttachment: (id: string) => get<Attachment>(`/attachments/${id}`),

  deleteAttachment: (id: string) => http.delete(`/attachments/${id}`).then(() => undefined),
};
