import type {
  KbQuota,
  KnowledgeBase,
  Document,
  DocumentChunk,
  KbSearchLog,
} from "../types";
import type { ApiResponse } from "../types";
import { get, getPage, post, put, patch, http, unwrap } from "./client";
import { appendTagIds } from "./query";
import { buildPageQuery, DEFAULT_PAGE_SIZE } from "../pagination";

export const kbApi = {
  getKbQuota: () => get<KbQuota>("/kb/quota"),

  listKbs: (page = 1, size = DEFAULT_PAGE_SIZE) =>
    getPage<KnowledgeBase>(`/kb?${buildPageQuery(page, size)}`),

  createKb: (payload: {
    name: string;
    description?: string;
    embedding_model_config_id?: string;
    chunk_size?: number;
    chunk_overlap?: number;
    retrieval_mode?: "vector" | "hybrid";
    hybrid_alpha?: number;
    rerank_model_config_id?: string | null;
    rerank_candidate_k?: number;
    visual_embedding_model_config_id?: string | null;
    is_public?: boolean;
  }) => post<KnowledgeBase>("/kb", payload),

  updateKb: (
    kbId: string,
    payload: {
      name?: string;
      description?: string | null;
      chunk_size?: number;
      chunk_overlap?: number;
      retrieval_mode?: "vector" | "hybrid";
      hybrid_alpha?: number;
      rerank_model_config_id?: string | null;
      rerank_candidate_k?: number;
      visual_embedding_model_config_id?: string | null;
      is_public?: boolean;
    },
  ) => patch<KnowledgeBase>(`/kb/${kbId}`, payload),

  deleteKb: (kbId: string) => http.delete(`/kb/${kbId}`).then(() => undefined),

  getKb: (kbId: string) => get<KnowledgeBase>(`/kb/${kbId}`),

  listDocuments: (kbId: string, page = 1, size = DEFAULT_PAGE_SIZE) =>
    getPage<Document>(`/kb/${kbId}/documents?${buildPageQuery(page, size)}`),

  listDocumentChunks: (kbId: string, documentId: string, page = 1, size = 20) =>
    getPage<DocumentChunk>(
      `/kb/${kbId}/documents/${documentId}/chunks?${buildPageQuery(page, size)}`,
    ),

  uploadDocument: async (kbId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    const res = await http.post<ApiResponse<Document>>(`/kb/${kbId}/documents`, form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return unwrap(res.data);
  },

  uploadDocumentsBatch: async (kbId: string, files: File[]) => {
    const form = new FormData();
    for (const f of files) form.append("files", f);
    const res = await http.post<ApiResponse<Document[]>>(`/kb/${kbId}/documents/batch`, form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return unwrap(res.data);
  },

  deleteDocument: (kbId: string, documentId: string) =>
    http
      .delete<ApiResponse<null>>(`/kb/${kbId}/documents/${documentId}`)
      .then((res) => {
        unwrap(res.data);
      }),

  retryDocument: (kbId: string, documentId: string) =>
    post<Document>(`/kb/${kbId}/documents/${documentId}/retry`),

  searchKb: (
    kbId: string,
    query: string,
    opts?: {
      top_k?: number;
      mode?: "default" | "vector" | "hybrid";
      media_types?: ("text" | "image" | "audio" | "video")[];
      query_document_id?: string;
      visual_search?: boolean;
    },
  ) =>
    post<{
      query: string;
      mode: string;
      hits: {
        content: string;
        score: number;
        score_vector?: number | null;
        score_keyword?: number | null;
        score_rerank?: number | null;
        filename?: string;
        vector_type?: string | null;
        mime_type?: string | null;
      }[];
    }>(`/kb/${kbId}/search`, {
      query,
      top_k: opts?.top_k ?? 5,
      mode: opts?.mode ?? "default",
      ...(opts?.media_types?.length ? { media_types: opts.media_types } : {}),
      ...(opts?.query_document_id ? { query_document_id: opts.query_document_id } : {}),
      ...(opts?.visual_search ? { visual_search: true } : {}),
    }),

  listKbSearchLogs: (kbId: string, page = 1, size = DEFAULT_PAGE_SIZE) =>
    getPage<KbSearchLog>(`/kb/${kbId}/search-logs?${buildPageQuery(page, size)}`),

};
