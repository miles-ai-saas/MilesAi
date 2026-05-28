/** 域类型：与 backend OpenAPI 对齐。 */

import type { EnumOption } from "@/lib/enum-meta";
export interface KnowledgeBase {
  id: string;
  tenant_id?: string;
  name: string;
  description?: string | null;
  is_public?: boolean;
  embedding_model_config_id: string;
  embedding_model_name?: string | null;
  visual_embedding_model_config_id?: string | null;
  visual_embedding_model_name?: string | null;
  embedding_dimension: number;
  chunk_size?: number;
  chunk_overlap?: number;
  retrieval_mode?: "vector" | "hybrid";
  hybrid_alpha?: number;
  rerank_model_config_id?: string | null;
  rerank_model_name?: string | null;
  rerank_candidate_k?: number;
  created_at?: string;
}

export interface Document {
  id: string;
  kb_id: string;
  filename: string;
  mime_type: string;
  file_size: number;
  status: string;
  fail_reason?: string | null;
  chunk_count?: number | null;
  created_at: string;
}

export interface DocumentChunk {
  id: string;
  document_id: string;
  kb_id: string;
  chunk_index: number;
  content: string;
  page_no?: number | null;
  created_at: string;
}

export interface KbQuota {
  used_knowledge_bases: number;
  max_knowledge_bases: number;
  used_storage_mb: number;
  max_storage_mb: number;
  max_file_mb: number;
}

export interface KbSearchLog {
  id: string;
  tenant_id: string;
  kb_id: string | null;
  kb_ids: string[] | null;
  query: string;
  top_k: number;
  hit_count: number;
  latency_ms: number;
  retrieval_mode: string;
  source: string;
  actor_user_id: string | null;
  agent_id: string | null;
  created_at: string;
}
