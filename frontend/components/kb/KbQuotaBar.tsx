"use client";

import type { KbQuota } from "@/lib/types";

function pct(used: number, max: number) {
  if (max <= 0) return 0;
  return Math.min(100, Math.round((used / max) * 100));
}

function Bar({ label, used, max, unit }: { label: string; used: number; max: number; unit: string }) {
  const p = pct(used, max);
  const warn = p >= 90;
  return (
    <div className="min-w-[10rem] flex-1">
      <div className="flex justify-between text-xs text-ink-muted">
        <span>{label}</span>
        <span className={warn ? "text-amber-700" : ""}>
          {used} / {max} {unit}
        </span>
      </div>
      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-surface-muted">
        <div
          className={`h-full rounded-full transition-all ${warn ? "bg-amber-500" : "bg-brand"}`}
          style={{ width: `${p}%` }}
        />
      </div>
    </div>
  );
}

type Props = {
  quota: KbQuota | null;
  loading?: boolean;
  className?: string;
};

export function KbQuotaBar({ quota, loading, className = "" }: Props) {
  if (loading) {
    return (
      <div className={`rounded-lg border border-line bg-surface-muted/50 px-4 py-3 text-sm text-ink-muted ${className}`}>
        加载配额…
      </div>
    );
  }
  if (!quota) return null;

  return (
    <div
      className={`flex flex-wrap items-center gap-4 rounded-lg border border-line bg-surface-muted/40 px-4 py-3 ${className}`}
    >
      <Bar
        label="知识库数量"
        used={quota.used_knowledge_bases}
        max={quota.max_knowledge_bases}
        unit="个"
      />
      <Bar label="存储空间" used={quota.used_storage_mb} max={quota.max_storage_mb} unit="MB" />
      <p className="w-full text-xs text-ink-faint sm:w-auto sm:shrink-0">
        单文件上限 {quota.max_file_mb} MB（含文档与附件）
      </p>
    </div>
  );
}
