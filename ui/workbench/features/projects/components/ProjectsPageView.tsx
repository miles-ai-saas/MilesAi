"use client";

import { BizPageHero } from "@/features/business-dashboard/components/BizPageHero";
import { BizListPageSkeleton } from "@/features/business/components/BizListSkeleton";
import { ExportCsvButton } from "@/features/business/components/ExportCsvButton";
import { useBizPermissions } from "@/features/business/lib/biz-permissions";
import { ProjectFormDialog } from "@/features/projects/components/ProjectFormDialog";
import {
  ProjectsFilters,
  ProjectsListFooter,
  ProjectsTable,
} from "@/features/projects/components/ProjectsTable";
import type { ProjectsPageVm } from "@/features/projects/hooks/use-projects-page";
import { PROJECT_STATUS_LABELS } from "@/features/projects/lib/biz-labels";
import { StatChip } from "@/components/ui/StatChip";
import { api } from "@/lib/api";

export function ProjectsPageView({ vm }: { vm: ProjectsPageVm }) {
  const {
    ready,
    confirmDialog,
    list,
    clientFilter,
    status,
    hasActiveFilters,
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

  if (!ready) {
    return <BizListPageSkeleton />;
  }

  const statusLabel = status ? PROJECT_STATUS_LABELS[status] ?? status : "全部状态";

  return (
    <div className="w-full">
      <BizPageHero
        flowStep="projects"
        compact
        subtitle="赢单后立项与执行，关联工作包、交付物与合同"
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

      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <StatChip
          label="项目总数"
          value={String(list.total)}
          hint={hasActiveFilters ? "当前筛选结果" : "全部项目"}
        />
        <StatChip label="状态筛选" value={statusLabel} hint="点击 Chip 快速切换" />
        <StatChip
          label="本页展示"
          value={String(list.items.length)}
          hint={clientFilter ? "已按客户筛选" : `第 ${list.page} 页`}
        />
      </div>

      <div className="card overflow-hidden">
        <ProjectsFilters vm={vm} />
        <ProjectsTable vm={vm} />
        <ProjectsListFooter vm={vm} />
      </div>

      {confirmDialog}
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
