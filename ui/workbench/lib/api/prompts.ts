import type { PromptTemplate } from "../types";
import type { ApiResponse } from "../types";
import { get, getPage, post, put, patch, http, unwrap, postWithTrace } from "./client";
import { appendTagIds } from "./query";
import { buildPageQuery, DEFAULT_PAGE_SIZE } from "../pagination";

export const promptsApi = {
  listPromptTemplates: (page = 1, size = DEFAULT_PAGE_SIZE, categoryId?: string, tagIds?: string[]) => {
    let q = buildPageQuery(page, size);
    if (categoryId) q += `&category_id=${categoryId}`;
    q = appendTagIds(q, tagIds);
    return getPage<PromptTemplate>(`/prompt-templates?${q}`);
  },

  createPromptTemplate: (name: string, content: string, description?: string, categoryId?: string, tagIds?: string[]) =>
    post<PromptTemplate>("/prompt-templates", {
      name,
      content,
      description,
      category_id: categoryId || null,
      tag_ids: tagIds ?? [],
    }),

  updatePromptTemplate: (
    id: string,
    payload: {
      name?: string;
      content?: string;
      description?: string;
      is_active?: boolean;
      category_id?: string | null;
      tag_ids?: string[];
    },
  ) => patch<PromptTemplate>(`/prompt-templates/${id}`, payload),

  deletePromptTemplate: (id: string) => http.delete(`/prompt-templates/${id}`).then(() => undefined),
};
