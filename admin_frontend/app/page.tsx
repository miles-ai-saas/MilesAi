"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { adminApi } from "@/lib/api";
import { useRequireAdmin } from "@/lib/auth-store";

export default function DashboardPage() {
  const ready = useRequireAdmin();
  const [stats, setStats] = useState({
    tenants: 0,
    activeTenants: 0,
    openRisks: 0,
    bills: 0,
    auditToday: 0,
  });

  useEffect(() => {
    if (!ready) return;
    Promise.all([
      adminApi.listTenants(1, 100),
      adminApi.listRiskEvents(),
      adminApi.listBills(),
      adminApi.listAuditLogs(),
    ]).then(([tenants, risks, bills, logs]) => {
      const today = new Date().toISOString().slice(0, 10);
      setStats({
        tenants: tenants.total,
        activeTenants: tenants.items.filter((t) => t.status === "active").length,
        openRisks: risks.items.filter((r) => !r.is_resolved).length,
        bills: bills.total,
        auditToday: logs.items.filter((l) => l.created_at.startsWith(today)).length,
      });
    });
  }, [ready]);

  const cards = [
    { label: "租户总数", value: stats.tenants, href: "/tenants" },
    { label: "活跃租户", value: stats.activeTenants, href: "/tenants" },
    { label: "待处理风险", value: stats.openRisks, href: "/risk" },
    { label: "账单记录", value: stats.bills, href: "/billing" },
    { label: "今日审计", value: stats.auditToday, href: "/audit" },
  ];

  return (
    <div>
      <PageHeader
        title="控制台"
        description="平台租户、计费与风控数据一览"
      />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {cards.map((c) => (
          <Link key={c.label} href={c.href} className="card p-5 transition hover:border-brand/40">
            <p className="text-sm text-ink-muted">{c.label}</p>
            <p className="mt-2 text-3xl font-bold text-brand">{c.value}</p>
          </Link>
        ))}
      </div>
      <section className="card mt-8 p-5">
        <h2 className="text-sm font-semibold text-ink">快捷操作</h2>
        <div className="mt-4 flex flex-wrap gap-3">
          <Link href="/tenants" className="btn-primary">
            管理租户
          </Link>
          <Link href="/billing" className="btn-ghost">
            查看计费
          </Link>
          <Link href="/risk" className="btn-ghost">
            风控中心
          </Link>
        </div>
      </section>
    </div>
  );
}
