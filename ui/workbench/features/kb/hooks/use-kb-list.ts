"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { usePagedList } from "@/hooks/use-paged-list";
import { useKbMeta } from "@/features/kb/hooks/use-kb-meta";
import { filterBySearch } from "@/lib/filter-search";
import {
  DEFAULT_CHUNK_OVERLAP,
  DEFAULT_CHUNK_SIZE,
  DEFAULT_RERANK_CANDIDATE_K,
  isClipModel,
} from "@/features/kb/lib/kb-page-shared";
import type { KnowledgeBase, KbQuota, ModelConfig } from "@/lib/types";

export function useKbList() {
  const { ready } = useRequireAuth();
  const [search, setSearch] = useState("");
  const kbMeta = useKbMeta(ready);
  const [quota, setQuota] = useState<KbQuota | null>(null);
  const [quotaLoading, setQuotaLoading] = useState(true);

  const list = usePagedList(useCallback((p, s) => api.listKbs(p, s), []), { enabled: ready });

  const reloadQuota = useCallback(() => {
    if (!ready) return Promise.resolve();
    setQuotaLoading(true);
    return api
      .getKbQuota()
      .then(setQuota)
      .catch(() => setQuota(null))
      .finally(() => setQuotaLoading(false));
  }, [ready]);

  useEffect(() => {
    void reloadQuota();
  }, [reloadQuota]);

  const filtered = useMemo(() => filterBySearch(list.items, search, (kb) => `${kb.name} ${kb.description ?? ""}`), [list.items, search]);

  return {
    search,
    setSearch,
    list,
    kbMeta,
    quota,
    quotaLoading,
    filtered,
    reloadQuota,
  };
}

export type KbListSlice = ReturnType<typeof useKbList>;

export function useKbModels(ready: boolean) {
  const [embeddingModels, setEmbeddingModels] = useState<ModelConfig[]>([]);
  const [rerankModels, setRerankModels] = useState<ModelConfig[]>([]);

  useEffect(() => {
    if (!ready) return;
    void api
      .listModelConfigs({ model_type: "embedding" })
      .then(setEmbeddingModels)
      .catch(() => {});
    void api
      .listModelConfigs({ model_type: "rerank" })
      .then(setRerankModels)
      .catch(() => {});
  }, [ready]);

  const textEmbeddingModels = useMemo(() => embeddingModels.filter((m) => !isClipModel(m)), [embeddingModels]);
  const clipModels = useMemo(() => embeddingModels.filter((m) => isClipModel(m)), [embeddingModels]);

  return { embeddingModels, rerankModels, textEmbeddingModels, clipModels };
}
