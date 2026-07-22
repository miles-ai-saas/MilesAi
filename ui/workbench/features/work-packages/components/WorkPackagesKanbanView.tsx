"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { BizPageHero } from "@/features/business-dashboard/components/BizPageHero";
import { BizListPageSkeleton } from "@/features/business/components/BizListSkeleton";
import {
  SERVICE_LINES,
  SERVICE_LINE_LABELS,
} from "@/features/projects/lib/biz-labels";
import { StatChip } from "@/components/ui/StatChip";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
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
  }, [ready, load]);

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

  const clearFilters = useCallback(() => setServiceLine(""), []);

  return {
    items,
    loading,
    serviceLine,
    setServiceLine,
    clearFilters,
    hasActiveFilters: Boolean(serviceLine),
    load,
    updateStatus,
    updatingId,
    ready,
  };
}

export type WorkPackagesPageVm = ReturnType<typeof useWorkPackagesPage>;

function KanbanSkeleton() {
  return (
    <div className="grid gap-4 p-4 lg:grid-cols-4">
      {[1, 2, 3, 4].map((i) => (
        <div key={i} className="h-64 animate-pulse rounded-lg bg-surface-muted" />
      ))}
    </div>
  );
}

function WorkPackagesFilters({ vm }: { vm: WorkPackagesPageVm }) {
  const { serviceLine, setServiceLine, clearFilters, hasActiveFilters } = vm;

  return (
    <div className="border-b border-line bg-surface-muted/20 px-4 py-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-ink-muted">服务线</span>
        <button
          type="button"
          className={`rounded-full px-2.5 py-0.5 text-xs ${
            !serviceLine ? "bg-brand text-white" : "border border-line bg-surface text-ink-muted hover:text-ink"
          }`}
          onClick={() => setServiceLine("")}
        >
          全部
        </button>
        {SERVICE_LINES.map((item) => (
          <button
            key={item.key}
            type="button"
            className={`rounded-full px-2.5 py-0.5 text-xs ${
              serviceLine === item.key
                ? "bg-brand/10 font-medium text-brand ring-1 ring-brand/30"
                : "border border-line bg-surface text-ink-muted hover:border-brand/30 hover:text-ink"
            }`}
            onClick={() => setServiceLine(serviceLine === item.key ? "" : item.key)}
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

function KanbanColumn({
  status,
  label,
  count,
  items,
  updatingId,
  onDrop,
}: {
  status: string;
  label: string;
  count: number;
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
      className="flex min-h-[18rem] flex-col rounded-lg border border-line bg-surface-muted/30"
      onDragOver={handleDragOver}
      onDrop={handleDrop}
    >
      <div className="flex items-center justify-between border-b border-line px-3 py-2.5">
        <span className="text-xs font-semibold text-ink">{label}</span>
        <span className="rounded-full bg-surface px-2 py-0.5 text-[10px] tabular-nums text-ink-muted">{count}</span>
      </div>
      <div className="flex-1 space-y-2 overflow-y-auto p-2">
        {items.length === 0 ? (
          <p className="px-1 py-6 text-center text-xs text-ink-faint">暂无工作包</p>
        ) : (
          items.map((wp) => <KanbanCard key={wp.id} wp={wp} busy={updatingId === wp.id} />)
        )}
      </div>
    </div>
  );
}

function KanbanCard({ wp, busy }: { wp: BizWorkPackageKanban; busy: boolean }) {
  return (
    <div
      draggable={!busy}
      onDragStart={(e) => e.dataTransfer.setData("application/x-biz-wp", JSON.stringify(wp))}
      className={`rounded-lg border border-line bg-surface p-3 text-sm shadow-sm transition ${
        busy ? "cursor-wait opacity-60" : "cursor-grab hover:border-brand/30 active:cursor-grabbing"
      }`}
    >
      <Link
        href={`/business/projects/detail?id=${wp.project_id}&tab=workpackages`}
        className="font-medium text-ink hover:text-brand"
        onClick={(e) => e.stopPropagation()}
      >
        {wp.name}
      </Link>
      <p className="mt-1 truncate text-xs text-ink-muted">
        {wp.project_name} · {wp.client_name}
      </p>
      <div className="mt-2 flex flex-wrap gap-1.5 text-[10px] text-ink-faint">
        <span className="rounded-full bg-surface-muted px-1.5 py-0.5">
          {SERVICE_LINE_LABELS[wp.service_line] ?? wp.service_line}
        </span>
        {wp.stage ? <span>{wp.stage}</span> : null}
      </div>
    </div>
  );
}

export function WorkPackagesKanbanView({ vm }: { vm: WorkPackagesPageVm }) {
  const { items, loading, serviceLine, hasActiveFilters, updateStatus, updatingId, ready } = vm;

  const inProgressCount = useMemo(
    () => items.filter((i) => i.status === "in_progress").length,
    [items],
  );

  const serviceLineLabel = serviceLine ? SERVICE_LINE_LABELS[serviceLine] ?? serviceLine : "全部服务线";

  if (!ready) {
    return <BizListPageSkeleton />;
  }

  return (
    <div className="w-full">
      <BizPageHero
        flowStep="work-packages"
        title="工作包看板"
        subtitle="跨项目按状态查看工作包；拖拽卡片变更状态，项目内细节请在项目详情维护"
        compact
      />

      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <StatChip
          label="工作包总数"
          value={String(items.length)}
          hint={hasActiveFilters ? "当前筛选结果" : "全部服务线"}
        />
        <StatChip label="进行中" value={String(inProgressCount)} hint="in_progress 列" />
        <StatChip label="服务线筛选" value={serviceLineLabel} hint="点击 Chip 快速切换" />
      </div>

      <div className="card overflow-hidden">
        <WorkPackagesFilters vm={vm} />
        {loading ? (
          <KanbanSkeleton />
        ) : (
          <div className="grid gap-4 p-4 lg:grid-cols-4">
            {KANBAN_COLUMNS.map((col) => {
              const colItems = items.filter((i) => i.status === col.status);
              return (
                <KanbanColumn
                  key={col.status}
                  status={col.status}
                  label={col.label}
                  count={colItems.length}
                  items={colItems}
                  updatingId={updatingId}
                  onDrop={(wp) => void updateStatus(wp, col.status)}
                />
              );
            })}
          </div>
        )}
      </div>

      {!loading && items.length === 0 ? (
        <p className="mt-4 text-center text-sm text-ink-faint">
          {hasActiveFilters ? "当前服务线下暂无工作包，试试清除筛选" : "暂无工作包，请先在项目中创建"}
        </p>
      ) : null}
    </div>
  );
}
