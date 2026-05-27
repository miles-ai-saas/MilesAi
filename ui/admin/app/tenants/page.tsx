"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { adminApi, type AdminTenant, type BillingPlan } from "@/lib/api";
import { useRequireAdmin } from "@/lib/auth-store";

const STATUS_LABEL: Record<string, string> = {
  active: "活跃",
  trial: "试用",
  suspended: "已停用",
};

export default function TenantsPage() {
  const ready = useRequireAdmin();
  const [tenants, setTenants] = useState<AdminTenant[]>([]);
  const [plans, setPlans] = useState<BillingPlan[]>([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [name, setName] = useState("");
  const [planId, setPlanId] = useState("");

  const reload = async () => {
    const [t, p] = await Promise.all([
      adminApi.listTenants(1, 50, statusFilter || undefined),
      adminApi.listPlans(),
    ]);
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
      <PageHeader title="租户管理" description="创建租户、分配套餐与查看用量" />

      <div className="mb-4 flex flex-wrap gap-2">
        {["", "active", "trial", "suspended"].map((s) => (
          <button
            key={s || "all"}
            type="button"
            onClick={() => setStatusFilter(s)}
            className={`rounded-full px-3 py-1 text-xs ${
              statusFilter === s ? "bg-brand text-white" : "border bg-white text-ink-muted"
            }`}
          >
            {s ? STATUS_LABEL[s] || s : "全部"}
          </button>
        ))}
      </div>

      <section className="card mb-6 p-4">
        <h2 className="text-sm font-semibold">新建租户</h2>
        <div className="mt-3 flex flex-wrap gap-2">
          <input
            className="input-field max-w-xs"
            placeholder="租户名称"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <select
            className="input-field max-w-xs"
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
          <button type="button" onClick={create} className="btn-primary">
            创建
          </button>
        </div>
      </section>

      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead>
            <tr>
              <th>名称</th>
              <th className="col-center">套餐</th>
              <th className="col-center">状态</th>
              <th className="col-center col-numeric">用量</th>
              <th className="col-actions">操作</th>
            </tr>
          </thead>
          <tbody>
            {tenants.map((t) => (
              <tr key={t.id}>
                <td className="cell-primary">{t.name}</td>
                <td className="col-center cell-muted">{t.plan_name || "—"}</td>
                <td className="col-center">
                  <span className="badge bg-brand-light text-ink">
                    {STATUS_LABEL[t.status] || t.status}
                  </span>
                </td>
                <td className="col-center col-numeric cell-numeric">
                  {t.storage_used_mb}/{t.max_storage_mb} MB · Token {t.tokens_used_month.toLocaleString()}
                </td>
                <td className="col-actions">
                  <Link href={`/tenants/${t.id}`} className="text-brand hover:underline">
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
