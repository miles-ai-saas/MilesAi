"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { PROJECT_STATUS_LABELS } from "@/features/projects/lib/biz-labels";
import type { DashboardSummary, FinancialSummary } from "@/lib/types";

const COLOR_MAP: Record<string, string> = {
  brand: "bg-brand-light text-brand",
  amber: "bg-amber-50 text-amber-700",
  emerald: "bg-emerald-50 text-emerald-700",
  slate: "bg-slate-100 text-slate-700",
};

export function useBusinessDashboardPage() {
  const { ready } = useRequireAuth();
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [finance, setFinance] = useState<FinancialSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!ready) return;
    Promise.all([api.getDashboardSummary(), api.getFinancialSummary()])
      .then(([d, f]) => { setData(d); setFinance(f); })
      .finally(() => setLoading(false));
  }, [ready]);

  return { ready, data, finance, loading };
}

export type BusinessDashboardPageVm = ReturnType<typeof useBusinessDashboardPage>;

export function BusinessDashboardView({ vm }: { vm: BusinessDashboardPageVm }) {
  const { data, finance, loading } = vm;

  if (loading || !data) {
    return <p className="text-sm text-ink-muted">加载中…</p>;
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-ink">业务仪表盘</h1>
        <p className="mt-1 text-sm text-ink-muted">在制项目、待验收交付物与工作包进度概览</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="在制项目" value={data.active_projects} color="brand" />
        <StatCard label="待验收交付物" value={data.pending_deliverables} color="amber" />
        <StatCard label="进行中工作包" value={data.work_packages_in_progress} color="emerald" />
        <StatCard label="客户数" value={data.total_clients} color="slate" />
      </div>

      {finance && (
        <div className="mt-8">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-base font-medium text-ink">财务概览</h2>
            <Link href="/business/contracts" className="text-xs text-brand hover:underline">合同管理</Link>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard label="合同总数" value={finance.contract_count} color="slate" />
            <StatCard label="应收合计" value={finance.total_income} color="emerald" formatAmount />
            <StatCard label="已结清" value={finance.total_paid} color="brand" formatAmount />
            <StatCard label="待收付" value={finance.total_pending_in + finance.total_pending_out} color="amber" formatAmount />
          </div>
        </div>
      )}

      <div className="mt-8">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-base font-medium text-ink">最近更新项目</h2>
          <Link href="/business/projects" className="text-xs text-brand hover:underline">查看全部</Link>
        </div>
        {data.recent_projects.length === 0 && <p className="text-sm text-ink-faint">暂无项目</p>}
        <div className="space-y-2">
          {data.recent_projects.map((p) => (
            <Link key={p.id} href={`/business/projects/${p.id}`} className="card flex items-center justify-between p-4 transition hover:shadow-md">
              <div>
                <p className="font-medium text-ink">{p.name}</p>
                <p className="text-xs text-ink-muted">{p.client_name}</p>
              </div>
              <span className={`rounded px-2 py-0.5 text-xs ${
                p.status === "active" ? "bg-brand-light text-brand" :
                p.status === "delivered" ? "bg-green-50 text-green-700" :
                "bg-surface-muted text-ink-muted"
              }`}>
                {PROJECT_STATUS_LABELS[p.status] ?? p.status}
              </span>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value, color, formatAmount }: { label: string; value: number; color: string; formatAmount?: boolean }) {
  const display = formatAmount ? `¥${value.toLocaleString()}` : String(value);
  return (
    <div className="card p-5">
      <p className="text-sm text-ink-muted">{label}</p>
      <p className={`mt-1 ${formatAmount ? "text-2xl" : "text-3xl"} font-bold ${COLOR_MAP[color] ?? "text-ink"}`}>{display}</p>
    </div>
  );
}
