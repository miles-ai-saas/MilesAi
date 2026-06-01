"use client";

import { BizPageHero } from "@/features/business-dashboard/components/BizPageHero";
import { ProjectFormDialog } from "@/features/projects/components/ProjectFormDialog";
import { ProjectsTable } from "@/features/projects/components/ProjectsTable";
import type { ProjectsPageVm } from "@/features/projects/hooks/use-projects-page";

export function ProjectsPageView({ vm }: { vm: ProjectsPageVm }) {
  const {
    ready,
    confirmDialog,
    list,
    clientFilter,
    filterClientName,
    createOpen,
    closeCreate,
    createForm,
    setCreateForm,
    clients,
    clientsLoading,
    saving,
    createError,
    openCreate,
    handleCreateSave,
  } = vm;

  return (
    <div className="w-full">
      {!ready ? (
        <p className="text-sm text-ink-muted">加载中…</p>
      ) : (
        <>
          <BizPageHero
            flowStep="projects"
            subtitle="商机赢单后立项；工作包、交付物、成员与结项均在此管理"
            actions={
              <button type="button" onClick={() => openCreate()} className="btn-primary text-sm">
                新建项目
              </button>
            }
          />

          {clientFilter ? (
            <p className="mb-4 text-sm text-ink-muted">
              当前筛选：客户 {filterClientName ?? clientFilter.slice(0, 8)}
            </p>
          ) : null}

          {list.error ? (
            <p className="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{list.error}</p>
          ) : null}

          <ProjectsTable vm={vm} />
          {confirmDialog}
        </>
      )}

      <ProjectFormDialog
        open={createOpen}
        form={createForm}
        clients={clients}
        clientsLoading={clientsLoading}
        saving={saving}
        createError={createError}
        onClose={closeCreate}
        onChange={setCreateForm}
        onSave={() => void handleCreateSave()}
      />
    </div>
  );
}
