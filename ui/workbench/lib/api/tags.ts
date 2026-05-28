import type { TenantTag } from "../types";
import type { ApiResponse } from "../types";
import { get, getPage, post, put, patch, http, unwrap, postWithTrace } from "./client";
import { appendTagIds } from "./query";
import { buildPageQuery, DEFAULT_PAGE_SIZE } from "../pagination";

export const tagsApi = {
  listCategories: async (domain: import("../types").CategoryDomain) => {
    const raw = await get<import("../types").SysCategory[] | null>(`/categories?domain=${domain}`);
    return Array.isArray(raw) ? raw : [];
  },

  listTags: () => get<TenantTag[]>("/tags"),

  createTag: (name: string) => post<TenantTag>("/tags", { name }),

  deleteTag: (id: string) => http.delete(`/tags/${id}`).then(() => undefined),
};
