"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/PageHeader";
import { DASHBOARD_PAGE_DESC, DASHBOARD_QUICK_LINKS, quotaLabel } from "@/lib/dashboard-shared";
import type { DashboardPageVm } from "@/hooks/use-dashboard-page";

export function DashboardOverview({ vm }: { vm: DashboardPageVm }) {
  if (vm.loading) {
    return <p className="text-sm text-ink-muted">加载概览…</p>;
  }

  return (
    <div className="resource-page-shell">
      <PageHeader title="工作台概览" description={DASHBOARD_PAGE_DESC} />

      <div className="resource-card-grid mb-8">
        {vm.statCards.map((c) => (
          <Link key={c.label} href={c.href} className="resource-card !min-h-[100px] flex-row items-center justify-between !p-4">
            <span className="text-sm text-ink-muted">{c.label}</span>
            <span className="text-2xl font-bold text-brand">{c.value}</span>
          </Link>
        ))}
      </div>

      {vm.quota && (
        <>
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-ink">资源配额</h2>
            <Link href="/system/quota" className="text-xs text-brand hover:underline">
              查看详情
            </Link>
          </div>
          <div className="resource-card-grid mb-8">
            {(
              [
                ["智能体", vm.quota.agents],
                ["流程", vm.quota.flows],
                ["知识库", vm.quota.knowledge_bases],
                ["存储", vm.quota.storage_mb],
              ] as const
            ).map(([label, metric]) => (
              <Link key={label} href="/system/quota" className="resource-card !min-h-[88px] flex-row items-center justify-between !p-4">
                <span className="text-sm text-ink-muted">{label}</span>
                <span className="text-sm tabular-nums font-medium text-ink">{quotaLabel(metric)}</span>
              </Link>
            ))}
          </div>
        </>
      )}

      <h2 className="mb-3 text-sm font-semibold text-ink">快捷入口</h2>
      <div className="resource-card-grid">
        {DASHBOARD_QUICK_LINKS.map((item) => (
          <Link key={item.href} href={item.href} className="resource-card">
            <p className="font-medium text-ink">{item.label}</p>
            <p className="mt-1 text-xs text-ink-muted">{item.desc}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
