"use client";

import Link from "next/link";
import type { BillingPlansPageVm } from "@/hooks/use-billing-plans-page";

export function BillingPlansCreateSection({ vm }: { vm: BillingPlansPageVm }) {
  const { showPlanForm, planCode, setPlanCode, planName, setPlanName, planPrice, setPlanPrice, onCreatePlan } = vm;
  if (!showPlanForm) return null;

  return (
    <section className="card mb-6 p-4">
      <h2 className="text-sm font-semibold text-ink">新建套餐</h2>
      <div className="mt-3 grid gap-2 sm:grid-cols-3">
        <input className="input-field" placeholder="code（如 pro）" value={planCode} onChange={(e) => setPlanCode(e.target.value)} />
        <input className="input-field" placeholder="名称" value={planName} onChange={(e) => setPlanName(e.target.value)} />
        <input className="input-field" placeholder="月费（元）" value={planPrice} onChange={(e) => setPlanPrice(e.target.value)} />
      </div>
      <button type="button" className="btn-primary mt-3" onClick={() => void onCreatePlan()}>
        保存套餐
      </button>
    </section>
  );
}

export function BillingPlansGridSection({ vm }: { vm: BillingPlansPageVm }) {
  const { plans, togglePlanActive } = vm;

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {plans.map((p) => (
        <div key={p.id} className="card p-4 text-sm">
          <Link href={`/billing/plans/${p.id}`} className="font-bold text-ink hover:text-brand">
            {p.name}
          </Link>
          <p className="mt-1 font-mono text-xs cell-muted">{p.code}</p>
          <p className="mt-2 cell-numeric text-brand">¥{p.price_monthly}/月</p>
          <p className="mt-1 cell-numeric text-xs cell-muted">
            {p.max_storage_mb.toLocaleString()} MB · {p.max_tokens_monthly.toLocaleString()} Token
          </p>
          {!p.is_active && <span className="mt-2 inline-block text-xs text-ink-faint">已停用</span>}
          <div className="mt-3 flex flex-wrap gap-3">
            <Link href={`/billing/plans/${p.id}`} className="text-xs text-brand hover:underline">
              查看详情
            </Link>
            <button type="button" className="text-xs cell-muted hover:text-brand" onClick={() => void togglePlanActive(p)}>
              {p.is_active ? "停用" : "启用"}
            </button>
          </div>
        </div>
      ))}
      {plans.length === 0 && <p className="text-sm cell-muted">暂无套餐</p>}
    </div>
  );
}
