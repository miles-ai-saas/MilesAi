"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { BUSINESS_MAIN_FLOW, BUSINESS_RESOURCE_FLOW } from "@/features/business-dashboard/lib/business-flow";
import { PROJECT_STATUS_LABELS } from "@/features/projects/lib/biz-labels";
import { hasPermission } from "@/lib/permissions";
import { useAuthStore } from "@/lib/auth-store";
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
  const user = useAuthStore((s) => s.user);

  if (loading || !data) {
    return <p className="text-sm text-ink-muted">加载中…</p>;
  }

  const pendingPay = finance ? finance.total_pending_in + finance.total_pending_out : 0;
  const attentionItems = [
    {
      show: data.pending_deliverables > 0,
      label: "待验收交付物",
      value: data.pending_deliverables,
      href: (data.pending_deliverable_items?.[0])
        ? `/business/projects/${data.pending_deliverable_items[0].project_id}?tab=deliverables`
        : "/business/projects",
      hint: "进入项目交付物 Tab",
      color: "amber" as const,
    },
    {
      show: data.due_milestones > 0,
      label: "到期里程碑",
      value: data.due_milestones,
      href: (data.due_milestone_items?.[0])
        ? `/business/projects/${data.due_milestone_items[0].project_id}?tab=workpackages`
        : "/business/work-packages",
      hint: "查看工作包看板",
      color: "amber" as const,
    },
    {
      show: finance != null && pendingPay > 0,
      label: "待收付金额",
      value: pendingPay,
      href: "/business/finance",
      hint: "财务概览",
      color: "emerald" as const,
      formatAmount: true,
    },
  ].filter((i) => i.show);

  const quickLinks = [
    ...BUSINESS_MAIN_FLOW.filter((s) => !s.permission || hasPermission(user, s.permission)),
    ...(hasPermission(user, BUSINESS_RESOURCE_FLOW.permission!) ? [BUSINESS_RESOURCE_FLOW] : []),
  ];

  return (
    <div className="w-full">
      <header className="mb-6">
        <h1 className="text-xl font-semibold text-ink">业务工作台</h1>
      </header>

      {attentionItems.length > 0 && (
        <section className="mb-8">
          <h2 className="mb-3 text-sm font-semibold text-ink">待办关注</h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {attentionItems.map((item) => (
              <Link
                key={item.label}
                href={item.href}
                className="card flex flex-col gap-1 p-4 transition hover:shadow-md"
              >
                <span className="text-xs text-ink-muted">{item.label}</span>
                <span className={`text-2xl font-bold ${COLOR_MAP[item.color] ?? "text-ink"} inline-block rounded px-1`}>
                  {item.formatAmount ? `¥${item.value.toLocaleString()}` : item.value}
                </span>
                <span className="text-xs text-brand">{item.hint} →</span>
              </Link>
            ))}
          </div>
        </section>
      )}

      <section className="mb-8">
        <h2 className="mb-3 text-sm font-semibold text-ink">快捷入口</h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {quickLinks.map((link) => (
            <Link
              key={link.id}
              href={link.href}
              className="card p-4 transition hover:border-brand/30 hover:shadow-md"
            >
              <p className="font-medium text-ink">{link.label}</p>
              <p className="mt-1 text-xs text-ink-muted">{link.description}</p>
            </Link>
          ))}
        </div>
      </section>

      <section className="mb-8">
        <h2 className="mb-3 text-sm font-semibold text-ink">执行概览</h2>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="在制项目" value={data.active_projects} color="brand" href="/business/projects" />
          <StatCard label="待验收交付物" value={data.pending_deliverables} color="amber" href={data.pending_deliverable_items?.[0] ? `/business/projects/${data.pending_deliverable_items[0].project_id}?tab=deliverables` : "/business/projects"} />
          <StatCard label="进行中工作包" value={data.work_packages_in_progress} color="emerald" href="/business/work-packages" />
          <StatCard label="客户数" value={data.total_clients} color="slate" href="/business/clients" />
        </div>
      </section>

      {(data.pending_deliverable_items?.length ?? 0) > 0 && (
        <section className="mb-8">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-ink">待验收交付物</h2>
            <Link href="/business/projects" className="text-xs text-brand hover:underline">全部项目</Link>
          </div>
          <div className="space-y-2">
            {data.pending_deliverable_items?.map((d) => (
              <Link
                key={d.id}
                href={`/business/projects/${d.project_id}?tab=deliverables`}
                className="card flex items-center justify-between p-3 transition hover:shadow-md"
              >
                <div>
                  <p className="text-sm font-medium text-ink">{d.name}</p>
                  <p className="text-xs text-ink-muted">{d.project_name}</p>
                </div>
                <span className="text-xs text-amber-700">待验收 →</span>
              </Link>
            ))}
          </div>
        </section>
      )}

      {data.due_milestone_items.length > 0 && (
        <section className="mb-8">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-ink">里程碑提醒</h2>
            <Link href="/business/work-packages" className="text-xs text-brand hover:underline">工作包看板</Link>
          </div>
          <div className="space-y-2">
            {data.due_milestone_items.map((m) => (
              <Link
                key={m.id}
                href={`/business/projects/${m.project_id}?tab=workpackages`}
                className={`card flex items-center justify-between p-3 transition hover:shadow-md ${m.overdue ? "border-l-4 border-l-red-400" : ""}`}
              >
                <div>
                  <p className="text-sm font-medium text-ink">{m.title}</p>
                  <p className="text-xs text-ink-muted">{m.project_name}</p>
                </div>
                <span className={`text-xs ${m.overdue ? "text-red-600" : "text-amber-700"}`}>
                  {m.overdue ? "已逾期" : "即将到期"} · {m.due_date}
                </span>
              </Link>
            ))}
          </div>
        </section>
      )}

      {finance && hasPermission(user, "biz:finance:read") && (
        <section className="mb-8">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-ink">商务结算</h2>
            <Link href="/business/finance" className="text-xs text-brand hover:underline">财务概览</Link>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard label="合同总数" value={finance.contract_count} color="slate" href="/business/contracts" />
            <StatCard label="应收合计" value={finance.total_income} color="emerald" formatAmount href="/business/finance" />
            <StatCard label="已结清" value={finance.total_paid} color="brand" formatAmount href="/business/finance" />
            <StatCard label="待收付" value={pendingPay} color="amber" formatAmount href="/business/finance" />
          </div>
        </section>
      )}

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-ink">最近更新项目</h2>
          <Link href="/business/projects" className="text-xs text-brand hover:underline">全部项目</Link>
        </div>
        {data.recent_projects.length === 0 ? (
          <p className="text-sm text-ink-faint">暂无项目，可从商机赢单后转化</p>
        ) : (
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
        )}
      </section>
    </div>
  );
}

function StatCard({ label, value, color, formatAmount, href }: {
  label: string;
  value: number;
  color: string;
  formatAmount?: boolean;
  href?: string;
}) {
  const display = formatAmount ? `¥${value.toLocaleString()}` : String(value);
  const inner = (
    <>
      <p className="text-sm text-ink-muted">{label}</p>
      <p className={`mt-1 ${formatAmount ? "text-2xl" : "text-3xl"} font-bold ${COLOR_MAP[color] ?? "text-ink"}`}>{display}</p>
    </>
  );
  if (href) {
    return (
      <Link href={href} className="card block p-5 transition hover:shadow-md">
        {inner}
      </Link>
    );
  }
  return <div className="card p-5">{inner}</div>;
}
