"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { BizWorkPackage } from "@/lib/types";
import { SERVICE_LINE_LABELS, SERVICE_LINES, WP_STATUS_LABELS } from "@/features/projects/lib/biz-labels";
import type { ProjectDetailPageVm } from "@/features/projects/hooks/use-project-detail-page";

export function ProjectWorkPackagesTab({ vm }: { vm: ProjectDetailPageVm }) {
  const { project, projectId, updateWpStatus, refreshProject } = vm;
  const [serviceLine, setServiceLine] = useState("");
  const [wpName, setWpName] = useState("");
  const [saving, setSaving] = useState(false);

  if (!project) return null;

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!serviceLine || !wpName.trim()) return;
    setSaving(true);
    try {
      await api.createWorkPackage(projectId, { service_line: serviceLine, name: wpName.trim() });
      setServiceLine("");
      setWpName("");
      await refreshProject();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mt-4 space-y-4">
      <form onSubmit={handleAdd} className="card flex flex-wrap items-end gap-3 p-4">
        <label>
          <span className="text-xs text-ink-muted">服务线</span>
          <select className="input-field mt-1 text-sm" value={serviceLine} onChange={(e) => setServiceLine(e.target.value)} required>
            <option value="">— 请选择 —</option>
            {SERVICE_LINES.map((line) => <option key={line.key} value={line.key}>{line.label}</option>)}
          </select>
        </label>
        <label className="min-w-[12rem] flex-1">
          <span className="text-xs text-ink-muted">工作包名称</span>
          <input className="input-field mt-1 w-full text-sm" value={wpName} onChange={(e) => setWpName(e.target.value)} placeholder="如：主视觉设计" required />
        </label>
        <button type="submit" disabled={saving || !serviceLine || !wpName.trim()} className="btn-primary text-sm">{saving ? "添加中…" : "添加工作包"}</button>
      </form>

      {(project.work_packages ?? []).length === 0 && <p className="text-sm text-ink-faint">暂无工作包</p>}
      {project.work_packages?.map((wp) => (
        <WorkPackageCard key={wp.id} wp={wp} updateWpStatus={updateWpStatus} />
      ))}
    </div>
  );
}

function WorkPackageCard({ wp, updateWpStatus }: { wp: BizWorkPackage; updateWpStatus: (wp: BizWorkPackage, next: string) => Promise<void> }) {
  return (
    <div className="card p-4">
      <div className="flex items-start justify-between">
        <div>
          <span className="font-medium text-ink">{wp.name}</span>
          <span className="ml-2 rounded bg-surface-muted px-2 py-0.5 text-xs text-ink-muted">{SERVICE_LINE_LABELS[wp.service_line] ?? wp.service_line}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className={`rounded px-2 py-0.5 text-xs ${wp.status === "in_progress" ? "bg-brand-light text-brand" : wp.status === "done" ? "bg-green-50 text-green-700" : "bg-surface-muted text-ink-muted"}`}>
            {WP_STATUS_LABELS[wp.status] ?? wp.status}
          </span>
          {wp.status === "pending" && <button type="button" className="text-xs text-brand hover:underline" onClick={() => updateWpStatus(wp, "in_progress")}>开始</button>}
          {wp.status === "in_progress" && (<><button type="button" className="text-xs text-brand hover:underline" onClick={() => updateWpStatus(wp, "review")}>送审</button><button type="button" className="text-xs text-ink-muted hover:underline" onClick={() => updateWpStatus(wp, "done")}>完成</button></>)}
          {wp.status === "review" && <button type="button" className="text-xs text-brand hover:underline" onClick={() => updateWpStatus(wp, "done")}>通过</button>}
        </div>
      </div>
      {wp.stage && <p className="mt-1 text-xs text-ink-faint">阶段：{wp.stage}</p>}
      <div className="mt-2 flex gap-4 text-xs text-ink-muted">
        {wp.budget != null && <span>预算 ¥{wp.budget.toLocaleString()}</span>}
        {wp.actual_cost != null && <span>实际 ¥{wp.actual_cost.toLocaleString()}</span>}
        {wp.planned_start && <span>{wp.planned_start} ~ {wp.planned_end || "—"}</span>}
      </div>
    </div>
  );
}
