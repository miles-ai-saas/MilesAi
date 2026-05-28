import type { ComplianceScanBindings, ComplianceScanResult, WordLibrary, LibraryWord, InterceptLog } from "../types";
import { get, getPage, post, patch, http } from "./client";
import { buildPageQuery, DEFAULT_PAGE_SIZE } from "../pagination";

export const complianceApi = {
  getComplianceScanBindings: () => get<ComplianceScanBindings>("/compliance/bindings"),

  setComplianceScanBindings: (libraryIds: string[]) =>
    http.put("/compliance/bindings", { library_ids: libraryIds }).then((r) => r.data.data as ComplianceScanBindings),

  listWordLibraries: (page = 1, size = DEFAULT_PAGE_SIZE) => getPage<WordLibrary>(`/compliance/libraries?${buildPageQuery(page, size)}`),

  getWordLibrary: (libraryId: string) => get<WordLibrary>(`/compliance/libraries/${libraryId}`),

  createWordLibrary: (payload: { name: string; description?: string; is_active?: boolean; sort_order?: number }) =>
    post<WordLibrary>("/compliance/libraries", payload),

  updateWordLibrary: (
    libraryId: string,
    payload: Partial<{
      name: string;
      description: string | null;
      is_active: boolean;
      sort_order: number;
    }>,
  ) => patch<WordLibrary>(`/compliance/libraries/${libraryId}`, payload),

  deleteWordLibrary: (libraryId: string) => http.delete(`/compliance/libraries/${libraryId}`).then(() => undefined),

  listLibraryWords: (libraryId: string, page = 1, size = DEFAULT_PAGE_SIZE) =>
    getPage<LibraryWord>(`/compliance/libraries/${libraryId}/words?${buildPageQuery(page, size)}`),

  addLibraryWord: (libraryId: string, payload: { word: string; action: "warn" | "block"; is_active?: boolean }) =>
    post<LibraryWord>(`/compliance/libraries/${libraryId}/words`, payload),

  batchAddLibraryWords: (libraryId: string, words: { word: string; action: "warn" | "block"; is_active?: boolean }[]) =>
    post<LibraryWord[]>(`/compliance/libraries/${libraryId}/words/batch`, { words }),

  updateLibraryWord: (libraryId: string, bindingId: string, payload: { action?: "warn" | "block"; is_active?: boolean }) =>
    patch<LibraryWord>(`/compliance/libraries/${libraryId}/words/${bindingId}`, payload),

  deleteLibraryWord: (libraryId: string, bindingId: string) => http.delete(`/compliance/libraries/${libraryId}/words/${bindingId}`).then(() => undefined),

  scanCompliance: (text: string, module = "manual_test") => post<ComplianceScanResult>("/compliance/scan", { text, module }),

  listInterceptLogs: (page = 1, size = DEFAULT_PAGE_SIZE) => getPage<InterceptLog>(`/compliance/logs?${buildPageQuery(page, size)}`),
};
