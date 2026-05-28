"use client";

/** 租户资源配额只读页（链路 §3）。 */

import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import type { QuotaMetric, TenantQuota } from "@/lib/types";

function pct(used: number, max: number) {
  if (max <= 0) return 0;
  return Math.min(100, Math.round((used / max) * 100));
}

function QuotaCard({ title, metric, hint }: { title: string; metric: QuotaMetric; hint?: string }) {
  const unlimited = metric.max <= 0;
  const p = unlimited ? 0 : pct(metric.used, metric.max);
  const warn = !unlimited && p >= 90;

  return (
    <div className="card p-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-ink">{title}</h3>
          {hint && <p className="mt-0.5 text-xs text-ink-faint">{hint}</p>}
        </div>
        <span className={`text-sm tabular-nums ${warn ? "font-medium text-amber-800" : "text-ink-muted"}`}>
          {metric.used}
          {unlimited ? "" : ` / ${metric.max}`}
          {metric.unit ? ` ${metric.unit}` : ""}
        </span>
      </div>
      {!unlimited && (
        <div className="mt-3 h-2 overflow-hidden rounded-full bg-surface-muted">
          <div className={`h-full rounded-full transition-all ${warn ? "bg-amber-500" : "bg-brand"}`} style={{ width: `${p}%` }} />
        </div>
      )}
      {unlimited && <p className="mt-2 text-xs text-ink-faint">当前未设置上限</p>}
    </div>
  );
}

export default function SystemQuotaPage() {
  const { ready } = useRequireAuth();
  const [quota, setQuota] = useState<TenantQuota | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!ready) return;
    setLoading(true);
    setError("");
    api
      .getSystemQuota()
      .then(setQuota)
      .catch((e: Error) => setError(e.message || "加载失败"))
      .finally(() => setLoading(false));
  }, [ready]);

  return (
    <div className="w-full space-y-6">
      <PageHeader title="资源配额" description="查看本租户资源使用与上限。配额调整请联系平台管理员（运营后台）。" />

      {loading && <p className="text-sm text-ink-muted">加载中…</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {quota && (
        <div className="grid gap-4 sm:grid-cols-2">
          <QuotaCard title="知识库" metric={quota.knowledge_bases} />
          <QuotaCard title="存储空间" metric={quota.storage_mb} hint="文档与附件合计" />
          <QuotaCard title="智能体" metric={quota.agents} />
          <QuotaCard title="流程" metric={quota.flows} />
          <QuotaCard title="本月 Token" metric={quota.tokens_monthly} />
          <QuotaCard title="今日生成次数" metric={quota.generative_daily} hint="生图 / 生视频" />
        </div>
      )}

      <p className="text-xs text-ink-faint">如需提升配额，请联系平台管理员在运营后台调整租户套餐或配额上限。</p>
    </div>
  );
}
