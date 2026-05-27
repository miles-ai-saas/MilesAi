"use client";

/** 知识库配额条（链路 §8，`api.getKbQuota`）。 */
import type { KbQuota } from "@/lib/types";

function pct(used: number, max: number) {
  if (max <= 0) return 0;
  return Math.min(100, Math.round((used / max) * 100));
}

function InlineStat({
  label,
  used,
  max,
  unit,
}: {
  label: string;
  used: number;
  max: number;
  unit: string;
}) {
  const p = pct(used, max);
  const warn = p >= 90;
  return (
    <span
      className={`whitespace-nowrap ${warn ? "font-medium text-amber-800" : "text-ink-muted"}`}
      title={`${label}：${used} / ${max} ${unit}${warn ? "（即将用尽）" : ""}`}
    >
      {label} {used}/{max}
      {unit}
    </span>
  );
}

type Props = {
  quota: KbQuota | null;
  loading?: boolean;
  className?: string;
  /** inline：列表页标题栏旁；detail：详情页标题区一行摘要 */
  variant?: "inline" | "detail";
};

export function KbQuotaBar({ quota, loading, className = "", variant = "inline" }: Props) {
  if (loading) {
    return (
      <span className={`text-xs text-ink-faint ${className}`} aria-busy>
        配额加载中…
      </span>
    );
  }
  if (!quota) return null;

  if (variant === "inline") {
    return (
      <div
        className={`flex flex-wrap items-center gap-x-3 gap-y-1 text-xs ${className}`}
        aria-label="租户知识库配额"
      >
        <InlineStat
          label="库"
          used={quota.used_knowledge_bases}
          max={quota.max_knowledge_bases}
          unit=""
        />
        <span className="text-ink-faint" aria-hidden>
          ·
        </span>
        <InlineStat label="存储" used={quota.used_storage_mb} max={quota.max_storage_mb} unit="MB" />
        <span className="hidden text-ink-faint lg:inline" title="单文件上传上限">
          · 单文件 ≤{quota.max_file_mb}MB
        </span>
      </div>
    );
  }

  const kbPct = pct(quota.used_knowledge_bases, quota.max_knowledge_bases);
  const storePct = pct(quota.used_storage_mb, quota.max_storage_mb);
  const kbWarn = kbPct >= 90;
  const storeWarn = storePct >= 90;

  return (
    <p className={`text-xs text-ink-faint ${className}`}>
      租户配额：
      <span className={kbWarn ? "text-amber-800" : "text-ink-muted"}>
        {" "}
        知识库 {quota.used_knowledge_bases}/{quota.max_knowledge_bases}
      </span>
      <span className="text-ink-faint"> · </span>
      <span className={storeWarn ? "text-amber-800" : "text-ink-muted"}>
        存储 {quota.used_storage_mb}/{quota.max_storage_mb} MB
      </span>
      <span className="text-ink-faint"> · 单文件 ≤{quota.max_file_mb} MB</span>
    </p>
  );
}
