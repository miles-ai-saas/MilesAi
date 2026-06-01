"use client";

import { BizPageHero } from "@/features/business-dashboard/components/BizPageHero";
import { useBizPermissions } from "@/features/business/lib/biz-permissions";
import { SupplierFormDialog } from "@/features/suppliers/components/SupplierFormDialog";
import {
  SuppliersFilters,
  SuppliersListFooter,
  SuppliersTable,
} from "@/features/suppliers/components/SuppliersTable";
import type { SuppliersPageVm } from "@/features/suppliers/hooks/use-suppliers-page";
import {
  SUPPLIER_CATEGORY_LABELS,
  SUPPLIER_STATUS_LABELS,
} from "@/features/suppliers/lib/supplier-labels";
import { StatChip } from "@/components/ui/StatChip";

function PageSkeleton() {
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-20 animate-pulse rounded-xl bg-surface-muted" />
        ))}
      </div>
      <div className="h-[420px] animate-pulse rounded-xl bg-surface-muted" />
    </div>
  );
}

export function SuppliersPageView({ vm }: { vm: SuppliersPageVm }) {
  const {
    ready,
    confirmDialog,
    list,
    createOpen,
    setCreateOpen,
    createForm,
    setCreateForm,
    saving,
    openCreate,
    handleCreateSave,
    category,
    status,
    hasActiveFilters,
  } = vm;
  const { canWriteSupplier } = useBizPermissions();

  if (!ready) {
    return <PageSkeleton />;
  }

  const categoryLabel = category ? SUPPLIER_CATEGORY_LABELS[category] ?? category : "全部类型";
  const statusLabel = status ? SUPPLIER_STATUS_LABELS[status] ?? status : "全部状态";

  return (
    <div className="w-full">
      <BizPageHero
        flowStep="suppliers"
        flowHighlight={false}
        compact
        title="供应商"
        subtitle="管理外协与合作方，维护联系人及银行信息，关联项目采购"
        actions={
          canWriteSupplier ? (
            <button type="button" onClick={openCreate} className="btn-primary text-sm">
              新建供应商
            </button>
          ) : undefined
        }
      />

      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <StatChip
          label="供应商总数"
          value={String(list.total)}
          hint={hasActiveFilters ? "当前筛选结果" : "全部供应商"}
        />
        <StatChip label="类型筛选" value={categoryLabel} hint="点击 Chip 快速切换" />
        <StatChip label="合作状态" value={statusLabel} hint="合作中 / 暂停 / 黑名单" />
      </div>

      <div className="card overflow-hidden">
        <SuppliersFilters vm={vm} />
        <SuppliersTable vm={vm} />
        <SuppliersListFooter vm={vm} />
      </div>

      {confirmDialog}
      <SupplierFormDialog
        open={createOpen}
        form={createForm}
        saving={saving}
        onClose={() => setCreateOpen(false)}
        onChange={setCreateForm}
        onSave={() => void handleCreateSave()}
      />
    </div>
  );
}
