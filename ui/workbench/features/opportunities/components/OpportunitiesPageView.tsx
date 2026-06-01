"use client";

import { useMemo } from "react";
import { BizPageHero } from "@/features/business-dashboard/components/BizPageHero";
import { BizListPageSkeleton } from "@/features/business/components/BizListSkeleton";
import { ExportCsvButton } from "@/features/business/components/ExportCsvButton";
import { useBizPermissions } from "@/features/business/lib/biz-permissions";
import { OpportunitiesPipelineBoard } from "@/features/opportunities/components/OpportunitiesPipelineBoard";
import {
  OpportunitiesFilters,
  OpportunitiesListFooter,
  OpportunitiesTable,
} from "@/features/opportunities/components/OpportunitiesTable";
import { OpportunityDetailDialog } from "@/features/opportunities/components/OpportunityDetailDialog";
import { OpportunityFormDialog } from "@/features/opportunities/components/OpportunityFormDialog";
import type { OpportunitiesPageVm } from "@/features/opportunities/hooks/use-opportunities-page";
import { OPPORTUNITY_STAGE_LABELS } from "@/features/opportunities/lib/opportunity-labels";
import { StatChip } from "@/components/ui/StatChip";
import { api } from "@/lib/api";

function ViewModeToggle({
  viewMode,
  onChange,
}: {
  viewMode: "board" | "table";
  onChange: (mode: "board" | "table") => void;
}) {
  return (
    <div className="flex rounded-lg border border-line p-0.5 text-xs">
      <button
        type="button"
        className={`rounded-md px-3 py-1.5 ${viewMode === "board" ? "bg-brand text-white" : "text-ink-muted hover:text-ink"}`}
        onClick={() => onChange("board")}
      >
        看板
      </button>
      <button
        type="button"
        className={`rounded-md px-3 py-1.5 ${viewMode === "table" ? "bg-brand text-white" : "text-ink-muted hover:text-ink"}`}
        onClick={() => onChange("table")}
      >
        列表
      </button>
    </div>
  );
}

export function OpportunitiesPageView({ vm }: { vm: OpportunitiesPageVm }) {
  const {
    ready,
    viewMode,
    setViewMode,
    stage,
    hasActiveFilters,
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
    detailId,
    closeDetail,
    refreshList,
    list,
    pipeline,
    pipelineLoading,
  } = vm;
  const { canWriteOpportunity } = useBizPermissions();

  const pipelineTotal = useMemo(() => pipeline.length, [pipeline]);

  if (!ready) {
    return <BizListPageSkeleton />;
  }

  const stageLabel = stage ? OPPORTUNITY_STAGE_LABELS[stage] ?? stage : "全部阶段";
  const totalDisplay = viewMode === "board" ? String(pipelineTotal) : String(list.total);

  return (
    <div className="w-full">
      <BizPageHero
        flowStep="opportunities"
        compact
        subtitle="跟进销售漏斗、报价与赢单转化"
        actions={
          <>
            <ViewModeToggle viewMode={viewMode} onChange={setViewMode} />
            <ExportCsvButton url={api.exportOpportunitiesCsv()} filename="biz-opportunities.csv" />
            {canWriteOpportunity ? (
              <button type="button" onClick={() => openCreate()} className="btn-primary text-sm">
                新建商机
              </button>
            ) : null}
          </>
        }
      />

      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <StatChip
          label="商机总数"
          value={totalDisplay}
          hint={viewMode === "board" ? "看板全量" : hasActiveFilters ? "当前筛选结果" : "全部商机"}
        />
        <StatChip label="视图" value={viewMode === "board" ? "看板" : "列表"} hint="看板拖拽推进阶段" />
        <StatChip
          label="阶段筛选"
          value={viewMode === "table" ? stageLabel : "—"}
          hint={viewMode === "table" ? "列表模式可用" : "切换列表筛选"}
        />
      </div>

      {viewMode === "board" ? (
        <div className="card overflow-hidden p-4">
          {pipelineLoading ? (
            <div className="h-64 animate-pulse rounded-lg bg-surface-muted" />
          ) : (
            <OpportunitiesPipelineBoard vm={vm} />
          )}
        </div>
      ) : (
        <div className="card overflow-hidden">
          <OpportunitiesFilters vm={vm} />
          <OpportunitiesTable vm={vm} />
          <OpportunitiesListFooter vm={vm} />
        </div>
      )}

      {confirmDialog}
      <OpportunityFormDialog
        open={createOpen}
        form={createForm}
        clients={clients}
        clientsLoading={clientsLoading}
        saving={saving}
        onClose={() => setCreateOpen(false)}
        onChange={setCreateForm}
        onSave={() => void handleCreateSave()}
      />
      <OpportunityDetailDialog
        opportunityId={detailId}
        onClose={closeDetail}
        onMutated={() => void refreshList()}
      />
    </div>
  );
}
