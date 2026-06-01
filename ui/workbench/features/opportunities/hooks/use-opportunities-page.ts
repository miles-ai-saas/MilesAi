"use client";

/** 商机列表页 VM——看板 / 表格、阶段推进、转项目。 */

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { usePagedList } from "@/hooks/use-paged-list";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { useRequireAuth } from "@/lib/auth-store";
import { api } from "@/lib/api";
import type { BizOpportunity } from "@/lib/types";

export type OpportunitiesViewMode = "board" | "table";

export function useOpportunitiesPage() {
  const router = useRouter();
  const { ready } = useRequireAuth();
  const [viewMode, setViewMode] = useState<OpportunitiesViewMode>("board");
  const [pipeline, setPipeline] = useState<BizOpportunity[]>([]);
  const [pipelineLoading, setPipelineLoading] = useState(false);
  const list = usePagedList((page, size) => api.listOpportunities(page, size), { enabled: ready && viewMode === "table" });
  const { requestConfirm, confirmDialog } = useConfirmAction();

  const loadPipeline = useCallback(async () => {
    setPipelineLoading(true);
    try {
      setPipeline(await api.listOpportunityPipeline());
    } finally {
      setPipelineLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!ready || viewMode !== "board") return;
    void loadPipeline();
  }, [ready, viewMode, loadPipeline]);

  const handleDelete = useCallback(
    (o: BizOpportunity) => requestConfirm({
      title: "删除商机",
      description: `确定删除「${o.name}」？`,
      onConfirm: async () => {
        await api.deleteOpportunity(o.id);
        if (viewMode === "board") await loadPipeline();
        else list.reload();
      },
    }),
    [requestConfirm, viewMode, loadPipeline, list],
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

  return {
    ready,
    viewMode,
    setViewMode,
    list,
    pipeline,
    pipelineLoading,
    loadPipeline,
    onDelete: handleDelete,
    onStageChange,
    onConvert,
    confirmDialog,
  };
}

export type OpportunitiesPageVm = ReturnType<typeof useOpportunitiesPage>;
