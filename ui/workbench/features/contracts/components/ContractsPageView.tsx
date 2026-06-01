"use client";

import { BizPageHero } from "@/features/business-dashboard/components/BizPageHero";
import { BizListPageSkeleton } from "@/features/business/components/BizListSkeleton";
import { useBizPermissions } from "@/features/business/lib/biz-permissions";
import { ContractDetailDialog } from "@/features/contracts/components/ContractDetailDialog";
import { ContractFormDialog } from "@/features/contracts/components/ContractFormDialog";
import {
  ContractsFilters,
  ContractsListFooter,
  ContractsTable,
} from "@/features/contracts/components/ContractsTable";
import type { ContractsPageVm } from "@/features/contracts/hooks/use-contracts-page";
import { CONTRACT_STATUS_LABELS } from "@/features/contracts/lib/contract-labels";
import { StatChip } from "@/components/ui/StatChip";

export function ContractsPageView({ vm }: { vm: ContractsPageVm }) {
  const {
    ready,
    confirmDialog,
    createOpen,
    setCreateOpen,
    createForm,
    setCreateForm,
    projects,
    clients,
    optionsLoading,
    saving,
    openCreate,
    handleCreateSave,
    detailId,
    closeDetail,
    list,
    status,
    hasActiveFilters,
  } = vm;
  const { canWriteContract } = useBizPermissions();

  if (!ready) {
    return <BizListPageSkeleton />;
  }

  const statusLabel = status ? CONTRACT_STATUS_LABELS[status] ?? status : "全部状态";

  return (
    <div className="w-full">
      <BizPageHero
        flowStep="contracts"
        compact
        subtitle="管理签约、履约条款与收付款计划"
        actions={
          canWriteContract ? (
            <button type="button" onClick={() => openCreate()} className="btn-primary text-sm">
              新建合同
            </button>
          ) : undefined
        }
      />

      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <StatChip
          label="合同总数"
          value={String(list.total)}
          hint={hasActiveFilters ? "当前筛选结果" : "全部合同"}
        />
        <StatChip label="状态筛选" value={statusLabel} hint="点击 Chip 快速切换" />
        <StatChip label="本页展示" value={String(list.items.length)} hint={`第 ${list.page} 页`} />
      </div>

      <div className="card overflow-hidden">
        <ContractsFilters vm={vm} />
        <ContractsTable vm={vm} />
        <ContractsListFooter vm={vm} />
      </div>

      {confirmDialog}
      <ContractFormDialog
        open={createOpen}
        form={createForm}
        projects={projects}
        clients={clients}
        optionsLoading={optionsLoading}
        saving={saving}
        onClose={() => setCreateOpen(false)}
        onChange={setCreateForm}
        onSave={() => void handleCreateSave()}
      />
      <ContractDetailDialog
        contractId={detailId}
        onClose={closeDetail}
        onMutated={() => void list.reload()}
      />
    </div>
  );
}
