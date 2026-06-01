"use client";

import { BizPageHero } from "@/features/business-dashboard/components/BizPageHero";
import { useBizPermissions } from "@/features/business/lib/biz-permissions";
import { ClientDetailDialog } from "@/features/clients/components/ClientDetailDialog";
import { ClientFormDialog } from "@/features/clients/components/ClientFormDialog";
import { ClientsTable } from "@/features/clients/components/ClientsTable";
import type { ClientsPageVm } from "@/features/clients/hooks/use-clients-page";

export function ClientsPageView({ vm }: { vm: ClientsPageVm }) {
  const {
    ready,
    search,
    onSearch,
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
  } = vm;
  const { canWriteClient } = useBizPermissions();

  if (!ready) {
    return <p className="text-sm text-ink-muted">加载中…</p>;
  }

  return (
    <div className="w-full">
      <BizPageHero
        flowStep="clients"
        actions={
          canWriteClient ? (
            <button type="button" onClick={openCreate} className="btn-primary text-sm">
              新建客户
            </button>
          ) : undefined
        }
      />

      <div className="mb-4">
        <input
          type="search"
          placeholder="搜索客户名称…"
          value={search}
          onChange={(e) => onSearch(e.target.value)}
          className="input-field w-full max-w-xs text-sm"
        />
      </div>

      <ClientsTable vm={vm} />
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
