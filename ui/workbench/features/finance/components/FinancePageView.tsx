"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { BizPageHero } from "@/features/business-dashboard/components/BizPageHero";
import type { BizPayment, FinancialSummary } from "@/lib/types";

const COLOR_MAP: Record<string, string> = {
  brand: "bg-brand-light text-brand",
  amber: "bg-amber-50 text-amber-700",
  emerald: "bg-emerald-50 text-emerald-700",
  slate: "bg-slate-100 text-slate-700",
};

const PAYMENT_STATUS_LABELS: Record<string, string> = {
  pending: "待处理",
  paid: "已结清",
  cancelled: "已取消",
};

export function useFinancePage() {
  const { ready } = useRequireAuth();
  const [summary, setSummary] = useState<FinancialSummary | null>(null);
  const [pending, setPending] = useState<BizPayment[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!ready) return;
    Promise.all([api.getFinancialSummary(), api.listPendingPayments()])
      .then(([s, p]) => { setSummary(s); setPending(p); })
      .finally(() => setLoading(false));
  }, [ready]);

  return { ready, summary, pending, loading };
}

export type FinancePageVm = ReturnType<typeof useFinancePage>;

export function FinancePageView({ vm }: { vm: FinancePageVm }) {
  const { summary, pending, loading } = vm;

  if (loading || !summary) {
    return <p className="text-sm text-ink-muted">加载中…</p>;
  }

  return (
    <div>
      <BizPageHero
        flowStep="finance"
        actions={<Link href="/business/contracts" className="btn-sm-outline text-sm">合同管理</Link>}
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <StatCard label="合同总数" value={summary.contract_count} color="slate" />
        <StatCard label="应收合计" value={summary.total_income} color="emerald" formatAmount />
        <StatCard label="已结清" value={summary.total_paid} color="brand" formatAmount />
        <StatCard label="待收款" value={summary.total_pending_in} color="amber" formatAmount />
        <StatCard label="待付款" value={summary.total_pending_out} color="amber" formatAmount />
      </div>

      <div className="mt-8">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-base font-medium text-ink">待收付清单</h2>
          <span className="text-xs text-ink-muted">{pending.length} 条</span>
        </div>
        {pending.length === 0 ? (
          <p className="text-sm text-ink-faint">暂无待收付记录</p>
        ) : (
          <div className="card overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs text-ink-muted">
                  <th className="p-3">名称</th>
                  <th className="p-3">方向</th>
                  <th className="p-3">金额</th>
                  <th className="p-3">计划日期</th>
                  <th className="p-3">状态</th>
                  <th className="p-3">操作</th>
                </tr>
              </thead>
              <tbody>
                {pending.map((p) => (
                  <tr key={p.id} className="border-b border-line last:border-0">
                    <td className="p-3">{p.name}</td>
                    <td className="p-3">{p.direction === "in" ? "收款" : "付款"}</td>
                    <td className="p-3">¥{p.amount.toLocaleString()}</td>
                    <td className="p-3">{p.planned_date ?? "—"}</td>
                    <td className="p-3">{PAYMENT_STATUS_LABELS[p.status] ?? p.status}</td>
                    <td className="p-3">
                      <Link href={`/business/contracts?id=${p.contract_id}`} className="text-xs text-brand hover:underline">
                        查看合同
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
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
