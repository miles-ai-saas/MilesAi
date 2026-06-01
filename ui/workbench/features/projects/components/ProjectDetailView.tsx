"use client";

import { ProjectCloseWizard } from "@/features/projects/components/ProjectCloseWizard";
import { useBizPermissions } from "@/features/business/lib/biz-permissions";
import { ProjectAiTab } from "@/features/projects/components/ProjectAiTab";
import { ProjectDeliverablesTab } from "@/features/projects/components/ProjectDeliverablesTab";
import { ProjectMembersTab } from "@/features/projects/components/ProjectMembersTab";
import { ProjectSuppliersTab } from "@/features/projects/components/ProjectSuppliersTab";
import { ProjectWorkPackagesTab } from "@/features/projects/components/ProjectWorkPackagesTab";
import type { ProjectDetailPageVm } from "@/features/projects/hooks/use-project-detail-page";
import { PROJECT_STATUS_LABELS, SERVICE_LINE_LABELS } from "@/features/projects/lib/biz-labels";
import type { BizProject } from "@/lib/types";

const TABS = [
  { id: "info" as const, label: "基本信息" },
  { id: "workpackages" as const, label: "工作包" },
  { id: "deliverables" as const, label: "交付物" },
  { id: "members" as const, label: "成员" },
  { id: "suppliers" as const, label: "供应商" },
  { id: "cost" as const, label: "成本" },
  { id: "ai" as const, label: "AI 服务" },
];

export function ProjectDetailView({ vm }: { vm: ProjectDetailPageVm }) {
  const { router, project, loading, error, tab, deliverables, members, costSummary, handleTabChange } = vm;

  if (loading) return <p className="text-sm text-ink-muted">加载中…</p>;
  if (error || !project) return <p className="text-sm text-red-600">{error || "项目不存在"}</p>;

  const tabLabel = (id: typeof TABS[number]["id"]) => {
    if (id === "workpackages") return `工作包 (${project.work_packages?.length ?? 0})`;
    if (id === "deliverables") return `交付物 (${deliverables.length})`;
    if (id === "members") return `成员 (${members.length})`;
    if (id === "suppliers") return "供应商";
    return TABS.find((t) => t.id === id)?.label ?? id;
  };

  return (
    <div>
      <button type="button" onClick={() => router.back()} className="mb-4 text-xs text-brand hover:underline">← 返回项目列表</button>

      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold text-ink">{project.name}</h1>
          {project.code && <p className="text-sm text-ink-muted">{project.code}</p>}
        </div>
        <span className={`rounded px-2 py-0.5 text-xs ${project.status === "active" ? "bg-brand-light text-brand" : project.status === "delivered" ? "bg-green-50 text-green-700" : project.status === "cancelled" ? "bg-red-50 text-red-600" : "bg-surface-muted text-ink-muted"}`}>
          {PROJECT_STATUS_LABELS[project.status] ?? project.status}
        </span>
      </div>

      <div className="mt-6 flex gap-1 overflow-x-auto border-b border-line">
        {TABS.map((t) => (
          <button key={t.id} type="button" className={`shrink-0 px-4 py-2 text-sm font-medium transition ${tab === t.id ? "-mb-px border-b-2 border-brand text-brand" : "text-ink-muted hover:text-ink"}`} onClick={() => handleTabChange(t.id)}>
            {tabLabel(t.id)}
          </button>
        ))}
      </div>

      {tab === "info" && <ProjectInfoTab project={project} vm={vm} />}
      {tab === "workpackages" && <ProjectWorkPackagesTab vm={vm} />}
      {tab === "deliverables" && <ProjectDeliverablesTab vm={vm} />}
      {tab === "members" && <ProjectMembersTab vm={vm} />}
      {tab === "suppliers" && <ProjectSuppliersTab vm={vm} />}
      {tab === "cost" && <ProjectCostTab costSummary={costSummary} />}
      {tab === "ai" && <ProjectAiTab vm={vm} />}
    </div>
  );
}

function ProjectInfoTab({ project, vm }: { project: BizProject; vm: ProjectDetailPageVm }) {
  const { canWriteProject } = useBizPermissions();
  const canClose = project.status !== "closed" && project.status !== "cancelled";

  return (
    <div className="mt-6 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-ink">基本信息</h2>
        {!vm.editingInfo && canWriteProject && (
          <button type="button" className="text-xs text-brand hover:underline" onClick={() => vm.setEditingInfo(true)}>编辑</button>
        )}
      </div>

      {vm.editingInfo ? (
        <form onSubmit={(e) => void vm.saveProjectInfo(e)} className="card space-y-3 p-4">
          <label>
            <span className="text-xs text-ink-muted">项目名称</span>
            <input className="input-field mt-1 w-full text-sm" value={vm.infoForm.name} onChange={(e) => vm.setInfoForm({ ...vm.infoForm, name: e.target.value })} required />
          </label>
          <div className="grid gap-3 sm:grid-cols-2">
            <label>
              <span className="text-xs text-ink-muted">项目编号</span>
              <input className="input-field mt-1 w-full text-sm" value={vm.infoForm.code} onChange={(e) => vm.setInfoForm({ ...vm.infoForm, code: e.target.value })} />
            </label>
            <label>
              <span className="text-xs text-ink-muted">状态</span>
              <select className="input-field mt-1 w-full text-sm" value={vm.infoForm.status} onChange={(e) => vm.setInfoForm({ ...vm.infoForm, status: e.target.value })}>
                {Object.entries(PROJECT_STATUS_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </label>
          </div>
          <label>
            <span className="text-xs text-ink-muted">总预算</span>
            <input type="number" min="0" step="0.01" className="input-field mt-1 w-full text-sm" value={vm.infoForm.total_budget} onChange={(e) => vm.setInfoForm({ ...vm.infoForm, total_budget: e.target.value })} />
          </label>
          <label>
            <span className="text-xs text-ink-muted">描述</span>
            <textarea className="input-field mt-1 w-full text-sm" rows={3} value={vm.infoForm.description} onChange={(e) => vm.setInfoForm({ ...vm.infoForm, description: e.target.value })} />
          </label>
          <div className="flex gap-2">
            <button type="submit" disabled={vm.savingInfo || !vm.infoForm.name.trim()} className="btn-primary text-sm">
              {vm.savingInfo ? "保存中…" : "保存"}
            </button>
            <button type="button" className="btn-sm-outline text-sm" onClick={() => vm.setEditingInfo(false)}>取消</button>
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

      {canClose && canWriteProject && (
        <div className="card flex flex-wrap items-center gap-3 p-4">
          <ProjectCloseWizard vm={vm} onDone={() => {}} />
          <p className="text-xs text-ink-muted">通过向导检查交付与工作包后再结项，可选案例入库。</p>
        </div>
      )}
    </div>
  );
}

function ProjectCostTab({ costSummary }: { costSummary: import("@/lib/types").BizProjectCostSummary | null }) {
  if (!costSummary) return <p className="mt-4 text-sm text-ink-muted">加载中…</p>;

  return (
    <div className="mt-4 space-y-4">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <InfoCard label="项目总预算" value={costSummary.total_budget != null ? `¥${costSummary.total_budget.toLocaleString()}` : "—"} />
        <InfoCard label="工作包预算合计" value={costSummary.work_package_budget_total != null ? `¥${costSummary.work_package_budget_total.toLocaleString()}` : "—"} />
        <InfoCard label="工作包实际合计" value={costSummary.work_package_actual_total != null ? `¥${costSummary.work_package_actual_total.toLocaleString()}` : "—"} />
        <InfoCard label="预算偏差" value={costSummary.budget_variance != null ? `¥${costSummary.budget_variance.toLocaleString()}` : "—"} />
      </div>
      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line text-left text-xs text-ink-muted">
              <th className="p-3">工作包</th>
              <th className="p-3">服务线</th>
              <th className="p-3">预算</th>
              <th className="p-3">实际</th>
              <th className="p-3">偏差</th>
            </tr>
          </thead>
          <tbody>
            {costSummary.work_packages.map((line) => (
              <tr key={line.id} className="border-b border-line last:border-0">
                <td className="p-3">{line.name}</td>
                <td className="p-3">{SERVICE_LINE_LABELS[line.service_line] ?? line.service_line}</td>
                <td className="p-3">{line.budget != null ? `¥${line.budget.toLocaleString()}` : "—"}</td>
                <td className="p-3">{line.actual_cost != null ? `¥${line.actual_cost.toLocaleString()}` : "—"}</td>
                <td className="p-3">{line.variance != null ? `¥${line.variance.toLocaleString()}` : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function InfoCard({ label, value }: { label: string; value: string }) {
  return <div className="card p-4"><p className="text-xs text-ink-faint">{label}</p><p className="mt-1 text-sm text-ink">{value}</p></div>;
}
