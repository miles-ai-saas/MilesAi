"use client";

import { BizPageHero } from "@/features/business-dashboard/components/BizPageHero";
import { useBizPermissions } from "@/features/business/lib/biz-permissions";
import { OpportunitiesPipelineBoard } from "@/features/opportunities/components/OpportunitiesPipelineBoard";
import { OpportunitiesTable } from "@/features/opportunities/components/OpportunitiesTable";
import { OpportunityDetailDialog } from "@/features/opportunities/components/OpportunityDetailDialog";
import { OpportunityFormDialog } from "@/features/opportunities/components/OpportunityFormDialog";
import type { OpportunitiesPageVm } from "@/features/opportunities/hooks/use-opportunities-page";

export function OpportunitiesPageView({ vm }: { vm: OpportunitiesPageVm }) {
  const {
    ready,
    viewMode,
    setViewMode,
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
  } = vm;
  const { canWriteOpportunity } = useBizPermissions();
  if (!ready) return <p className="text-sm text-ink-muted">加载中…</p>;

  return (
    <div className="w-full">
      <BizPageHero
        flowStep="opportunities"
        actions={
          <>
            <div className="flex rounded-lg border border-line p-0.5 text-xs">
              <button type="button" className={`rounded-md px-3 py-1.5 ${viewMode === "board" ? "bg-brand-light text-brand" : "text-ink-muted"}`} onClick={() => setViewMode("board")}>看板</button>
              <button type="button" className={`rounded-md px-3 py-1.5 ${viewMode === "table" ? "bg-brand-light text-brand" : "text-ink-muted"}`} onClick={() => setViewMode("table")}>列表</button>
            </div>
            {canWriteOpportunity && (
              <button type="button" onClick={() => openCreate()} className="btn-primary text-sm">
                新建商机
              </button>
            )}
          </>
        }
      />
      {viewMode === "board" ? <OpportunitiesPipelineBoard vm={vm} /> : <OpportunitiesTable vm={vm} />}
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
