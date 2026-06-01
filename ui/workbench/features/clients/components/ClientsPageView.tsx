"use client";

import { BizPageHero } from "@/features/business-dashboard/components/BizPageHero";
import { BizListPageSkeleton } from "@/features/business/components/BizListSkeleton";
import { useBizPermissions } from "@/features/business/lib/biz-permissions";
import { ClientDetailDialog } from "@/features/clients/components/ClientDetailDialog";
import { ClientFormDialog } from "@/features/clients/components/ClientFormDialog";
import {
  ClientsFilters,
  ClientsListFooter,
  ClientsTable,
} from "@/features/clients/components/ClientsTable";
import type { ClientsPageVm } from "@/features/clients/hooks/use-clients-page";
import { StatChip } from "@/components/ui/StatChip";

export function ClientsPageView({ vm }: { vm: ClientsPageVm }) {
  const {
    ready,
    confirmDialog,
    createOpen,
    setCreateOpen,
    createForm,
    setCreateForm,
    saving,
    openCreate,
    handleCreateSave,
    detailId,
    closeDetail,
    list,
    hasActiveFilters,
  } = vm;
  const { canWriteClient } = useBizPermissions();

  if (!ready) {
    return <BizListPageSkeleton />;
  }

  return (
    <div className="w-full">
      <BizPageHero
        flowStep="clients"
        compact
        subtitle="维护甲方档案、联系人与保密等级，关联商机与项目"
        actions={
          canWriteClient ? (
            <button type="button" onClick={openCreate} className="btn-primary text-sm">
              新建客户
            </button>
          ) : undefined
        }
      />

      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <StatChip
          label="客户总数"
          value={String(list.total)}
          hint={hasActiveFilters ? "当前筛选结果" : "全部客户"}
        />
        <StatChip label="本页展示" value={String(list.items.length)} hint={`第 ${list.page} 页`} />
        <StatChip label="筛选" value={hasActiveFilters ? "已筛选" : "全部"} hint="按名称搜索" />
      </div>

      <div className="card overflow-hidden">
        <ClientsFilters vm={vm} />
        <ClientsTable vm={vm} />
        <ClientsListFooter vm={vm} />
      </div>

      {confirmDialog}
      <ClientFormDialog
        open={createOpen}
        form={createForm}
        saving={saving}
        onClose={() => setCreateOpen(false)}
        onChange={setCreateForm}
        onSave={() => void handleCreateSave()}
      />
      <ClientDetailDialog
        clientId={detailId}
        onClose={closeDetail}
        onMutated={() => void list.reload()}
      />
    </div>
  );
}
