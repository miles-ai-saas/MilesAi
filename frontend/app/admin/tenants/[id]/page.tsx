"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { adminApi, type AdminTenantDetail, type BillingPlan } from "@/lib/admin-api";
import { useRequireAdmin } from "@/lib/admin-auth-store";

export default function AdminTenantDetailPage() {
  const { id } = useParams<{ id: string }>();
  const ready = useRequireAdmin();
  const [tenant, setTenant] = useState<AdminTenantDetail | null>(null);
  const [plans, setPlans] = useState<BillingPlan[]>([]);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    if (!ready) return;
    Promise.all([adminApi.getTenant(id), adminApi.listPlans()]).then(([t, p]) => {
      setTenant(t);
      setPlans(p);
    });
  }, [ready, id]);

  const save = async () => {
    if (!tenant) return;
    await adminApi.updateTenant(id, {
      status: tenant.status,
      plan_id: tenant.plan_id,
      is_active: tenant.is_active,
    });
    setMsg("已保存");
  };

  const saveQuota = async () => {
    if (!tenant) return;
    await adminApi.updateQuota(id, {
      max_tokens_monthly: tenant.max_tokens_monthly,
      max_storage_mb: tenant.max_storage_mb,
      max_knowledge_bases: tenant.max_knowledge_bases,
    });
    setMsg("配额已更新");
  };

  if (!tenant) return <p className="text-slate-500">加载中…</p>;

  return (
    <div className="max-w-3xl space-y-6">
      <h1 className="text-xl font-bold">{tenant.name}</h1>
      {msg && <p className="text-sm text-emerald-600">{msg}</p>}

      <section className="rounded-lg border bg-white p-4">
        <h2 className="font-semibold text-sm">基本信息</h2>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <label className="text-xs text-slate-500">
            状态
            <select
              className="mt-1 block w-full rounded border px-2 py-1 text-sm"
              value={tenant.status}
              onChange={(e) => setTenant({ ...tenant, status: e.target.value })}
            >
              <option value="active">active</option>
              <option value="trial">trial</option>
              <option value="suspended">suspended</option>
            </select>
          </label>
          <label className="text-xs text-slate-500">
            套餐
            <select
              className="mt-1 block w-full rounded border px-2 py-1 text-sm"
              value={tenant.plan_id || ""}
              onChange={(e) => setTenant({ ...tenant, plan_id: e.target.value || null })}
            >
              <option value="">无</option>
              {plans.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
        </div>
        <button type="button" onClick={save} className="mt-4 rounded bg-brand px-4 py-2 text-sm text-white">
          保存
        </button>
      </section>

      <section className="rounded-lg border bg-white p-4">
        <h2 className="font-semibold text-sm">使用统计</h2>
        <div className="mt-3 grid grid-cols-3 gap-3 text-sm">
          <div>知识库 {tenant.usage.knowledge_bases}</div>
          <div>文档 {tenant.usage.documents}</div>
          <div>智能体 {tenant.usage.agents}</div>
          <div>流程 {tenant.usage.flows}</div>
          <div>用户 {tenant.usage.users}</div>
          <div>存储 {tenant.usage.storage_used_mb} MB</div>
        </div>
      </section>

      <section className="rounded-lg border bg-white p-4">
        <h2 className="font-semibold text-sm">额度管理</h2>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <label className="text-xs">
            Token 月额度
            <input
              type="number"
              className="mt-1 block w-full rounded border px-2 py-1 text-sm"
              value={tenant.max_tokens_monthly}
              onChange={(e) =>
                setTenant({ ...tenant, max_tokens_monthly: Number(e.target.value) })
              }
            />
          </label>
          <label className="text-xs">
            存储 MB
            <input
              type="number"
              className="mt-1 block w-full rounded border px-2 py-1 text-sm"
              value={tenant.max_storage_mb}
              onChange={(e) => setTenant({ ...tenant, max_storage_mb: Number(e.target.value) })}
            />
          </label>
        </div>
        <button type="button" onClick={saveQuota} className="mt-4 rounded border px-4 py-2 text-sm">
          更新配额
        </button>
      </section>
    </div>
  );
}
