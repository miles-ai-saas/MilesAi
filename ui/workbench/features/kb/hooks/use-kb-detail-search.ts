"use client";

import { useCallback, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { usePagedList } from "@/hooks/use-paged-list";
import { type KbDetailAlertState, type KbDetailTabKey, type KbSearchHit } from "@/features/kb/hooks/use-kb-detail-page";
import type { Document } from "@/lib/types";

type SearchSliceDeps = {
  id: string;
  ready: boolean;
  tab: KbDetailTabKey;
  setAlert: (alert: KbDetailAlertState) => void;
  docItems: Document[];
};

export function useKbDetailSearch({ id, ready, tab, setAlert, docItems }: SearchSliceDeps) {
  const [searchQ, setSearchQ] = useState("");
  const [searchTopK, setSearchTopK] = useState(5);
  const [searchMode, setSearchMode] = useState<"default" | "vector" | "hybrid">("default");
  const [searchMediaTypes, setSearchMediaTypes] = useState<string[]>([]);
  const [searchQueryDocId, setSearchQueryDocId] = useState("");
  const [searchVisual, setSearchVisual] = useState(false);
  const [searching, setSearching] = useState(false);
  const [searchResultMode, setSearchResultMode] = useState("");
  const [searchHits, setSearchHits] = useState<KbSearchHit[]>([]);

  const logs = usePagedList(
    useCallback((p, s) => api.listKbSearchLogs(id, p, s), [id]),
    { enabled: ready && !!id && tab === "logs", resetKey: `${id}-${tab}` },
  );

  const imageVideoDocs = useMemo(
    () => docItems.filter((d) => d.status === "ready" && (/^image\//.test(d.mime_type) || /^video\//.test(d.mime_type))),
    [docItems],
  );

  const imageDocs = useMemo(() => docItems.filter((d) => d.status === "ready" && /^image\//.test(d.mime_type)), [docItems]);

  const onSearch = async () => {
    const q = searchQ.trim();
    if (searchVisual ? !q && !searchQueryDocId : !q && !searchQueryDocId) return;
    setSearching(true);
    setAlert(null);
    try {
      const res = await api.searchKb(id, q, {
        mode: searchMode,
        top_k: searchTopK,
        ...(searchMediaTypes.length ? { media_types: searchMediaTypes as ("text" | "image" | "audio" | "video")[] } : {}),
        ...(searchQueryDocId ? { query_document_id: searchQueryDocId } : {}),
        ...(searchVisual ? { visual_search: true } : {}),
      });
      setSearchResultMode(res.mode);
      setSearchHits(res.hits);
      if (tab === "logs") await logs.reload();
    } catch (err) {
      setAlert({ tone: "error", message: err instanceof Error ? err.message : "检索失败" });
    } finally {
      setSearching(false);
    }
  };

  return {
    logs,
    searchQ,
    setSearchQ,
    searchTopK,
    setSearchTopK,
    searchMode,
    setSearchMode,
    searchMediaTypes,
    setSearchMediaTypes,
    searchQueryDocId,
    setSearchQueryDocId,
    searchVisual,
    setSearchVisual,
    searching,
    searchResultMode,
    searchHits,
    imageVideoDocs,
    imageDocs,
    onSearch,
  };
}

export type KbDetailSearchSlice = ReturnType<typeof useKbDetailSearch>;
