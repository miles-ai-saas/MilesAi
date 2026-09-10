"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { adminApi } from "@/lib/api";
import { useRequireAdmin } from "@/lib/auth-store";

export default function DashboardPage() {
  const ready = useRequireAdmin();
  const [stats, setStats] = useState({
    tenants_total: 0,
    tenants_active: 0,
    risk_open: 0,
    bills_total: 0,
    audit_today: 0,
  });

  useEffect(() => {
    if (!ready) return;
    adminApi.getDashboardSummary().then((s) =>
      setStats({
        tenants_total: s.tenants_total,
        tenants_active: s.tenants_active,
        risk_open: s.risk_open,
        bills_total: s.bills_total,
        audit_today: s.audit_today,
      }),
    );
  }, [ready]);

  const cards = [
    { label: "租户总数", value: stats.tenants_total, href: "/tenants" },
    { label: "活跃租户", value: stats.tenants_active, href: "/tenants" },
    { label: "待处理风险", value: stats.risk_open, href: "/risk" },
    { label: "账单记录", value: stats.bills_total, href: "/billing/bills" },
    { label: "今日审计", value: stats.audit_today, href: "/audit" },
  ];

  return (
    <div className="admin-page-stack">
      <PageHeader title="控制台" description="平台租户、计费与风控数据一览" />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {cards.map((c) => (
          <Link key={c.label} href={c.href} className="card p-5 transition hover:border-brand/40">
            <p className="text-sm text-ink-muted">{c.label}</p>
            <p className="mt-2 text-3xl font-bold stat-value text-brand">{c.value}</p>
          </Link>
        ))}
      </div>
      <section className="card p-5">
        <h2 className="text-sm font-semibold text-ink">快捷操作</h2>
        <div className="mt-4 flex flex-wrap gap-3">
          <Link href="/tenants" className="btn-primary">
            管理租户
          </Link>
          <Link href="/billing/plans" className="btn-ghost">
            套餐管理
          </Link>
          <Link href="/billing/bills" className="btn-ghost">
            账单管理
          </Link>
          <Link href="/risk" className="btn-ghost">
            风控中心
          </Link>
        </div>
      </section>
    </div>
  );
}
