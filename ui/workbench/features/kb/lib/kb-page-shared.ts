import type { ModelConfig } from "@/lib/types";

export const KB_PAGE_DESC = "管理企业知识库与文档，为智能体 RAG 检索与流程节点提供知识来源。";

export const DEFAULT_CHUNK_SIZE = 500;
export const DEFAULT_CHUNK_OVERLAP = 50;
export const DEFAULT_RERANK_CANDIDATE_K = 50;

export function embeddingDimension(m: ModelConfig): number {
  const dim = m.extra?.embedding_dimension;
  return typeof dim === "number" ? dim : 0;
}

export function isClipModel(m: ModelConfig): boolean {
  return m.extra?.invoke_mode === "clip";
}
