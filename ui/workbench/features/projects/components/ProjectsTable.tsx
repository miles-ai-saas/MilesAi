"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { BizTableSkeleton } from "@/features/business/components/BizListSkeleton";
import { useBizPermissions } from "@/features/business/lib/biz-permissions";
import type { ProjectsPageVm } from "@/features/projects/hooks/use-projects-page";
import {
  PROJECT_STATUSES,
  PROJECT_STATUS_LABELS,
  projectStatusBadgeClass,
} from "@/features/projects/lib/biz-labels";
import type { BizProject } from "@/lib/types";

function RowActions({
  projectId,
  onDelete,
}: {
  projectId: string;
  onDelete: () => void;
}) {
  return (
    <div className="flex justify-end gap-2">
      <Link href={`/business/projects/${projectId}`} className="text-xs text-brand hover:underline" onClick={(e) => e.stopPropagation()}>
        详情
      </Link>
      <button
        type="button"
        className="text-xs text-red-600 hover:underline"
        onClick={(e) => {
          e.stopPropagation();
          onDelete();
        }}
      >
        删除
      </button>
    </div>
  );
}

function ProjectMobileCard({
  project,
  onDelete,
}: {
  project: BizProject;
  onDelete: () => void;
}) {
  return (
    <article className="card p-4">
      <div className="flex items-start justify-between gap-3">
        <Link href={`/business/projects/${project.id}`} className="min-w-0">
          <h3 className="truncate font-medium text-ink hover:text-brand">{project.name}</h3>
          {project.code ? <p className="truncate text-xs text-ink-faint">{project.code}</p> : null}
        </Link>
        <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs ${projectStatusBadgeClass(project.status)}`}>
          {PROJECT_STATUS_LABELS[project.status] ?? project.status}
        </span>
      </div>
      <p className="mt-2 text-xs text-ink-muted">{project.work_packages?.length ?? 0} 个工作包</p>
      <div className="mt-3 flex justify-end">
        <RowActions projectId={project.id} onDelete={onDelete} />
      </div>
    </article>
  );
}

export function ProjectsFilters({ vm }: { vm: ProjectsPageVm }) {
  const {
    clientFilter,
    filterClientName,
    clearClientFilter,
    status,
    onStatus,
    clearFilters,
    hasActiveFilters,
    openCreate,
  } = vm;
  const { canWriteProject } = useBizPermissions();

  return (
    <div className="space-y-3 border-b border-line bg-surface-muted/20 px-4 py-4">
      {clientFilter ? (
        <div className="flex flex-wrap items-center gap-3 rounded-lg border border-brand/20 bg-brand/5 px-3 py-2 text-sm">
          <span className="text-ink-muted">
            客户筛选：<span className="font-medium text-ink">{filterClientName ?? clientFilter.slice(0, 8)}</span>
          </span>
          <button type="button" className="text-xs text-brand hover:underline" onClick={clearClientFilter}>
            清除
          </button>
          {canWriteProject ? (
            <button type="button" className="text-xs text-brand hover:underline" onClick={() => openCreate(clientFilter)}>
              为此客户新建
            </button>
          ) : null}
        </div>
      ) : null}

      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-ink-muted">状态</span>
        <button
          type="button"
          className={`rounded-full px-2.5 py-0.5 text-xs ${
            !status ? "bg-brand text-white" : "border border-line bg-surface text-ink-muted hover:text-ink"
          }`}
          onClick={() => onStatus("")}
        >
          全部
        </button>
        {PROJECT_STATUSES.map((item) => (
          <button
            key={item.key}
            type="button"
            className={`rounded-full px-2.5 py-0.5 text-xs ${
              status === item.key
                ? "bg-brand/10 font-medium text-brand ring-1 ring-brand/30"
                : "border border-line bg-surface text-ink-muted hover:border-brand/30 hover:text-ink"
            }`}
            onClick={() => onStatus(status === item.key ? "" : item.key)}
          >
            {item.label}
          </button>
        ))}
        {hasActiveFilters ? (
          <button type="button" className="btn-ghost text-xs text-ink-muted" onClick={clearFilters}>
            清除筛选
          </button>
        ) : null}
      </div>
    </div>
  );
}

export function ProjectsTable({ vm }: { vm: ProjectsPageVm }) {
  const { list, onDelete } = vm;
  const router = useRouter();

  if (list.loading) {
    return <BizTableSkeleton />;
  }

  if (list.error) {
    return (
      <div className="px-4 py-8">
        <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{list.error}</p>
      </div>
    );
  }

  if (list.items.length === 0) {
    return (
      <div className="px-4 py-16 text-center">
        <p className="text-sm text-ink-muted">暂无匹配的项目</p>
        <p className="mt-1 text-xs text-ink-faint">调整筛选条件，或从商机赢单后转化</p>
      </div>
    );
  }

  return (
    <>
      <div className="space-y-3 p-3 md:hidden">
        {list.items.map((project) => (
          <ProjectMobileCard key={project.id} project={project} onDelete={() => onDelete(project)} />
        ))}
      </div>

      <div className="hidden overflow-x-auto md:block">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead className="border-b border-line bg-surface-muted/60 text-xs text-ink-muted">
            <tr>
              <th className="px-4 py-2.5 font-medium">项目名称</th>
              <th className="px-4 py-2.5 font-medium">状态</th>
              <th className="px-4 py-2.5 font-medium">工作包</th>
              <th className="px-4 py-2.5 text-right font-medium">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line-soft">
            {list.items.map((project) => (
              <tr
                key={project.id}
                className="cursor-pointer transition hover:bg-surface-muted/40"
                onClick={() => router.push(`/business/projects/${project.id}`)}
              >
                <td className="px-4 py-3">
                  <p className="font-medium text-ink">{project.name}</p>
                  {project.code ? <p className="text-xs text-ink-faint">{project.code}</p> : null}
                </td>
                <td className="px-4 py-3">
                  <span className={`rounded-full px-2 py-0.5 text-xs ${projectStatusBadgeClass(project.status)}`}>
                    {PROJECT_STATUS_LABELS[project.status] ?? project.status}
                  </span>
                </td>
                <td className="px-4 py-3 tabular-nums text-ink-muted">{project.work_packages?.length ?? 0}</td>
                <td className="px-4 py-3" onClick={(e) => e.stopPropagation()} onKeyDown={(e) => e.stopPropagation()}>
                  <RowActions projectId={project.id} onDelete={() => onDelete(project)} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

export function ProjectsListFooter({ vm }: { vm: ProjectsPageVm }) {
  const { list } = vm;
  return (
    <ResourceListFooter
      className="border-t border-line px-4 py-3"
      page={list.page}
      size={list.size}
      total={list.total}
      onPageChange={list.setPage}
      onSizeChange={list.setSize}
    />
  );
}
