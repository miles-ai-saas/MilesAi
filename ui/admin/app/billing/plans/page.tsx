"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { adminApi, type BillingPlan } from "@/lib/api";
import { useRequireAdmin } from "@/lib/auth-store";

export default function BillingPlansPage() {
  const ready = useRequireAdmin();
  const [plans, setPlans] = useState<BillingPlan[]>([]);
  const [showPlanForm, setShowPlanForm] = useState(false);
  const [planCode, setPlanCode] = useState("");
  const [planName, setPlanName] = useState("");
  const [planPrice, setPlanPrice] = useState("0");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const reload = async () => {
    setPlans(await adminApi.listPlans());
  };

  useEffect(() => {
    if (!ready) return;
    reload().catch(() => undefined);
  }, [ready]);

  const onCreatePlan = async () => {
    setErr("");
    setMsg("");
    try {
      await adminApi.createPlan({
        code: planCode.trim(),
        name: planName.trim(),
        price_monthly: Number(planPrice) || 0,
        max_knowledge_bases: 10,
        max_storage_mb: 10240,
        max_tokens_monthly: 1_000_000,
        max_agents: 20,
        max_flows: 20,
        is_active: true,
      });
      setShowPlanForm(false);
      setPlanCode("");
      setPlanName("");
      setMsg("套餐已创建");
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "创建失败");
    }
  };

  return (
    <div>
      <PageHeader
        title="套餐管理"
        description="定义租户可绑定的计费方案与默认配额"
        action={
          <button type="button" className="btn-primary" onClick={() => setShowPlanForm((v) => !v)}>
            {showPlanForm ? "取消" : "新建套餐"}
          </button>
        }
      />

      {msg && <p className="mb-4 text-sm text-emerald-600">{msg}</p>}
      {err && <p className="mb-4 text-sm text-red-600">{err}</p>}

      {showPlanForm && (
        <section className="card mb-6 p-4">
          <h2 className="text-sm font-semibold text-ink">新建套餐</h2>
          <div className="mt-3 grid gap-2 sm:grid-cols-3">
            <input className="input-field" placeholder="code（如 pro）" value={planCode} onChange={(e) => setPlanCode(e.target.value)} />
            <input className="input-field" placeholder="名称" value={planName} onChange={(e) => setPlanName(e.target.value)} />
            <input className="input-field" placeholder="月费（元）" value={planPrice} onChange={(e) => setPlanPrice(e.target.value)} />
          </div>
          <button type="button" className="btn-primary mt-3" onClick={onCreatePlan}>
            保存套餐
          </button>
        </section>
      )}

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
              <button
                type="button"
                className="text-xs cell-muted hover:text-brand"
                onClick={async () => {
                  await adminApi.updatePlan(p.id, { is_active: !p.is_active });
                  setMsg(p.is_active ? "套餐已停用" : "套餐已启用");
                  await reload();
                }}
              >
                {p.is_active ? "停用" : "启用"}
              </button>
            </div>
          </div>
        ))}
        {plans.length === 0 && <p className="text-sm cell-muted">暂无套餐</p>}
      </div>
    </div>
  );
}
