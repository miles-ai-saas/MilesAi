"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { BizMilestone, BizWorkPackage } from "@/lib/types";
import { SERVICE_LINE_LABELS, SERVICE_LINES, WP_STATUS_LABELS } from "@/features/projects/lib/biz-labels";
import type { ProjectDetailPageVm } from "@/features/projects/hooks/use-project-detail-page";

export function ProjectWorkPackagesTab({ vm }: { vm: ProjectDetailPageVm }) {
  const { project, projectId, updateWpStatus, advanceWpStage, refreshProject } = vm;
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
        <WorkPackageCard
          key={wp.id}
          wp={wp}
          projectId={projectId}
          updateWpStatus={updateWpStatus}
          advanceWpStage={advanceWpStage}
        />
      ))}
    </div>
  );
}

function WorkPackageCard({
  wp,
  projectId,
  updateWpStatus,
  advanceWpStage,
}: {
  wp: BizWorkPackage;
  projectId: string;
  updateWpStatus: (wp: BizWorkPackage, next: string) => Promise<void>;
  advanceWpStage: (wp: BizWorkPackage) => Promise<void>;
}) {
  const [expanded, setExpanded] = useState(false);
  const [milestones, setMilestones] = useState<BizMilestone[]>([]);
  const [msTitle, setMsTitle] = useState("");
  const [msDue, setMsDue] = useState("");
  const [loadingMs, setLoadingMs] = useState(false);
  const [advancing, setAdvancing] = useState(false);

  const loadMilestones = useCallback(async () => {
    const rows = await api.listMilestones(projectId, wp.id);
    setMilestones(rows);
  }, [projectId, wp.id]);

  useEffect(() => {
    if (expanded) void loadMilestones();
  }, [expanded, loadMilestones]);

  const handleAddMilestone = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!msTitle.trim()) return;
    setLoadingMs(true);
    try {
      await api.createMilestone(projectId, wp.id, { title: msTitle.trim(), due_date: msDue || undefined });
      setMsTitle("");
      setMsDue("");
      await loadMilestones();
    } finally {
      setLoadingMs(false);
    }
  };

  const toggleComplete = async (m: BizMilestone) => {
    await api.updateMilestone(projectId, wp.id, m.id, {
      completed_at: m.completed_at ? null : new Date().toISOString().slice(0, 10),
    });
    await loadMilestones();
  };

  const handleAdvance = async () => {
    setAdvancing(true);
    try {
      await advanceWpStage(wp);
    } finally {
      setAdvancing(false);
    }
  };

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
          {wp.stage && (
            <button type="button" className="text-xs text-brand hover:underline" disabled={advancing} onClick={() => void handleAdvance()}>
              {advancing ? "推进中…" : "推进阶段"}
            </button>
          )}
          {wp.status === "pending" && <button type="button" className="text-xs text-brand hover:underline" onClick={() => updateWpStatus(wp, "in_progress")}>开始</button>}
          {wp.status === "in_progress" && (<><button type="button" className="text-xs text-brand hover:underline" onClick={() => updateWpStatus(wp, "review")}>送审</button><button type="button" className="text-xs text-ink-muted hover:underline" onClick={() => updateWpStatus(wp, "done")}>完成</button></>)}
          {wp.status === "review" && <button type="button" className="text-xs text-brand hover:underline" onClick={() => updateWpStatus(wp, "done")}>通过</button>}
        </div>
      </div>
      {wp.stage && <p className="mt-1 text-xs text-ink-faint">阶段：{wp.stage}（序号 {wp.stage_index}）</p>}
      <div className="mt-2 flex gap-4 text-xs text-ink-muted">
        {wp.budget != null && <span>预算 ¥{wp.budget.toLocaleString()}</span>}
        {wp.actual_cost != null && <span>实际 ¥{wp.actual_cost.toLocaleString()}</span>}
        {wp.planned_start && <span>{wp.planned_start} ~ {wp.planned_end || "—"}</span>}
      </div>

      <button type="button" className="mt-3 text-xs text-brand hover:underline" onClick={() => setExpanded((v) => !v)}>
        {expanded ? "收起里程碑" : "里程碑"}
      </button>

      {expanded && (
        <div className="mt-3 border-t border-line pt-3">
          <form onSubmit={handleAddMilestone} className="flex flex-wrap items-end gap-2">
            <input className="input-field text-sm" placeholder="里程碑标题" value={msTitle} onChange={(e) => setMsTitle(e.target.value)} required />
            <input type="date" className="input-field text-sm" value={msDue} onChange={(e) => setMsDue(e.target.value)} />
            <button type="submit" disabled={loadingMs} className="btn-sm-outline text-xs">{loadingMs ? "…" : "添加"}</button>
          </form>
          {milestones.length === 0 ? (
            <p className="mt-2 text-xs text-ink-faint">暂无里程碑</p>
          ) : (
            <ul className="mt-2 space-y-1">
              {milestones.map((m) => (
                <li key={m.id} className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={!!m.completed_at} onChange={() => void toggleComplete(m)} />
                  <span className={m.completed_at ? "text-ink-muted line-through" : "text-ink"}>{m.title}</span>
                  {m.due_date && <span className="text-xs text-ink-faint">截止 {m.due_date}</span>}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
