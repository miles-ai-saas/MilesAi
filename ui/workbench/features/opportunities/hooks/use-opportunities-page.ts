"use client";

/** 商机列表页 VM——看板 / 表格、阶段推进、转项目、新建弹窗。 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { usePagedList } from "@/hooks/use-paged-list";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { useRequireAuth } from "@/lib/auth-store";
import { api } from "@/lib/api";
import { useBizDetailNavigation, useBizLegacyDetailRedirect } from "@/features/business/lib/use-biz-detail-tab";
import {
  EMPTY_OPPORTUNITY_FORM,
  type OpportunityFormValues,
} from "@/features/opportunities/lib/opportunity-form-options";
import type { BizClient, BizOpportunity } from "@/lib/types";

export type OpportunitiesViewMode = "board" | "table";

export function useOpportunitiesPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { ready } = useRequireAuth();
  useBizLegacyDetailRedirect("/business/opportunities");
  const { openDetail } = useBizDetailNavigation("/business/opportunities");
  const [viewMode, setViewMode] = useState<OpportunitiesViewMode>("board");
  const [pipeline, setPipeline] = useState<BizOpportunity[]>([]);
  const [pipelineLoading, setPipelineLoading] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState<OpportunityFormValues>(EMPTY_OPPORTUNITY_FORM);
  const [clients, setClients] = useState<BizClient[]>([]);
  const [clientsLoading, setClientsLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const prefillHandled = useRef(false);

  const [stage, setStage] = useState("");

  const list = usePagedList(
    (page, size) => api.listOpportunities(page, size, undefined, stage || undefined),
    { enabled: ready && viewMode === "table", resetKey: `${viewMode}|${stage}` },
  );
  const { requestConfirm, confirmDialog } = useConfirmAction();

  const loadPipeline = useCallback(async () => {
    setPipelineLoading(true);
    try {
      setPipeline(await api.listOpportunityPipeline());
    } finally {
      setPipelineLoading(false);
    }
  }, []);

  const loadClients = useCallback(async () => {
    setClientsLoading(true);
    try {
      const r = await api.listClients(1, 100);
      setClients(r.items);
    } finally {
      setClientsLoading(false);
    }
  }, []);

  const openCreate = useCallback(
    (preselectedClientId?: string) => {
      setCreateForm({ ...EMPTY_OPPORTUNITY_FORM, client_id: preselectedClientId || "" });
      setCreateOpen(true);
      void loadClients();
    },
    [loadClients],
  );

  useEffect(() => {
    if (!ready || viewMode !== "board") return;
    void loadPipeline();
  }, [ready, viewMode, loadPipeline]);

  useEffect(() => {
    if (!ready || prefillHandled.current) return;
    const clientId = searchParams.get("client_id");
    if (!clientId) return;
    prefillHandled.current = true;
    openCreate(clientId);
    router.replace("/business/opportunities");
  }, [ready, searchParams, openCreate, router]);

  const refreshList = useCallback(async () => {
    if (viewMode === "board") await loadPipeline();
    else await list.reload();
  }, [viewMode, loadPipeline, list]);

  const handleCreateSave = useCallback(async () => {
    if (!createForm.name.trim() || !createForm.client_id) return;
    setSaving(true);
    try {
      const o = await api.createOpportunity({
        client_id: createForm.client_id,
        name: createForm.name.trim(),
        stage: createForm.stage,
        expected_value: createForm.expected_value ? Number(createForm.expected_value) : undefined,
        probability: createForm.probability ? Number(createForm.probability) : undefined,
        description: createForm.description.trim() || undefined,
      });
      setCreateOpen(false);
      await refreshList();
      openDetail(o.id);
    } finally {
      setSaving(false);
    }
  }, [createForm, refreshList, openDetail]);

  const handleDelete = useCallback(
    (o: BizOpportunity) => requestConfirm({
      title: "删除商机",
      description: `确定删除「${o.name}」？`,
      onConfirm: async () => {
        await api.deleteOpportunity(o.id);
        await refreshList();
      },
    }),
    [requestConfirm, refreshList],
  );

  const onStageChange = useCallback(async (id: string, stage: string) => {
    await api.updateOpportunity(id, { stage });
    await loadPipeline();
  }, [loadPipeline]);

  const onConvert = useCallback(async (o: BizOpportunity) => {
    const result = await api.convertOpportunityToProject(o.id);
    await loadPipeline();
    router.push(`/business/projects/${result.project_id}`);
  }, [loadPipeline, router]);

  const clearFilters = useCallback(() => setStage(""), []);

  return {
    ready,
    viewMode,
    setViewMode,
    stage,
    onStage: setStage,
    clearFilters,
    hasActiveFilters: Boolean(stage),
    list,
    pipeline,
    pipelineLoading,
    loadPipeline,
    onDelete: handleDelete,
    onStageChange,
    onConvert,
    confirmDialog,
    createOpen,
    setCreateOpen,
    createForm,
    setCreateForm,
    clients,
    clientsLoading,
    saving,
    openCreate,
    handleCreateSave,
    openDetail,
    refreshList,
  };
}

export type OpportunitiesPageVm = ReturnType<typeof useOpportunitiesPage>;
