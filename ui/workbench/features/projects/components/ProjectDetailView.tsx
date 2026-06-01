"use client";

import Link from "next/link";
import { BizListPageSkeleton } from "@/features/business/components/BizListSkeleton";
import { ProjectCloseWizard } from "@/features/projects/components/ProjectCloseWizard";
import { useBizPermissions } from "@/features/business/lib/biz-permissions";
import { ProjectActivityTab } from "@/features/projects/components/ProjectActivityTab";
import { ProjectAiTab } from "@/features/projects/components/ProjectAiTab";
import { ProjectDeliverablesTab } from "@/features/projects/components/ProjectDeliverablesTab";
import { ProjectMembersTab } from "@/features/projects/components/ProjectMembersTab";
import { ProjectSuppliersTab } from "@/features/projects/components/ProjectSuppliersTab";
import { ProjectWorkPackagesTab } from "@/features/projects/components/ProjectWorkPackagesTab";
import type { ProjectDetailPageVm, ProjectDetailTab } from "@/features/projects/hooks/use-project-detail-page";
import {
  PROJECT_STATUS_LABELS,
  PROJECT_STATUSES,
  projectStatusBadgeClass,
  SERVICE_LINE_LABELS,
} from "@/features/projects/lib/biz-labels";
import { StatChip } from "@/components/ui/StatChip";
import type { BizProject, BizProjectCostSummary } from "@/lib/types";

const TABS: { id: ProjectDetailTab; label: string }[] = [
  { id: "info", label: "基本信息" },
  { id: "workpackages", label: "工作包" },
  { id: "deliverables", label: "交付物" },
  { id: "members", label: "成员" },
  { id: "suppliers", label: "供应商" },
  { id: "cost", label: "成本" },
  { id: "activity", label: "动态" },
  { id: "ai", label: "AI 服务" },
];

export function ProjectDetailView({ vm }: { vm: ProjectDetailPageVm }) {
  const {
    project,
    clientName,
    loading,
    error,
    tab,
    deliverables,
    members,
    supplierCount,
    pendingDeliverables,
    costSummary,
    handleTabChange,
  } = vm;

  if (loading) {
    return <BizListPageSkeleton statCount={3} />;
  }

  if (error || !project) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-8 text-center">
        <p className="text-sm text-red-700">{error || "项目不存在"}</p>
        <Link href="/business/projects" className="mt-3 inline-block text-sm text-brand hover:underline">
          返回项目列表
        </Link>
      </div>
    );
  }

  const wpCount = project.work_packages?.length ?? 0;
  const inProgressWp = project.work_packages?.filter((wp) => wp.status === "in_progress").length ?? 0;

  const tabLabel = (id: ProjectDetailTab) => {
    if (id === "workpackages") return `工作包 (${wpCount})`;
    if (id === "deliverables") {
      return pendingDeliverables > 0
        ? `交付物 (${deliverables.length} · ${pendingDeliverables} 待验收)`
        : `交付物 (${deliverables.length})`;
    }
    if (id === "members") return `成员 (${members.length})`;
    if (id === "suppliers") return `供应商 (${supplierCount})`;
    return TABS.find((t) => t.id === id)?.label ?? id;
  };

  return (
    <div className="w-full">
      <Link href="/business/projects" className="mb-4 inline-flex items-center text-xs text-brand hover:underline">
        ← 返回项目列表
      </Link>

      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-xl font-semibold text-ink">{project.name}</h1>
            <span className={`rounded-full px-2 py-0.5 text-xs ${projectStatusBadgeClass(project.status)}`}>
              {PROJECT_STATUS_LABELS[project.status] ?? project.status}
            </span>
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-ink-muted">
            {project.code ? <span>{project.code}</span> : null}
            {clientName ? (
              <Link href={`/business/clients?id=${project.client_id}`} className="text-brand hover:underline">
                客户：{clientName}
              </Link>
            ) : null}
          </div>
        </div>
        <Link href="/business/work-packages" className="btn-ghost shrink-0 text-xs">
          工作包看板
        </Link>
      </div>

      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <StatChip label="工作包" value={String(wpCount)} hint={inProgressWp > 0 ? `${inProgressWp} 个进行中` : "按服务线拆分"} />
        <StatChip
          label="交付物"
          value={String(deliverables.length)}
          hint={pendingDeliverables > 0 ? `${pendingDeliverables} 份待验收` : "文档与设计稿等"}
        />
        <StatChip label="项目成员" value={String(members.length)} hint={supplierCount > 0 ? `关联 ${supplierCount} 家供应商` : "协作与权限"} />
      </div>

      <div className="card overflow-hidden">
        <div className="border-b border-line bg-surface-muted/20 px-2 pt-2">
          <nav aria-label="项目详情 Tab" className="flex gap-1 overflow-x-auto pb-0">
            {TABS.map((t) => (
              <button
                key={t.id}
                type="button"
                className={`shrink-0 rounded-t-lg px-3 py-2 text-sm font-medium transition ${
                  tab === t.id
                    ? "bg-surface text-brand shadow-sm ring-1 ring-line"
                    : "text-ink-muted hover:bg-surface/60 hover:text-ink"
                }`}
                onClick={() => handleTabChange(t.id)}
              >
                {tabLabel(t.id)}
              </button>
            ))}
          </nav>
        </div>

        <div className="p-4 lg:p-6">
          {tab === "info" && <ProjectInfoTab project={project} vm={vm} />}
          {tab === "workpackages" && <ProjectWorkPackagesTab vm={vm} />}
          {tab === "deliverables" && <ProjectDeliverablesTab vm={vm} />}
          {tab === "members" && <ProjectMembersTab vm={vm} />}
          {tab === "suppliers" && <ProjectSuppliersTab vm={vm} />}
          {tab === "cost" && <ProjectCostTab costSummary={costSummary} />}
          {tab === "activity" && <ProjectActivityTab vm={vm} />}
          {tab === "ai" && <ProjectAiTab vm={vm} />}
        </div>
      </div>
    </div>
  );
}

function ProjectInfoTab({ project, vm }: { project: BizProject; vm: ProjectDetailPageVm }) {
  const { canWriteProject } = useBizPermissions();
  const canClose = project.status !== "closed" && project.status !== "cancelled";

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-ink">基本信息</h2>
        {!vm.editingInfo && canWriteProject ? (
          <button type="button" className="text-xs text-brand hover:underline" onClick={() => vm.setEditingInfo(true)}>
            编辑
          </button>
        ) : null}
      </div>

      {vm.editingInfo ? (
        <form onSubmit={(e) => void vm.saveProjectInfo(e)} className="space-y-3 rounded-xl border border-line bg-surface-muted/20 p-4">
          <label>
            <span className="text-xs text-ink-muted">项目名称</span>
            <input
              className="input-field mt-1 w-full text-sm"
              value={vm.infoForm.name}
              onChange={(e) => vm.setInfoForm({ ...vm.infoForm, name: e.target.value })}
              required
            />
          </label>
          <div className="grid gap-3 sm:grid-cols-2">
            <label>
              <span className="text-xs text-ink-muted">项目编号</span>
              <input
                className="input-field mt-1 w-full text-sm"
                value={vm.infoForm.code}
                onChange={(e) => vm.setInfoForm({ ...vm.infoForm, code: e.target.value })}
              />
            </label>
            <label>
              <span className="text-xs text-ink-muted">状态</span>
              <select
                className="input-field mt-1 w-full text-sm"
                value={vm.infoForm.status}
                onChange={(e) => vm.setInfoForm({ ...vm.infoForm, status: e.target.value })}
              >
                {PROJECT_STATUSES.map((s) => (
                  <option key={s.key} value={s.key}>
                    {s.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <label>
            <span className="text-xs text-ink-muted">总预算</span>
            <input
              type="number"
              min="0"
              step="0.01"
              className="input-field mt-1 w-full text-sm"
              value={vm.infoForm.total_budget}
              onChange={(e) => vm.setInfoForm({ ...vm.infoForm, total_budget: e.target.value })}
            />
          </label>
          <label>
            <span className="text-xs text-ink-muted">描述</span>
            <textarea
              className="input-field mt-1 w-full text-sm"
              rows={3}
              value={vm.infoForm.description}
              onChange={(e) => vm.setInfoForm({ ...vm.infoForm, description: e.target.value })}
            />
          </label>
          <div className="flex gap-2">
            <button type="submit" disabled={vm.savingInfo || !vm.infoForm.name.trim()} className="btn-primary text-sm">
              {vm.savingInfo ? "保存中…" : "保存"}
            </button>
            <button type="button" className="btn-sm-outline text-sm" onClick={() => vm.setEditingInfo(false)}>
              取消
            </button>
          </div>
        </form>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          <InfoCard label="描述" value={project.description || "—"} />
          <InfoCard label="总预算" value={project.total_budget ? `¥${project.total_budget.toLocaleString()}` : "—"} />
          <InfoCard label="工作包数" value={`${project.work_packages?.length ?? 0}`} />
          <InfoCard label="项目编号" value={project.code || "—"} />
        </div>
      )}

      {canClose && canWriteProject ? (
        <div className="flex flex-wrap items-center gap-3 rounded-xl border border-line bg-surface-muted/20 p-4">
          <ProjectCloseWizard vm={vm} onDone={() => void vm.refreshProject()} />
          <p className="text-xs text-ink-muted">通过向导检查交付与工作包后再结项，可选案例入库。</p>
        </div>
      ) : null}
    </div>
  );
}

function ProjectCostTab({ costSummary }: { costSummary: BizProjectCostSummary | null }) {
  if (!costSummary) {
    return (
      <div className="space-y-3 py-8">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-12 animate-pulse rounded-lg bg-surface-muted" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <InfoCard label="项目总预算" value={costSummary.total_budget != null ? `¥${costSummary.total_budget.toLocaleString()}` : "—"} />
        <InfoCard label="工作包预算合计" value={costSummary.work_package_budget_total != null ? `¥${costSummary.work_package_budget_total.toLocaleString()}` : "—"} />
        <InfoCard label="工作包实际合计" value={costSummary.work_package_actual_total != null ? `¥${costSummary.work_package_actual_total.toLocaleString()}` : "—"} />
        <InfoCard
          label="预算偏差"
          value={costSummary.budget_variance != null ? `¥${costSummary.budget_variance.toLocaleString()}` : "—"}
        />
      </div>
      <div className="overflow-x-auto rounded-xl border border-line">
        <table className="w-full min-w-[640px] text-sm">
          <thead>
            <tr className="border-b border-line bg-surface-muted/60 text-left text-xs text-ink-muted">
              <th className="px-4 py-2.5 font-medium">工作包</th>
              <th className="px-4 py-2.5 font-medium">服务线</th>
              <th className="px-4 py-2.5 font-medium">预算</th>
              <th className="px-4 py-2.5 font-medium">实际</th>
              <th className="px-4 py-2.5 font-medium">偏差</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line-soft">
            {costSummary.work_packages.map((line) => (
              <tr key={line.id}>
                <td className="px-4 py-3 text-ink">{line.name}</td>
                <td className="px-4 py-3 text-ink-muted">{SERVICE_LINE_LABELS[line.service_line] ?? line.service_line}</td>
                <td className="px-4 py-3 tabular-nums">{line.budget != null ? `¥${line.budget.toLocaleString()}` : "—"}</td>
                <td className="px-4 py-3 tabular-nums">{line.actual_cost != null ? `¥${line.actual_cost.toLocaleString()}` : "—"}</td>
                <td className="px-4 py-3 tabular-nums">{line.variance != null ? `¥${line.variance.toLocaleString()}` : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function InfoCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-line bg-surface-muted/20 px-4 py-3">
      <p className="text-xs text-ink-faint">{label}</p>
      <p className="mt-1 text-sm text-ink">{value}</p>
    </div>
  );
}
