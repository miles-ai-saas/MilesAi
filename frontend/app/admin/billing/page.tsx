"use client";

import { useEffect, useState } from "react";
import { adminApi, type BillingPlan, type TenantBill } from "@/lib/admin-api";
import { useRequireAdmin } from "@/lib/admin-auth-store";

export default function AdminBillingPage() {
  const ready = useRequireAdmin();
  const [plans, setPlans] = useState<BillingPlan[]>([]);
  const [bills, setBills] = useState<TenantBill[]>([]);
  const [selectedBill, setSelectedBill] = useState<string | null>(null);
  const [billDetail, setBillDetail] = useState<Awaited<ReturnType<typeof adminApi.getBill>> | null>(
    null
  );

  useEffect(() => {
    if (!ready) return;
    Promise.all([adminApi.listPlans(), adminApi.listBills()]).then(([p, b]) => {
      setPlans(p);
      setBills(b.items);
    });
  }, [ready]);

  const viewBill = async (id: string) => {
    setSelectedBill(id);
    setBillDetail(await adminApi.getBill(id));
  };

  return (
    <div className="space-y-8">
      <h1 className="text-xl font-bold">计费管理</h1>

      <section className="rounded-lg border bg-white p-4">
        <h2 className="text-sm font-semibold">套餐配置</h2>
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          {plans.map((p) => (
            <div key={p.id} className="rounded border p-3 text-sm">
              <p className="font-bold">{p.name}</p>
              <p className="text-xs text-slate-500">{p.code}</p>
              <p className="mt-2 text-brand">¥{p.price_monthly}/月</p>
              <p className="mt-1 text-xs text-slate-500">
                {p.max_storage_mb} MB · {p.max_tokens_monthly} tokens
              </p>
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-lg border bg-white p-4">
        <h2 className="text-sm font-semibold">账单列表</h2>
        <table className="mt-4 w-full text-sm">
          <thead className="text-xs text-slate-500">
            <tr>
              <th className="py-2 text-left">租户</th>
              <th>周期</th>
              <th>金额</th>
              <th>状态</th>
              <th></th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {bills.map((b) => (
              <tr key={b.id}>
                <td className="py-2">{b.tenant_name}</td>
                <td className="text-center text-xs">
                  {b.period_start} ~ {b.period_end}
                </td>
                <td className="text-center">¥{b.amount}</td>
                <td className="text-center">{b.status}</td>
                <td className="text-center">
                  <button type="button" className="text-brand text-xs" onClick={() => viewBill(b.id)}>
                    明细
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {billDetail && selectedBill && (
          <div className="mt-4 rounded bg-slate-50 p-3 text-xs">
            <p className="font-semibold">消费明细</p>
            <ul className="mt-2 space-y-1">
              {billDetail.line_items.map((item, i) => (
                <li key={i}>
                  {item.item_type}: {item.description} — ¥{item.amount}
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>
    </div>
  );
}
