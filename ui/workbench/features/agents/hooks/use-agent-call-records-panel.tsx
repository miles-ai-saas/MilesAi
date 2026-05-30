"use client";

import { useCallback, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { usePagedList } from "@/hooks/use-paged-list";

export type AgentCallRecordFilters = {
  status: string;
  conversationId: string;
  q: string;
};

const DEFAULT_FILTERS: AgentCallRecordFilters = {
  status: "",
  conversationId: "",
  q: "",
};

export function useAgentCallRecordsPanel(agentId: string, conversationId?: string) {
  const [filters, setFilters] = useState<AgentCallRecordFilters>(() => ({
    ...DEFAULT_FILTERS,
    conversationId: conversationId ?? "",
  }));
  const [draft, setDraft] = useState(filters);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const resetKey = useMemo(
    () => `${agentId}:${filters.status}:${filters.conversationId}:${filters.q}`,
    [agentId, filters.conversationId, filters.q, filters.status],
  );

  const list = usePagedList(
    useCallback(
      (page, size) =>
        api.listAgentCallRecords(agentId, page, size, {
          status: filters.status || undefined,
          conversation_id: filters.conversationId || undefined,
          q: filters.q || undefined,
        }),
      [agentId, filters.conversationId, filters.q, filters.status],
    ),
    { resetKey, pageSize: 20 },
  );

  const hasActiveFilters = Boolean(filters.status || filters.conversationId || filters.q);

  const setStatusFilter = (status: string) => {
    const next = { ...filters, status };
    setDraft(next);
    setFilters(next);
  };

  const applyFilters = () => setFilters({ ...draft });

  const resetFilters = () => {
    const next = { ...DEFAULT_FILTERS, conversationId: conversationId ?? "" };
    setDraft(next);
    setFilters(next);
  };

  return {
    list,
    filters,
    draft,
    setDraft,
    applyFilters,
    resetFilters,
    setStatusFilter,
    hasActiveFilters,
    selectedId,
    setSelectedId,
  };
}

export type AgentCallRecordsPanelVm = ReturnType<typeof useAgentCallRecordsPanel>;
