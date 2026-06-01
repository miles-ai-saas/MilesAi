"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { BizPageHero } from "@/features/business-dashboard/components/BizPageHero";
import {
  BUSINESS_MAIN_FLOW,
  BUSINESS_RESOURCE_FLOW,
} from "@/features/business-dashboard/lib/business-flow";
import { PROJECT_STATUS_LABELS } from "@/features/projects/lib/biz-labels";
import { StatChip } from "@/components/ui/StatChip";
import { api } from "@/lib/api";
import { useRequireAuth, useAuthStore } from "@/lib/auth-store";
import { hasPermission } from "@/lib/permissions";
import type { DashboardSummary, FinancialSummary } from "@/lib/types";

const DELIVERY_TOOL_LINKS = [
  {
    id: "service-templates",
    label: "服务线模板",
    href: "/business/service-templates",
    description: "配置阶段流水线与 AI 助手",
    permission: "biz:project:read",
  },
  {
    id: "template-market",
    label: "模板市场",
    href: "/business/template-market",
    description: "浏览与应用行业模板",
    permission: "biz:project:read",
  },
] as const;

const STATUS_BADGE: Record<string, string> = {
  active: "bg-brand-light text-brand",
  delivered: "bg-emerald-50 text-emerald-700",
};

export function useBusinessDashboardPage() {
  const { ready } = useRequireAuth();
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [finance, setFinance] = useState<FinancialSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!ready) return;
    Promise.all([api.getDashboardSummary(), api.getFinancialSummary()])
      .then(([d, f]) => {
        setData(d);
        setFinance(f);
      })
      .finally(() => setLoading(false));
  }, [ready]);

  return { ready, data, finance, loading };
}

export type BusinessDashboardPageVm = ReturnType<typeof useBusinessDashboardPage>;

function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <div className="h-8 w-48 animate-pulse rounded-lg bg-surface-muted" />
        <div className="h-4 w-72 animate-pulse rounded bg-surface-muted" />
      </div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-24 animate-pulse rounded-xl bg-surface-muted" />
        ))}
      </div>
      <div className="grid gap-6 xl:grid-cols-12">
        <div className="h-80 animate-pulse rounded-xl bg-surface-muted xl:col-span-8" />
        <div className="h-80 animate-pulse rounded-xl bg-surface-muted xl:col-span-4" />
      </div>
    </div>
  );
}

function KpiLink({
  href,
  label,
  value,
  hint,
}: {
  href: string;
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <Link href={href} className="block transition hover:opacity-90">
      <StatChip label={label} value={value} hint={hint} />
    </Link>
  );
}

function SectionCard({
  title,
  action,
  children,
}: {
  title: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="card overflow-hidden">
      <div className="flex items-center justify-between border-b border-line bg-surface-muted/30 px-4 py-3">
        <h2 className="text-sm font-semibold text-ink">{title}</h2>
        {action}
      </div>
      <div className="p-4">{children}</div>
    </section>
  );
}

function AttentionBanner({
  items,
}: {
  items: Array<{
    label: string;
    value: string;
    href: string;
    hint: string;
    tone: "amber" | "emerald";
  }>;
}) {
  if (items.length === 0) return null;

  const toneClass = {
    amber: "border-amber-200 bg-amber-50/80 text-amber-800",
    emerald: "border-emerald-200 bg-emerald-50/80 text-emerald-800",
  };

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {items.map((item) => (
        <Link
          key={item.label}
          href={item.href}
          className={`rounded-xl border p-4 transition hover:shadow-md ${toneClass[item.tone]}`}
        >
          <p className="text-xs opacity-80">{item.label}</p>
          <p className="mt-1 text-2xl font-bold tabular-nums">{item.value}</p>
          <p className="mt-1 text-xs font-medium">{item.hint} →</p>
        </Link>
      ))}
    </div>
  );
}

function QuickNavList({
  links,
}: {
  links: Array<{ id: string; label: string; href: string; description: string }>;
}) {
  return (
    <ul className="divide-y divide-line-soft -mx-4 -my-4">
      {links.map((link) => (
        <li key={link.id}>
          <Link
            href={link.href}
            className="flex items-center justify-between gap-3 px-4 py-3 transition hover:bg-surface-muted/50"
          >
            <div className="min-w-0">
              <p className="text-sm font-medium text-ink">{link.label}</p>
              <p className="truncate text-xs text-ink-muted">{link.description}</p>
            </div>
            <span className="shrink-0 text-ink-faint" aria-hidden>
              →
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

function FinanceMiniGrid({
  finance,
  pendingPay,
}: {
  finance: FinancialSummary;
  pendingPay: number;
}) {
  const rows = [
    { label: "合同总数", value: String(finance.contract_count) },
    { label: "应收合计", value: `¥${finance.total_income.toLocaleString()}` },
    { label: "已结清", value: `¥${finance.total_paid.toLocaleString()}` },
    { label: "待收付", value: `¥${pendingPay.toLocaleString()}`, highlight: pendingPay > 0 },
  ];

  return (
    <dl className="grid grid-cols-2 gap-3">
      {rows.map((row) => (
        <div key={row.label} className="rounded-lg border border-line bg-surface-muted/30 px-3 py-2.5">
          <dt className="text-xs text-ink-muted">{row.label}</dt>
          <dd className={`mt-0.5 text-lg font-semibold tabular-nums ${row.highlight ? "text-amber-700" : "text-ink"}`}>
            {row.value}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export function BusinessDashboardView({ vm }: { vm: BusinessDashboardPageVm }) {
  const { data, finance, loading } = vm;
  const user = useAuthStore((s) => s.user);

  if (loading || !data) {
    return <DashboardSkeleton />;
  }

  const pendingPay = finance ? finance.total_pending_in + finance.total_pending_out : 0;
  const deliverableHref = data.pending_deliverable_items?.[0]
    ? `/business/projects/${data.pending_deliverable_items[0].project_id}?tab=deliverables`
    : "/business/projects";
  const milestoneHref = data.due_milestone_items?.[0]
    ? `/business/projects/${data.due_milestone_items[0].project_id}?tab=workpackages`
    : "/business/work-packages";

  const attentionItems = [
    {
      show: data.pending_deliverables > 0,
      label: "待验收交付物",
      value: String(data.pending_deliverables),
      href: deliverableHref,
      hint: "进入项目交付物",
      tone: "amber" as const,
    },
    {
      show: data.due_milestones > 0,
      label: "到期里程碑",
      value: String(data.due_milestones),
      href: milestoneHref,
      hint: "查看工作包看板",
      tone: "amber" as const,
    },
    {
      show: finance != null && pendingPay > 0,
      label: "待收付金额",
      value: `¥${pendingPay.toLocaleString()}`,
      href: "/business/finance",
      hint: "财务概览",
      tone: "emerald" as const,
    },
  ].filter((i) => i.show);

  const funnelLinks = BUSINESS_MAIN_FLOW.filter((s) => !s.permission || hasPermission(user, s.permission));
  const deliveryLinks = DELIVERY_TOOL_LINKS.filter((s) => !s.permission || hasPermission(user, s.permission));
  const resourceLinks = hasPermission(user, BUSINESS_RESOURCE_FLOW.permission!)
    ? [BUSINESS_RESOURCE_FLOW]
    : [];
  const quickLinks = [...funnelLinks, ...deliveryLinks, ...resourceLinks];

  const hasTodoLists =
    (data.pending_deliverable_items?.length ?? 0) > 0 || data.due_milestone_items.length > 0;

  return (
    <div className="w-full">
      <BizPageHero
        flowStep="dashboard"
        flowHighlight
        subtitle="销售漏斗、项目交付与商务结算一屏总览"
      />

      <div className="mb-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <KpiLink
          label="在制项目"
          value={String(data.active_projects)}
          hint="进行中与执行阶段"
          href="/business/projects"
        />
        <KpiLink
          label="待验收交付物"
          value={String(data.pending_deliverables)}
          hint="已提交待确认"
          href={deliverableHref}
        />
        <KpiLink
          label="进行中工作包"
          value={String(data.work_packages_in_progress)}
          hint="按服务线推进"
          href="/business/work-packages"
        />
        <KpiLink
          label="客户数"
          value={String(data.total_clients)}
          hint="全部有效客户"
          href="/business/clients"
        />
      </div>

      {attentionItems.length > 0 ? (
        <div className="mb-6">
          <AttentionBanner items={attentionItems} />
        </div>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-12">
        <div className="space-y-6 xl:col-span-8">
          {hasTodoLists ? (
            <SectionCard
              title="待办明细"
              action={
                <Link href="/business/work-packages" className="text-xs text-brand hover:underline">
                  工作包看板
                </Link>
              }
            >
              <div className="space-y-6">
                {(data.pending_deliverable_items?.length ?? 0) > 0 ? (
                  <div>
                    <h3 className="mb-2 text-xs font-medium text-ink-muted">待验收交付物</h3>
                    <ul className="space-y-2">
                      {data.pending_deliverable_items?.map((d) => (
                        <li key={d.id}>
                          <Link
                            href={`/business/projects/${d.project_id}?tab=deliverables`}
                            className="flex items-center justify-between rounded-lg border border-line px-3 py-2.5 transition hover:border-brand/30 hover:bg-surface-muted/40"
                          >
                            <div className="min-w-0">
                              <p className="truncate text-sm font-medium text-ink">{d.name}</p>
                              <p className="truncate text-xs text-ink-muted">{d.project_name}</p>
                            </div>
                            <span className="ml-3 shrink-0 text-xs text-amber-700">待验收</span>
                          </Link>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}

                {data.due_milestone_items.length > 0 ? (
                  <div>
                    <h3 className="mb-2 text-xs font-medium text-ink-muted">里程碑提醒</h3>
                    <ul className="space-y-2">
                      {data.due_milestone_items.map((m) => (
                        <li key={m.id}>
                          <Link
                            href={`/business/projects/${m.project_id}?tab=workpackages`}
                            className={`flex items-center justify-between rounded-lg border border-line px-3 py-2.5 transition hover:border-brand/30 hover:bg-surface-muted/40 ${
                              m.overdue ? "border-l-4 border-l-red-400" : ""
                            }`}
                          >
                            <div className="min-w-0">
                              <p className="truncate text-sm font-medium text-ink">{m.title}</p>
                              <p className="truncate text-xs text-ink-muted">{m.project_name}</p>
                            </div>
                            <span className={`ml-3 shrink-0 text-xs ${m.overdue ? "text-red-600" : "text-amber-700"}`}>
                              {m.overdue ? "已逾期" : "即将到期"} · {m.due_date}
                            </span>
                          </Link>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>
            </SectionCard>
          ) : (
            <SectionCard title="待办明细">
              <p className="py-6 text-center text-sm text-ink-faint">暂无待验收交付物或到期里程碑</p>
            </SectionCard>
          )}

          <SectionCard
            title="最近更新项目"
            action={
              <Link href="/business/projects" className="text-xs text-brand hover:underline">
                全部项目
              </Link>
            }
          >
            {data.recent_projects.length === 0 ? (
              <p className="py-6 text-center text-sm text-ink-faint">暂无项目，可从商机赢单后转化</p>
            ) : (
              <ul className="space-y-2">
                {data.recent_projects.map((p) => (
                  <li key={p.id}>
                    <Link
                      href={`/business/projects/${p.id}`}
                      className="flex items-center justify-between rounded-lg border border-line px-3 py-3 transition hover:border-brand/30 hover:bg-surface-muted/40"
                    >
                      <div className="min-w-0">
                        <p className="truncate font-medium text-ink">{p.name}</p>
                        <p className="truncate text-xs text-ink-muted">{p.client_name}</p>
                      </div>
                      <span
                        className={`ml-3 shrink-0 rounded-full px-2 py-0.5 text-xs ${
                          STATUS_BADGE[p.status] ?? "bg-surface-muted text-ink-muted"
                        }`}
                      >
                        {PROJECT_STATUS_LABELS[p.status] ?? p.status}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </SectionCard>
        </div>

        <aside className="space-y-6 xl:col-span-4">
          <SectionCard title="快捷入口">
            <QuickNavList links={quickLinks} />
          </SectionCard>

          {finance && hasPermission(user, "biz:finance:read") ? (
            <SectionCard
              title="商务结算"
              action={
                <Link href="/business/finance" className="text-xs text-brand hover:underline">
                  财务概览
                </Link>
              }
            >
              <FinanceMiniGrid finance={finance} pendingPay={pendingPay} />
            </SectionCard>
          ) : null}
        </aside>
      </div>
    </div>
  );
}
