"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { BizProjectActivityItem } from "@/lib/types";
import type { ProjectDetailPageVm } from "@/features/projects/hooks/use-project-detail-page";

export function ProjectActivityTab({ vm }: { vm: ProjectDetailPageVm }) {
  const { projectId } = vm;
  const [items, setItems] = useState<BizProjectActivityItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.listProjectActivity(projectId)
      .then(setItems)
      .finally(() => setLoading(false));
  }, [projectId]);

  if (loading) return <p className="mt-4 text-sm text-ink-muted">加载动态…</p>;
  if (items.length === 0) return <p className="mt-4 text-sm text-ink-faint">暂无业务操作记录</p>;

  return (
    <div className="mt-4 space-y-2">
      {items.map((item) => (
        <div key={item.id} className="card p-3 text-sm">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="font-medium text-ink">{item.label}</span>
            <span className="text-xs text-ink-muted">{formatTime(item.created_at)}</span>
          </div>
          <p className="mt-1 text-xs text-ink-faint">
            {item.username ?? "系统"}
            {item.action === "biz.milestone.due_reminder" && item.detail?.due_date
              ? ` · 到期 ${String(item.detail.due_date)}`
              : item.detail?.name
                ? ` · ${String(item.detail.name)}`
                : item.detail?.title
                  ? ` · ${String(item.detail.title)}`
                  : ""}
          </p>
        </div>
      ))}
    </div>
  );
}

function formatTime(iso: string): string {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleString("zh-CN", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  } catch {
    return iso.slice(0, 16);
  }
}
