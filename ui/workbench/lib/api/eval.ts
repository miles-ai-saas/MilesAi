import type {
  EvalCase,
  EvalCaseImportResult,
  EvalDataset,
  EvalRun,
  EvalRunItem,
  EvalScoringMode,
} from "../types/eval";
import { buildPageQuery, DEFAULT_PAGE_SIZE } from "../pagination";
import { get, getPage, http, patch, post } from "./client";

export const evalApi = {
  listEvalDatasets: (page = 1, size = DEFAULT_PAGE_SIZE) =>
    getPage<EvalDataset>(`/eval/datasets?${buildPageQuery(page, size)}`),

  createEvalDataset: (name: string, description?: string) =>
    post<EvalDataset>("/eval/datasets", { name, description: description || null }),

  updateEvalDataset: (id: string, payload: { name?: string; description?: string | null }) =>
    patch<EvalDataset>(`/eval/datasets/${id}`, payload),

  deleteEvalDataset: (id: string) => http.delete(`/eval/datasets/${id}`).then(() => undefined),

  listEvalCases: (datasetId: string, page = 1, size = DEFAULT_PAGE_SIZE) =>
    getPage<EvalCase>(`/eval/datasets/${datasetId}/cases?${buildPageQuery(page, size)}`),

  createEvalCase: (
    datasetId: string,
    payload: { query: string; name?: string; expected?: Record<string, unknown> | null; sort_index?: number },
  ) => post<EvalCase>(`/eval/datasets/${datasetId}/cases`, payload),

  promoteEvalCaseFromCallRecord: (
    datasetId: string,
    payload: {
      agent_id: string;
      call_id: string;
      name?: string | null;
      expected?: Record<string, unknown> | null;
      prefer_session_text?: boolean;
    },
  ) => post<EvalCase>(`/eval/datasets/${datasetId}/cases/from-call-record`, payload),

  importEvalCasesCsv: (datasetId: string, csvText: string) =>
    post<EvalCaseImportResult>(`/eval/datasets/${datasetId}/cases/import-csv`, { csv_text: csvText }),

  updateEvalCase: (
    datasetId: string,
    caseId: string,
    payload: {
      query?: string;
      name?: string | null;
      expected?: Record<string, unknown> | null;
      sort_index?: number;
    },
  ) => patch<EvalCase>(`/eval/datasets/${datasetId}/cases/${caseId}`, payload),

  deleteEvalCase: (datasetId: string, caseId: string) =>
    http.delete(`/eval/datasets/${datasetId}/cases/${caseId}`).then(() => undefined),

  listEvalRuns: (page = 1, size = DEFAULT_PAGE_SIZE, datasetId?: string) => {
    let q = buildPageQuery(page, size);
    if (datasetId) q += `&dataset_id=${datasetId}`;
    return getPage<EvalRun>(`/eval/runs?${q}`);
  },

  createEvalRun: (payload: {
    dataset_id: string;
    agent_id: string;
    scoring_mode?: EvalScoringMode;
    judge_model_config_id?: string | null;
  }) => post<EvalRun>("/eval/runs", payload),

  getEvalRun: (runId: string) => get<EvalRun>(`/eval/runs/${runId}`),

  startEvalRun: (runId: string) => post<EvalRun>(`/eval/runs/${runId}/start`),

  listEvalRunItems: (runId: string, page = 1, size = DEFAULT_PAGE_SIZE) =>
    getPage<EvalRunItem>(`/eval/runs/${runId}/items?${buildPageQuery(page, size)}`),
};
