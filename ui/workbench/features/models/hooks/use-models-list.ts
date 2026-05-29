"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { VENDOR_ORDER, type SourceFilter } from "@/features/models/lib/model-page-shared";
import type { ModelCatalogMeta, ModelConfig } from "@/lib/types";

export function useModelsList() {
  const { ready } = useRequireAuth();
  const [meta, setMeta] = useState<ModelCatalogMeta | null>(null);
  const [items, setItems] = useState<ModelConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [vendor, setVendor] = useState("");
  const [modelType, setModelType] = useState("");
  const [source, setSource] = useState<SourceFilter>("");

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const [m, list] = await Promise.all([
        api.getModelCatalogMeta(),
        api.listModelConfigs({
          vendor: vendor || undefined,
          model_type: modelType || undefined,
          source: source || undefined,
          q: search.trim() || undefined,
        }),
      ]);
      setMeta(m);
      setItems(list);
    } finally {
      setLoading(false);
    }
  }, [vendor, modelType, source, search]);

  useEffect(() => {
    if (!ready) return;
    void reload();
  }, [ready, reload]);

  const vendors = useMemo(() => {
    const fromMeta = meta?.vendors ?? [];
    return [...fromMeta].sort((a, b) => VENDOR_ORDER.indexOf(a.value as (typeof VENDOR_ORDER)[number]) - VENDOR_ORDER.indexOf(b.value as (typeof VENDOR_ORDER)[number]));
  }, [meta]);

  return {
    meta,
    items,
    loading,
    search,
    setSearch,
    vendor,
    setVendor,
    modelType,
    setModelType,
    source,
    setSource,
    vendors,
    reload,
  };
}

export type ModelsListSlice = ReturnType<typeof useModelsList>;
