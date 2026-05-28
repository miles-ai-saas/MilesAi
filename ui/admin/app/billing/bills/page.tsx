"use client";

import { useCallback, useEffect, useState } from "react";
import { ListFooter } from "@/components/list/ListFooter";
import { PageHeader } from "@/components/layout/PageHeader";
import { usePagedList } from "@/hooks/use-paged-list";
import { adminApi, type AdminTenant, type TenantBillDetail } from "@/lib/api";
import { useRequireAdmin } from "@/lib/auth-store";

const BILL_STATUS_LABEL: Record<string, string> = {
  issued: "待支付",
  paid: "已付",
  void: "已作废",
  draft: "草稿",
};

export default function BillingBillsPage() {
  const ready = useRequireAdmin();
  const [tenants, setTenants] = useState<AdminTenant[]>([]);
  const [billDetail, setBillDetail] = useState<TenantBillDetail | null>(null);
  const [genTenantId, setGenTenantId] = useState("");
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const list = usePagedList(
    useCallback((p, s) => adminApi.listBills(p, s), []),
    {
      enabled: ready,
    },
  );

  useEffect(() => {
    if (!ready) return;
    adminApi
      .listTenants(1, 100)
      .then((t) => setTenants(t.items))
      .catch(() => undefined);
  }, [ready]);

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
      await list.reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "生成失败");
    }
  };

  const viewBill = async (id: string) => {
    setBillDetail(await adminApi.getBill(id));
  };

  return (
    <div>
      <PageHeader title="账单管理" description="按租户与账期生成、跟踪与结算账单" />

      {msg && <p className="mb-4 text-sm text-emerald-600">{msg}</p>}
      {err && <p className="mb-4 text-sm text-red-600">{err}</p>}

      <section className="card mb-6 p-4">
        <h2 className="text-sm font-semibold text-ink">生成账单</h2>
        <div className="mt-3 flex flex-wrap items-end gap-2">
          <select className="input-field w-auto min-w-[12rem]" value={genTenantId} onChange={(e) => setGenTenantId(e.target.value)}>
            <option value="">选择租户</option>
            {tenants.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
          <input type="date" className="input-field w-auto" value={periodStart} onChange={(e) => setPeriodStart(e.target.value)} />
          <span className="cell-muted">至</span>
          <input type="date" className="input-field w-auto" value={periodEnd} onChange={(e) => setPeriodEnd(e.target.value)} />
          <button type="button" className="btn-primary" onClick={onGenerateBill}>
            生成账单
          </button>
        </div>
      </section>

      <section className="card p-4">
        <h2 className="text-sm font-semibold text-ink">账单列表</h2>
        {list.loading ? (
          <p className="mt-4 text-sm text-ink-muted">加载中…</p>
        ) : (
          <>
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
                  {list.items.length === 0 && (
                    <tr>
                      <td colSpan={5} className="py-10 text-center cell-muted">
                        暂无账单
                      </td>
                    </tr>
                  )}
                  {list.items.map((b) => (
                    <tr key={b.id}>
                      <td className="cell-primary">{b.tenant_name || b.tenant_id.slice(0, 8)}</td>
                      <td className="col-center col-numeric cell-numeric">
                        {b.period_start} ~ {b.period_end}
                      </td>
                      <td className="col-center col-numeric cell-numeric">¥{b.amount}</td>
                      <td className="col-center">
                        <span className="badge bg-brand-light text-ink">{BILL_STATUS_LABEL[b.status] ?? b.status}</span>
                      </td>
                      <td className="col-actions">
                        <button type="button" className="text-brand hover:underline" onClick={() => viewBill(b.id)}>
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
                                await list.reload();
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
                                await list.reload();
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
            <ListFooter className="mt-3" page={list.page} size={list.size} total={list.total} onPageChange={list.setPage} onSizeChange={list.setSize} />
          </>
        )}
        {billDetail && (
          <div className="mt-4 rounded-lg bg-surface-muted p-3 text-xs">
            <p className="font-semibold text-ink">消费明细 · {billDetail.tenant_name}</p>
            <ul className="mt-2 space-y-1 cell-numeric cell-muted">
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
