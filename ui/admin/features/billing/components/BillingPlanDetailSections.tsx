"use client";

import Link from "next/link";
import { AdminDetailHeader } from "@/components/layout/AdminDetailHeader";
import { BillingPlanDetailField } from "@/features/billing/components/BillingPlanDetailField";
import type { BillingPlanDetailPageVm } from "@/features/billing/hooks/use-billing-plan-detail-page";

export function BillingPlanDetailHeaderSection({ vm }: { vm: BillingPlanDetailPageVm }) {
  const { plan, tenantTotal, saving, onSave } = vm;
  if (!plan) return null;

  return (
    <AdminDetailHeader
      backHref="/billing/plans"
      backLabel="返回套餐列表"
      title={plan.name}
      badges={
        <>
          <span className="badge bg-brand-light font-mono text-xs text-ink">{plan.code}</span>
          <span className={`status-badge ${plan.is_active ? "status-badge-published" : "status-badge-deprecated"}`}>
            {plan.is_active ? "启用中" : "已停用"}
          </span>
        </>
      }
      description={
        <span className="cell-numeric">
          ¥{plan.price_monthly}/月 · 绑定租户 {tenantTotal} 个
        </span>
      }
      action={
        <button type="button" className="btn-primary" disabled={saving} onClick={() => void onSave()}>
          {saving ? "保存中…" : "保存更改"}
        </button>
      }
    />
  );
}

export function BillingPlanDetailStatsSection({ vm }: { vm: BillingPlanDetailPageVm }) {
  const { plan, tenantTotal } = vm;
  if (!plan) return null;

  const stats = [
    { label: "月费", value: `¥${plan.price_monthly}` },
    { label: "Token 月额度", value: plan.max_tokens_monthly.toLocaleString() },
    { label: "存储上限", value: `${plan.max_storage_mb.toLocaleString()} MB` },
    { label: "绑定租户", value: String(tenantTotal) },
  ];

  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {stats.map((s) => (
        <div key={s.label} className="card p-4">
          <p className="text-xs cell-muted">{s.label}</p>
          <p className="mt-1 text-xl font-bold stat-value text-brand">{s.value}</p>
        </div>
      ))}
    </div>
  );
}

export function BillingPlanDetailFormSections({ vm }: { vm: BillingPlanDetailPageVm }) {
  const { form, setForm } = vm;
  if (!form) return null;

  return (
    <>
      <section className="card p-5">
        <h2 className="text-sm font-semibold text-ink">基本信息</h2>
        <div className="mt-4 space-y-3">
          <BillingPlanDetailField label="套餐名称">
            <input className="input-field" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </BillingPlanDetailField>
          <BillingPlanDetailField label="描述">
            <textarea
              className="input-field min-h-[72px] resize-y"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </BillingPlanDetailField>
          <BillingPlanDetailField label="月费（元）">
            <input className="input-field max-w-[12rem]" value={form.price_monthly} onChange={(e) => setForm({ ...form, price_monthly: e.target.value })} />
          </BillingPlanDetailField>
        </div>
      </section>

      <section className="card p-5">
        <h2 className="text-sm font-semibold text-ink">默认配额</h2>
        <p className="mt-1 text-xs cell-muted">租户绑定此套餐时将同步以下上限（可在租户详情单独调整）。</p>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <BillingPlanDetailField label="Token 月额度">
            <input
              type="number"
              className="input-field"
              value={form.max_tokens_monthly}
              onChange={(e) => setForm({ ...form, max_tokens_monthly: Number(e.target.value) })}
            />
          </BillingPlanDetailField>
          <BillingPlanDetailField label="存储 MB">
            <input
              type="number"
              className="input-field"
              value={form.max_storage_mb}
              onChange={(e) => setForm({ ...form, max_storage_mb: Number(e.target.value) })}
            />
          </BillingPlanDetailField>
          <BillingPlanDetailField label="知识库数量">
            <input
              type="number"
              className="input-field"
              value={form.max_knowledge_bases}
              onChange={(e) => setForm({ ...form, max_knowledge_bases: Number(e.target.value) })}
            />
          </BillingPlanDetailField>
          <BillingPlanDetailField label="智能体数量">
            <input type="number" className="input-field" value={form.max_agents} onChange={(e) => setForm({ ...form, max_agents: Number(e.target.value) })} />
          </BillingPlanDetailField>
          <BillingPlanDetailField label="流程数量">
            <input type="number" className="input-field" value={form.max_flows} onChange={(e) => setForm({ ...form, max_flows: Number(e.target.value) })} />
          </BillingPlanDetailField>
        </div>
      </section>
    </>
  );
}

export function BillingPlanDetailAside({ vm }: { vm: BillingPlanDetailPageVm }) {
  const { plan, tenants, tenantTotal, onToggleActive } = vm;
  if (!plan) return null;

  return (
    <aside className="space-y-4">
      <section className="card p-5">
        <h2 className="text-sm font-semibold text-ink">状态</h2>
        <p className="mt-1 text-xs cell-muted">停用后不可新绑租户；已绑定租户不受影响。</p>
        <button type="button" className="btn-ghost mt-4 w-full" onClick={() => void onToggleActive()}>
          {plan.is_active ? "停用套餐" : "重新启用"}
        </button>
      </section>

      <section className="card p-5">
        <h2 className="text-sm font-semibold text-ink">绑定租户</h2>
        {tenants.length === 0 ? (
          <p className="mt-3 text-sm cell-muted">暂无租户使用此套餐</p>
        ) : (
          <ul className="admin-data-list mt-3">
            {tenants.map((t) => (
              <li key={t.id} className="admin-data-row">
                <Link href={`/tenants/detail?id=${t.id}`} className="cell-primary hover:text-brand">
                  {t.name}
                </Link>
              </li>
            ))}
          </ul>
        )}
        {tenantTotal > tenants.length && (
          <p className="mt-2 text-xs cell-muted">
            共 {tenantTotal} 个，仅展示前 {tenants.length} 个
          </p>
        )}
      </section>
    </aside>
  );
}
