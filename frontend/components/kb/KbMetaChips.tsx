import { retrievalModeLabel } from "@/lib/kb-labels";
import type { KnowledgeBase } from "@/lib/types";

export function KbMetaChips({ kb }: { kb: KnowledgeBase }) {
  return (
    <div className="mt-3 flex flex-wrap gap-2">
      <span className="rounded-md bg-surface-muted px-2 py-1 text-xs text-ink-muted">
        {kb.embedding_model_name ?? "向量化模型"}
      </span>
      <span className="rounded-md bg-surface-muted px-2 py-1 text-xs text-ink-muted">
        {kb.embedding_dimension} 维
      </span>
      <span className="rounded-md bg-surface-muted px-2 py-1 text-xs text-ink-muted">
        分片 {kb.chunk_size ?? 500}/{kb.chunk_overlap ?? 50}
      </span>
      <span className="rounded-md bg-brand/10 px-2 py-1 text-xs font-medium text-brand">
        {retrievalModeLabel(kb.retrieval_mode)}
        {kb.retrieval_mode === "hybrid" ? ` · α ${kb.hybrid_alpha ?? 0.5}` : ""}
      </span>
    </div>
  );
}
