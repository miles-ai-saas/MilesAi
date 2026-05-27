"use client";

import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { adminApi, type AdminTenant, type BillingPlan, type TenantBill, type TenantBillDetail } from "@/lib/api";
import { useRequireAdmin } from "@/lib/auth-store";

export default function BillingPage() {
  const ready = useRequireAdmin();
  const [plans, setPlans] = useState<BillingPlan[]>([]);
  const [bills, setBills] = useState<TenantBill[]>([]);
  const [tenants, setTenants] = useState<AdminTenant[]>([]);
  const [billDetail, setBillDetail] = useState<TenantBillDetail | null>(null);
  const [showPlanForm, setShowPlanForm] = useState(false);
  const [planCode, setPlanCode] = useState("");
  const [planName, setPlanName] = useState("");
  const [planPrice, setPlanPrice] = useState("0");
  const [genTenantId, setGenTenantId] = useState("");
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const reload = async () => {
    const [p, b, t] = await Promise.all([
      adminApi.listPlans(),
      adminApi.listBills(),
      adminApi.listTenants(1, 100),
    ]);
    setPlans(p);
    setBills(b.items);
    setTenants(t.items);
  };

  useEffect(() => {
    if (!ready) return;
    reload().catch(() => undefined);
  }, [ready]);

  const viewBill = async (id: string) => {
    setBillDetail(await adminApi.getBill(id));
  };

  const onCreatePlan = async () => {
    setErr("");
    setMsg("");
    try {
      await adminApi.createPlan({
        code: planCode.trim(),
        name: planName.trim(),
        price_monthly: Number(planPrice) || 0,
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

  const onGenerateBill = async () => {
    setErr("");
    setMsg("");
    if (!genTenantId || !periodStart || !periodEnd) {
      setErr("请选择租户并填写账期");
      return;
    }
    try {
      await adminApi.generateBill(genTenantId, periodStart, periodEnd);
      setMsg("账单已生成");
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "生成失败");
    }
  };

  return (
    <div>
      <PageHeader
        title="计费管理"
        description="套餐配置与租户账单"
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
            <input
              className="input-field"
              placeholder="code（如 pro）"
              value={planCode}
              onChange={(e) => setPlanCode(e.target.value)}
            />
            <input
              className="input-field"
              placeholder="名称"
              value={planName}
              onChange={(e) => setPlanName(e.target.value)}
            />
            <input
              className="input-field"
              placeholder="月费（元）"
              value={planPrice}
              onChange={(e) => setPlanPrice(e.target.value)}
            />
          </div>
          <button type="button" className="btn-primary mt-3" onClick={onCreatePlan}>
            保存套餐
          </button>
        </section>
      )}

      <section className="card mb-8 p-4">
        <h2 className="text-sm font-semibold text-ink">套餐配置</h2>
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          {plans.map((p) => (
            <div key={p.id} className="rounded-lg border border-line p-3 text-sm">
              <p className="font-bold">{p.name}</p>
              <p className="text-xs text-ink-muted">{p.code}</p>
              <p className="mt-2 cell-numeric text-brand">¥{p.price_monthly}/月</p>
              <p className="mt-1 cell-numeric text-xs text-ink-muted">
                {p.max_storage_mb.toLocaleString()} MB · {p.max_tokens_monthly.toLocaleString()} tokens
              </p>
              {!p.is_active && (
                <span className="mt-2 inline-block text-xs text-ink-faint">已停用</span>
              )}
              <button
                type="button"
                className="mt-3 text-xs text-brand hover:underline"
                onClick={async () => {
                  await adminApi.updatePlan(p.id, { is_active: !p.is_active });
                  setMsg(p.is_active ? "套餐已停用" : "套餐已启用");
                  await reload();
                }}
              >
                {p.is_active ? "停用套餐" : "重新启用"}
              </button>
            </div>
          ))}
          {plans.length === 0 && <p className="text-sm text-ink-faint">暂无套餐</p>}
        </div>
      </section>

      <section className="card mb-8 p-4">
        <h2 className="text-sm font-semibold text-ink">生成账单</h2>
        <div className="mt-3 flex flex-wrap items-end gap-2">
          <select
            className="input-field w-auto min-w-[12rem]"
            value={genTenantId}
            onChange={(e) => setGenTenantId(e.target.value)}
          >
            <option value="">选择租户</option>
            {tenants.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
          <input
            type="date"
            className="input-field w-auto"
            value={periodStart}
            onChange={(e) => setPeriodStart(e.target.value)}
          />
          <span className="text-ink-muted">至</span>
          <input
            type="date"
            className="input-field w-auto"
            value={periodEnd}
            onChange={(e) => setPeriodEnd(e.target.value)}
          />
          <button type="button" className="btn-primary" onClick={onGenerateBill}>
            生成账单
          </button>
        </div>
      </section>

      <section className="card p-4">
        <h2 className="text-sm font-semibold text-ink">账单列表</h2>
        <div className="mt-4 admin-table-wrap border-0">
          <table className="admin-table">
            <thead>
              <tr>
                <th>租户</th>
                <th className="col-center col-numeric">周期</th>
                <th className="col-center col-numeric">金额</th>
                <th className="col-center">状态</th>
                <th className="col-actions">操作</th>
              </tr>
            </thead>
            <tbody>
              {bills.map((b) => (
                <tr key={b.id}>
                  <td className="cell-primary">{b.tenant_name || b.tenant_id.slice(0, 8)}</td>
                  <td className="col-center col-numeric cell-numeric">
                    {b.period_start} ~ {b.period_end}
                  </td>
                  <td className="col-center col-numeric cell-numeric">¥{b.amount}</td>
                  <td className="col-center">
                    <span className="badge bg-brand-light text-ink">{b.status}</span>
                  </td>
                  <td className="col-actions">
                    <button
                      type="button"
                      className="text-brand hover:underline"
                      onClick={() => viewBill(b.id)}
                    >
                      明细
                    </button>
                    {b.status === "issued" && (
                      <>
                        <button
                          type="button"
                          className="text-emerald-600 hover:underline"
                          onClick={async () => {
                            await adminApi.updateBillStatus(b.id, "paid");
                            setMsg("已标记为已付");
                            await reload();
                          }}
                        >
                          已付
                        </button>
                        <button
                          type="button"
                          className="text-red-600 hover:underline"
                          onClick={async () => {
                            await adminApi.updateBillStatus(b.id, "void");
                            setMsg("账单已作废");
                            await reload();
                          }}
                        >
                          作废
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {billDetail && (
          <div className="mt-4 rounded-lg bg-surface-muted p-3 text-xs">
            <p className="font-semibold text-ink">消费明细 · {billDetail.tenant_name}</p>
            <ul className="mt-2 space-y-1 cell-numeric text-ink-muted">
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
