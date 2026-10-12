/** Agent 评测域类型（对齐 `/api/v1/eval`）。 */

export interface EvalDataset {
  id: string;
  tenant_id: string;
  name: string;
  description?: string | null;
  created_at: string;
  case_count: number;
}

export interface EvalCase {
  id: string;
  dataset_id: string;
  name?: string | null;
  query: string;
  expected?: Record<string, unknown> | null;
  sort_index: number;
  created_at: string;
}

export type EvalScoringMode = "auto" | "rules" | "llm_judge";

export interface EvalRun {
  id: string;
  tenant_id: string;
  dataset_id: string;
  agent_id: string;
  status: string;
  scoring_mode: string;
  started_at?: string | null;
  finished_at?: string | null;
  error_message?: string | null;
  summary: Record<string, unknown>;
  created_at: string;
}

export interface EvalRunItem {
  id: string;
  run_id: string;
  case_id: string;
  status: string;
  answer_preview: string;
  score?: number | null;
  passed?: boolean | null;
  latency_ms: number;
  call_id?: string | null;
  trace_id?: string | null;
  error_message?: string | null;
  score_detail: Record<string, unknown>;
  created_at: string;
}
