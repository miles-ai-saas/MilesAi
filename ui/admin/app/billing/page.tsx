"use client";

import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { adminApi, type BillingPlan, type TenantBill, type TenantBillDetail } from "@/lib/api";
import { useRequireAdmin } from "@/lib/auth-store";

export default function BillingPage() {
  const ready = useRequireAdmin();
  const [plans, setPlans] = useState<BillingPlan[]>([]);
  const [bills, setBills] = useState<TenantBill[]>([]);
  const [billDetail, setBillDetail] = useState<TenantBillDetail | null>(null);

  useEffect(() => {
    if (!ready) return;
    Promise.all([adminApi.listPlans(), adminApi.listBills()]).then(([p, b]) => {
      setPlans(p);
      setBills(b.items);
    });
  }, [ready]);

  const viewBill = async (id: string) => {
    setBillDetail(await adminApi.getBill(id));
  };

  return (
    <div>
      <PageHeader title="计费管理" description="套餐配置与租户账单" />

      <section className="card mb-8 p-4">
        <h2 className="text-sm font-semibold text-ink">套餐配置</h2>
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          {plans.map((p) => (
            <div key={p.id} className="rounded-lg border border-line p-3 text-sm">
              <p className="font-bold">{p.name}</p>
              <p className="text-xs text-ink-muted">{p.code}</p>
              <p className="mt-2 text-brand">¥{p.price_monthly}/月</p>
              <p className="mt-1 text-xs text-ink-muted">
                {p.max_storage_mb} MB · {p.max_tokens_monthly.toLocaleString()} tokens
              </p>
            </div>
          ))}
          {plans.length === 0 && <p className="text-sm text-ink-faint">暂无套餐</p>}
        </div>
      </section>

      <section className="card p-4">
        <h2 className="text-sm font-semibold text-ink">账单列表</h2>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-xs text-ink-muted">
              <tr>
                <th className="py-2 text-left">租户</th>
                <th className="py-2 text-center">周期</th>
                <th className="py-2 text-center">金额</th>
                <th className="py-2 text-center">状态</th>
                <th className="py-2 text-right">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line-soft">
              {bills.map((b) => (
                <tr key={b.id} className="hover:bg-brand-light/60">
                  <td className="py-2">{b.tenant_name || b.tenant_id.slice(0, 8)}</td>
                  <td className="py-2 text-center text-xs">
                    {b.period_start} ~ {b.period_end}
                  </td>
                  <td className="py-2 text-center">¥{b.amount}</td>
                  <td className="py-2 text-center">
                    <span className="badge bg-brand-light text-ink">{b.status}</span>
                  </td>
                  <td className="py-2 text-right">
                    <button
                      type="button"
                      className="text-xs text-brand hover:underline"
                      onClick={() => viewBill(b.id)}
                    >
                      明细
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {billDetail && (
          <div className="mt-4 rounded-lg bg-surface-muted p-3 text-xs">
            <p className="font-semibold text-ink">消费明细 · {billDetail.tenant_name}</p>
            <ul className="mt-2 space-y-1 text-ink-muted">
              {billDetail.line_items.map((item, i) => (
                <li key={i}>
                  {item.item_type}: {item.description || "—"} — ¥{item.amount}
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>
    </div>
  );
}
