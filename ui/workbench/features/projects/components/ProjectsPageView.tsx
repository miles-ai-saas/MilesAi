"use client";

import Link from "next/link";
import { BizPageHero } from "@/features/business-dashboard/components/BizPageHero";
import { ExportCsvButton } from "@/features/business/components/ExportCsvButton";
import { useBizPermissions } from "@/features/business/lib/biz-permissions";
import { ProjectFormDialog } from "@/features/projects/components/ProjectFormDialog";
import { ProjectsTable } from "@/features/projects/components/ProjectsTable";
import type { ProjectsPageVm } from "@/features/projects/hooks/use-projects-page";
import { api } from "@/lib/api";

export function ProjectsPageView({ vm }: { vm: ProjectsPageVm }) {
  const {
    ready,
    confirmDialog,
    list,
    clientFilter,
    filterClientName,
    clearClientFilter,
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
  const { canWriteProject } = useBizPermissions();

  return (
    <div className="w-full">
      {!ready ? (
        <p className="text-sm text-ink-muted">加载中…</p>
      ) : (
        <>
          <BizPageHero
            flowStep="projects"
            compact
            actions={
              <div className="flex items-center gap-2">
                <ExportCsvButton url={api.exportProjectsCsv(clientFilter || undefined)} filename="biz-projects.csv" />
                {canWriteProject ? (
                  <button type="button" onClick={() => openCreate()} className="btn-primary text-sm">
                    新建项目
                  </button>
                ) : null}
              </div>
            }
          />

          {clientFilter ? (
            <div className="mb-4 flex flex-wrap items-center gap-3 rounded-lg border border-line bg-surface-muted/40 px-3 py-2 text-sm">
              <span className="text-ink-muted">
                筛选客户：<span className="font-medium text-ink">{filterClientName ?? clientFilter.slice(0, 8)}</span>
              </span>
              <button type="button" className="text-xs text-brand hover:underline" onClick={clearClientFilter}>
                清除筛选
              </button>
              {canWriteProject ? (
                <button type="button" className="text-xs text-brand hover:underline" onClick={() => openCreate(clientFilter)}>
                  为此客户新建项目
                </button>
              ) : null}
            </div>
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
