"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { AdminDetailHeader } from "@/components/layout/AdminDetailHeader";
import { adminApi, type AdminTenant, type BillingPlan } from "@/lib/api";
import { useRequireAdmin } from "@/lib/auth-store";

type PlanForm = {
  name: string;
  description: string;
  price_monthly: string;
  max_tokens_monthly: number;
  max_storage_mb: number;
  max_knowledge_bases: number;
  max_agents: number;
  max_flows: number;
};

function fromPlan(p: BillingPlan): PlanForm {
  return {
    name: p.name,
    description: p.description ?? "",
    price_monthly: String(p.price_monthly),
    max_tokens_monthly: p.max_tokens_monthly,
    max_storage_mb: p.max_storage_mb,
    max_knowledge_bases: p.max_knowledge_bases,
    max_agents: p.max_agents,
    max_flows: p.max_flows,
  };
}

function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-ink-muted">{label}</span>
      {children}
      {hint ? <span className="mt-1 block text-xs text-ink-faint">{hint}</span> : null}
    </label>
  );
}

export default function BillingPlanDetailPage() {
  const { id } = useParams<{ id: string }>();
  const ready = useRequireAdmin();
  const [plan, setPlan] = useState<BillingPlan | null>(null);
  const [form, setForm] = useState<PlanForm | null>(null);
  const [tenants, setTenants] = useState<AdminTenant[]>([]);
  const [tenantTotal, setTenantTotal] = useState(0);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [saving, setSaving] = useState(false);

  const reload = async () => {
    const [p, t] = await Promise.all([adminApi.getPlan(id), adminApi.listTenants(1, 10, undefined, id)]);
    setPlan(p);
    setForm(fromPlan(p));
    setTenants(t.items);
    setTenantTotal(t.total);
  };

  useEffect(() => {
    if (!ready) return;
    reload().catch(() => setErr("加载失败"));
  }, [ready, id]);

  const onSave = async () => {
    if (!form) return;
    setSaving(true);
    setErr("");
    try {
      const updated = await adminApi.updatePlan(id, {
        name: form.name.trim(),
        description: form.description.trim() || null,
        price_monthly: Number(form.price_monthly) || 0,
        max_tokens_monthly: form.max_tokens_monthly,
        max_storage_mb: form.max_storage_mb,
        max_knowledge_bases: form.max_knowledge_bases,
        max_agents: form.max_agents,
        max_flows: form.max_flows,
      });
      setPlan(updated);
      setForm(fromPlan(updated));
      setMsg("套餐已保存");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const onToggleActive = async () => {
    if (!plan) return;
    setErr("");
    try {
      const updated = await adminApi.updatePlan(id, { is_active: !plan.is_active });
      setPlan(updated);
      setMsg(updated.is_active ? "套餐已启用" : "套餐已停用");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "操作失败");
    }
  };

  if (!plan || !form) {
    return <p className="text-sm cell-muted">加载中…</p>;
  }

  return (
    <div className="space-y-6">
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

      {msg && <p className="text-sm text-emerald-600">{msg}</p>}
      {err && <p className="text-sm text-red-600">{err}</p>}

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[
          { label: "月费", value: `¥${plan.price_monthly}` },
          {
            label: "Token 月额度",
            value: plan.max_tokens_monthly.toLocaleString(),
          },
          {
            label: "存储上限",
            value: `${plan.max_storage_mb.toLocaleString()} MB`,
          },
          { label: "绑定租户", value: String(tenantTotal) },
        ].map((s) => (
          <div key={s.label} className="card p-4">
            <p className="text-xs cell-muted">{s.label}</p>
            <p className="mt-1 text-xl font-bold stat-value text-brand">{s.value}</p>
          </div>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <section className="card p-5">
            <h2 className="text-sm font-semibold text-ink">基本信息</h2>
            <div className="mt-4 space-y-3">
              <Field label="套餐名称">
                <input className="input-field" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
              </Field>
              <Field label="描述">
                <textarea
                  className="input-field min-h-[72px] resize-y"
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                />
              </Field>
              <Field label="月费（元）">
                <input className="input-field max-w-[12rem]" value={form.price_monthly} onChange={(e) => setForm({ ...form, price_monthly: e.target.value })} />
              </Field>
            </div>
          </section>

          <section className="card p-5">
            <h2 className="text-sm font-semibold text-ink">默认配额</h2>
            <p className="mt-1 text-xs cell-muted">租户绑定此套餐时将同步以下上限（可在租户详情单独调整）。</p>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <Field label="Token 月额度">
                <input
                  type="number"
                  className="input-field"
                  value={form.max_tokens_monthly}
                  onChange={(e) => setForm({ ...form, max_tokens_monthly: Number(e.target.value) })}
                />
              </Field>
              <Field label="存储 MB">
                <input
                  type="number"
                  className="input-field"
                  value={form.max_storage_mb}
                  onChange={(e) => setForm({ ...form, max_storage_mb: Number(e.target.value) })}
                />
              </Field>
              <Field label="知识库数量">
                <input
                  type="number"
                  className="input-field"
                  value={form.max_knowledge_bases}
                  onChange={(e) => setForm({ ...form, max_knowledge_bases: Number(e.target.value) })}
                />
              </Field>
              <Field label="智能体数量">
                <input
                  type="number"
                  className="input-field"
                  value={form.max_agents}
                  onChange={(e) => setForm({ ...form, max_agents: Number(e.target.value) })}
                />
              </Field>
              <Field label="流程数量">
                <input type="number" className="input-field" value={form.max_flows} onChange={(e) => setForm({ ...form, max_flows: Number(e.target.value) })} />
              </Field>
            </div>
          </section>
        </div>

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
                    <Link href={`/tenants/${t.id}`} className="cell-primary hover:text-brand">
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
      </div>
    </div>
  );
}
