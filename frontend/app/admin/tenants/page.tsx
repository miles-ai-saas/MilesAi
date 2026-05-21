"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { adminApi, type AdminTenant, type BillingPlan } from "@/lib/admin-api";
import { useRequireAdmin } from "@/lib/admin-auth-store";

export default function AdminTenantsPage() {
  const ready = useRequireAdmin();
  const [tenants, setTenants] = useState<AdminTenant[]>([]);
  const [plans, setPlans] = useState<BillingPlan[]>([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [name, setName] = useState("");
  const [planId, setPlanId] = useState("");

  const reload = async () => {
    const q = statusFilter ? `&status=${statusFilter}` : "";
    const [t, p] = await Promise.all([adminApi.listTenants(q), adminApi.listPlans()]);
    setTenants(t.items);
    setPlans(p);
  };

  useEffect(() => {
    if (!ready) return;
    reload();
  }, [ready, statusFilter]);

  const create = async () => {
    if (!name.trim()) return;
    await adminApi.createTenant({
      name: name.trim(),
      plan_id: planId || null,
      status: "active",
    });
    setName("");
    await reload();
  };

  return (
    <div>
      <h1 className="text-xl font-bold text-slate-800">租户管理</h1>

      <div className="mt-4 flex flex-wrap gap-2">
        {["", "active", "trial", "suspended"].map((s) => (
          <button
            key={s || "all"}
            type="button"
            onClick={() => setStatusFilter(s)}
            className={`rounded-full px-3 py-1 text-xs ${
              statusFilter === s ? "bg-brand text-white" : "border bg-white"
            }`}
          >
            {s || "全部"}
          </button>
        ))}
      </div>

      <section className="mt-6 rounded-lg border bg-white p-4">
        <h2 className="text-sm font-semibold">新建租户</h2>
        <div className="mt-2 flex flex-wrap gap-2">
          <input
            className="rounded border px-3 py-2 text-sm"
            placeholder="租户名称"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <select
            className="rounded border px-3 py-2 text-sm"
            value={planId}
            onChange={(e) => setPlanId(e.target.value)}
          >
            <option value="">选择套餐</option>
            {plans.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
          <button type="button" onClick={create} className="rounded bg-brand px-4 py-2 text-sm text-white">
            创建
          </button>
        </div>
      </section>

      <div className="mt-6 overflow-hidden rounded-lg border bg-white">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-xs text-slate-500">
            <tr>
              <th className="px-4 py-2 text-left">名称</th>
              <th className="px-4 py-2">套餐</th>
              <th className="px-4 py-2">状态</th>
              <th className="px-4 py-2">用量</th>
              <th className="px-4 py-2">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {tenants.map((t) => (
              <tr key={t.id}>
                <td className="px-4 py-3 font-medium">{t.name}</td>
                <td className="px-4 py-3 text-center text-xs">{t.plan_name || "-"}</td>
                <td className="px-4 py-3 text-center">
                  <span className="rounded bg-slate-100 px-2 py-0.5 text-xs">{t.status}</span>
                </td>
                <td className="px-4 py-3 text-center text-xs text-slate-500">
                  {t.storage_used_mb}/{t.max_storage_mb} MB · Token {t.tokens_used_month}
                </td>
                <td className="px-4 py-3 text-center">
                  <Link href={`/admin/tenants/${t.id}`} className="text-brand hover:underline">
                    详情
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
