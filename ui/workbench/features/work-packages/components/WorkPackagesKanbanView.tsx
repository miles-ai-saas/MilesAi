"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { SERVICE_LINE_LABELS, WP_STATUS_LABELS } from "@/features/projects/lib/biz-labels";
import type { BizWorkPackageKanban } from "@/lib/types";

const KANBAN_COLUMNS = [
  { status: "pending", label: "待开始" },
  { status: "in_progress", label: "进行中" },
  { status: "review", label: "审核中" },
  { status: "done", label: "已完成" },
] as const;

export function useWorkPackagesPage() {
  const { ready } = useRequireAuth();
  const [items, setItems] = useState<BizWorkPackageKanban[]>([]);
  const [loading, setLoading] = useState(true);
  const [serviceLine, setServiceLine] = useState("");
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    const data = await api.listWorkPackagesKanban(undefined, serviceLine || undefined);
    setItems(data.filter((i) => i.status !== "cancelled"));
  }, [serviceLine]);

  useEffect(() => {
    if (!ready) return;
    setLoading(true);
    load().finally(() => setLoading(false));
  }, [ready, load, serviceLine]);

  const updateStatus = async (wp: BizWorkPackageKanban, status: string) => {
    if (wp.status === status) return;
    setUpdatingId(wp.id);
    try {
      await api.updateWorkPackage(wp.project_id, wp.id, { status });
      await load();
    } finally {
      setUpdatingId(null);
    }
  };

  return { items, loading, serviceLine, setServiceLine, load, updateStatus, updatingId, ready };
}

export type WorkPackagesPageVm = ReturnType<typeof useWorkPackagesPage>;

export function WorkPackagesKanbanView({ vm }: { vm: WorkPackagesPageVm }) {
  const { items, loading, serviceLine, setServiceLine, updateStatus, updatingId } = vm;

  if (loading) return <p className="text-sm text-ink-muted">加载中…</p>;

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-ink">工作包看板</h1>
          <p className="mt-1 text-sm text-ink-muted">按状态查看跨项目工作包，拖拽卡片可变更状态</p>
        </div>
        <label>
          <span className="text-xs text-ink-muted">服务线筛选</span>
          <select className="input-field mt-1 text-sm" value={serviceLine} onChange={(e) => setServiceLine(e.target.value)}>
            <option value="">全部</option>
            {Object.entries(SERVICE_LINE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
      </div>

      <div className="grid gap-4 lg:grid-cols-4">
        {KANBAN_COLUMNS.map((col) => {
          const colItems = items.filter((i) => i.status === col.status);
          return (
            <KanbanColumn
              key={col.status}
              status={col.status}
              label={`${col.label} (${colItems.length})`}
              items={colItems}
              updatingId={updatingId}
              onDrop={(wp) => void updateStatus(wp, col.status)}
            />
          );
        })}
      </div>
    </div>
  );
}

function KanbanColumn({ status, label, items, updatingId, onDrop }: {
  status: string;
  label: string;
  items: BizWorkPackageKanban[];
  updatingId: string | null;
  onDrop: (wp: BizWorkPackageKanban) => void;
}) {
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const raw = e.dataTransfer.getData("application/x-biz-wp");
    if (!raw) return;
    const wp = JSON.parse(raw) as BizWorkPackageKanban;
    if (wp.status !== status) onDrop(wp);
  };

  return (
    <div
      className="min-h-[16rem] rounded-lg border border-line bg-surface-muted/40 p-3"
      onDragOver={handleDragOver}
      onDrop={handleDrop}
    >
      <h2 className="mb-3 text-sm font-medium text-ink">{label}</h2>
      <div className="space-y-2">
        {items.length === 0 && <p className="text-xs text-ink-faint">无</p>}
        {items.map((wp) => (
          <KanbanCard key={wp.id} wp={wp} busy={updatingId === wp.id} />
        ))}
      </div>
    </div>
  );
}

function KanbanCard({ wp, busy }: { wp: BizWorkPackageKanban; busy: boolean }) {
  return (
    <div
      draggable={!busy}
      onDragStart={(e) => e.dataTransfer.setData("application/x-biz-wp", JSON.stringify(wp))}
      className={`card cursor-grab p-3 text-sm active:cursor-grabbing ${busy ? "opacity-60" : ""}`}
    >
      <Link href={`/business/projects/${wp.project_id}`} className="font-medium text-ink hover:text-brand" onClick={(e) => e.stopPropagation()}>
        {wp.name}
      </Link>
      <p className="mt-1 text-xs text-ink-muted">{wp.project_name} · {wp.client_name}</p>
      <p className="mt-1 text-xs text-ink-faint">
        {SERVICE_LINE_LABELS[wp.service_line] ?? wp.service_line}
        {wp.stage ? ` · ${wp.stage}` : ""}
      </p>
      <p className="mt-1 text-[10px] text-ink-faint">{WP_STATUS_LABELS[wp.status] ?? wp.status}</p>
    </div>
  );
}
