import type { SkillPackage } from "../types";
import type { ApiResponse } from "../types";
import { get, getPage, post, put, patch, http, unwrap } from "./client";
import { appendTagIds } from "./query";
import { buildPageQuery, DEFAULT_PAGE_SIZE } from "../pagination";

export const skillsApi = {
  listSkillPackages: (page = 1, size = DEFAULT_PAGE_SIZE, categoryId?: string, tagIds?: string[]) => {
    let q = buildPageQuery(page, size);
    if (categoryId) q += `&category_id=${encodeURIComponent(categoryId)}`;
    q = appendTagIds(q, tagIds);
    return getPage<SkillPackage>(`/skill-packages?${q}`);
  },

  getSkillPackage: (id: string) => get<SkillPackage>(`/skill-packages/${id}`),

  createSkillPackageBlank: (payload: {
    name: string;
    description?: string;
    category_id: string;
    tag_ids?: string[];
  }) => post<SkillPackage>("/skill-packages/blank", payload),

  createSkillPackage: (payload: {
    name: string;
    description?: string;
    category_id?: string;
    tag_ids?: string[];
    tool_names?: string[];
    prompt_snippet?: string;
  }) => post<SkillPackage>("/skill-packages", payload),

  updateSkillPackage: (
    id: string,
    payload: {
      name?: string;
      description?: string;
      category_id?: string | null;
      tag_ids?: string[];
      tool_names?: string[];
      prompt_snippet?: string;
      is_active?: boolean;
    },
  ) => patch<SkillPackage>(`/skill-packages/${id}`, payload),

  deleteSkillPackage: (id: string) =>
    http.delete(`/skill-packages/${id}`).then(() => undefined),

  listSkillFiles: (id: string) => get<import("../types").SkillFileNode[]>(`/skill-packages/${id}/files`),

  getSkillFile: (id: string, path: string) =>
    get<{ path: string; content: string }>(
      `/skill-packages/${id}/file?path=${encodeURIComponent(path)}`,
    ),

  putSkillFile: (id: string, payload: { path: string; content: string }) =>
    put<{ path: string; content: string }>(`/skill-packages/${id}/file`, payload),

  reindexSkillPackage: (id: string) => post<SkillPackage>(`/skill-packages/${id}/reindex`, {}),

  deleteSkillFile: (id: string, path: string) =>
    http.delete(`/skill-packages/${id}/file?path=${encodeURIComponent(path)}`).then(() => undefined),

  importSkillLocal: (payload: {
    category_id: string;
    local_path: string;
    overwrite_existing?: boolean;
  }) => post<import("../types").SkillImportResult>("/skill-packages/import/local", payload),

  importSkillGit: (payload: {
    category_id: string;
    repo_url: string;
    overwrite_existing?: boolean;
  }) => post<import("../types").SkillImportResult>("/skill-packages/import/git", payload),

  importSkillZip: async (
    categoryId: string,
    file: File,
    overwriteExisting = false,
  ) => {
    const form = new FormData();
    form.append("file", file);
    const q = `category_id=${encodeURIComponent(categoryId)}&overwrite_existing=${overwriteExisting}`;
    const res = await http.post<ApiResponse<import("../types").SkillImportResult>>(
      `/skill-packages/import/zip?${q}`,
      form,
      { headers: { "Content-Type": "multipart/form-data" } },
    );
    return unwrap(res.data);
  },

};
