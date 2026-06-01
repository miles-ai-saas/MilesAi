"use client";

import { BizPageHero } from "@/features/business-dashboard/components/BizPageHero";
import { useBizPermissions } from "@/features/business/lib/biz-permissions";
import { SupplierDetailDialog } from "@/features/suppliers/components/SupplierDetailDialog";
import { SupplierFormDialog } from "@/features/suppliers/components/SupplierFormDialog";
import { SuppliersFilters, SuppliersTable } from "@/features/suppliers/components/SuppliersTable";
import type { SuppliersPageVm } from "@/features/suppliers/hooks/use-suppliers-page";

export function SuppliersPageView({ vm }: { vm: SuppliersPageVm }) {
  const {
    ready,
    confirmDialog,
    detailId,
    closeDetail,
    list,
    createOpen,
    setCreateOpen,
    createForm,
    setCreateForm,
    saving,
    openCreate,
    handleCreateSave,
  } = vm;
  const { canWriteSupplier } = useBizPermissions();

  if (!ready) return <p className="text-sm text-ink-muted">加载中…</p>;

  return (
    <div className="w-full">
      <BizPageHero
        flowStep="suppliers"
        flowHighlight={false}
        subtitle="与主链路并行：为项目关联印刷、拍摄、搭建等外包方"
        actions={
          canWriteSupplier ? (
            <button type="button" onClick={openCreate} className="btn-primary text-sm">
              新建供应商
            </button>
          ) : undefined
        }
      />
      <SuppliersFilters vm={vm} />
      <SuppliersTable vm={vm} />
      {confirmDialog}
      <SupplierFormDialog
        open={createOpen}
        form={createForm}
        saving={saving}
        onClose={() => setCreateOpen(false)}
        onChange={setCreateForm}
        onSave={() => void handleCreateSave()}
      />
      <SupplierDetailDialog
        supplierId={detailId}
        onClose={closeDetail}
        onMutated={() => void list.reload()}
      />
    </div>
  );
}
