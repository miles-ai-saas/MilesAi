"use client";

import { useCallback, useEffect, useState } from "react";
import { usePagedList } from "@/hooks/use-paged-list";
import { adminApi, type AdminTenant, type TenantBillDetail } from "@/lib/api";
import { useRequireAdmin } from "@/lib/auth-store";

export function useBillingBillsPage() {
  const ready = useRequireAdmin();
  const [tenants, setTenants] = useState<AdminTenant[]>([]);
  const [billDetail, setBillDetail] = useState<TenantBillDetail | null>(null);
  const [genTenantId, setGenTenantId] = useState("");
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const list = usePagedList(useCallback((p, s) => adminApi.listBills(p, s), []), { enabled: ready });

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

  const markPaid = async (id: string) => {
    await adminApi.updateBillStatus(id, "paid");
    setMsg("已标记为已付");
    await list.reload();
  };

  const voidBill = async (id: string) => {
    await adminApi.updateBillStatus(id, "void");
    setMsg("账单已作废");
    await list.reload();
  };

  return {
    tenants,
    billDetail,
    genTenantId,
    setGenTenantId,
    periodStart,
    setPeriodStart,
    periodEnd,
    setPeriodEnd,
    msg,
    err,
    list,
    onGenerateBill,
    viewBill,
    markPaid,
    voidBill,
  };
}

export type BillingBillsPageVm = ReturnType<typeof useBillingBillsPage>;
