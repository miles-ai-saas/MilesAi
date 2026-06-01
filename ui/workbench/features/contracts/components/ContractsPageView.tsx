"use client";

import { BizPageHero } from "@/features/business-dashboard/components/BizPageHero";
import { useBizPermissions } from "@/features/business/lib/biz-permissions";
import { ContractDetailDialog } from "@/features/contracts/components/ContractDetailDialog";
import { ContractFormDialog } from "@/features/contracts/components/ContractFormDialog";
import { ContractsTable } from "@/features/contracts/components/ContractsTable";
import type { ContractsPageVm } from "@/features/contracts/hooks/use-contracts-page";

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
  } = vm;
  const { canWriteContract } = useBizPermissions();

  if (!ready) return <p className="text-sm text-ink-muted">加载中…</p>;

  return (
    <div className="w-full">
      <BizPageHero
        flowStep="contracts"
        subtitle="项目签约后登记合同，并关联收付款计划"
        actions={
          canWriteContract ? (
            <button type="button" onClick={() => openCreate()} className="btn-primary text-sm">
              新建合同
            </button>
          ) : undefined
        }
      />
      <ContractsTable vm={vm} />
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
