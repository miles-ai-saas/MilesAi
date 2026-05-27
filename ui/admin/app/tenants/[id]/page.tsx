"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { AdminDetailHeader } from "@/components/layout/AdminDetailHeader";
import { UsageQuotaRow } from "@/components/tenant/UsageQuotaRow";
import {
  adminApi,
  type AdminTenantDetail,
  type BillingPlan,
  type TenantBill,
} from "@/lib/api";
import { useRequireAdmin } from "@/lib/auth-store";

const STATUS_LABEL: Record<string, string> = {
  active: "活跃",
  trial: "试用",
  suspended: "已停用",
};

const BILL_STATUS_LABEL: Record<string, string> = {
  issued: "待支付",
  paid: "已付",
  void: "已作废",
  draft: "草稿",
};

function pct(used: number, max: number) {
  return max > 0 ? Math.min(100, Math.round((used / max) * 100)) : 0;
}

function statusBadgeClass(status: string) {
  if (status === "active") return "bg-emerald-50 text-emerald-700";
  if (status === "trial") return "bg-sky-50 text-sky-700";
  return "bg-surface-muted text-ink-muted";
}

function applyPlanQuotas(
  tenant: AdminTenantDetail,
  plan: BillingPlan,
): AdminTenantDetail {
  return {
    ...tenant,
    max_tokens_monthly: plan.max_tokens_monthly,
    max_storage_mb: plan.max_storage_mb,
    max_knowledge_bases: plan.max_knowledge_bases,
    max_agents: plan.max_agents,
    max_flows: plan.max_flows,
  };
}

export default function TenantDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const ready = useRequireAdmin();
  const [tenant, setTenant] = useState<AdminTenantDetail | null>(null);
  const [plans, setPlans] = useState<BillingPlan[]>([]);
  const [bills, setBills] = useState<TenantBill[]>([]);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [savingSub, setSavingSub] = useState(false);
  const [savingQuota, setSavingQuota] = useState(false);

  const reload = async () => {
    const [t, p, usage, billRes] = await Promise.all([
      adminApi.getTenant(id),
      adminApi.listPlans(),
      adminApi.getTenantUsage(id),
      adminApi.listBills(1, 5, id),
    ]);
    setTenant({ ...t, usage });
    setPlans(p);
    setBills(billRes.items);
  };

  useEffect(() => {
    if (!ready) return;
    reload().catch(() => undefined);
  }, [ready, id]);

  const activePlans = useMemo(
    () => plans.filter((p) => p.is_active || p.id === tenant?.plan_id),
    [plans, tenant?.plan_id],
  );

  const selectedPlan = useMemo(
    () => plans.find((p) => p.id === tenant?.plan_id) ?? null,
    [plans, tenant?.plan_id],
  );

  const saveSubscription = async () => {
    if (!tenant) return;
    setSavingSub(true);
    setErr("");
    try {
      await adminApi.updateTenant(id, {
        status: tenant.status,
        plan_id: tenant.plan_id,
        is_active: tenant.is_active,
      });
      setMsg("订阅信息已保存");
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "保存失败");
    } finally {
      setSavingSub(false);
    }
  };

  const saveQuota = async () => {
    if (!tenant) return;
    setSavingQuota(true);
    setErr("");
    try {
      await adminApi.updateQuota(id, {
        max_tokens_monthly: tenant.max_tokens_monthly,
        max_storage_mb: tenant.max_storage_mb,
        max_knowledge_bases: tenant.max_knowledge_bases,
        max_agents: tenant.max_agents,
        max_flows: tenant.max_flows,
      });
      setMsg("配额已更新");
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "更新失败");
    } finally {
      setSavingQuota(false);
    }
  };

  const onApplyPlanQuota = () => {
    if (!tenant || !selectedPlan) return;
    setTenant(applyPlanQuotas(tenant, selectedPlan));
    setMsg(`已填入套餐「${selectedPlan.name}」的配额，请点击「保存配额」生效`);
  };

  const onDelete = async () => {
    if (!tenant || !confirm(`确定删除租户「${tenant.name}」？将清空其业务数据。`)) return;
    await adminApi.deleteTenant(id);
    router.push("/tenants");
  };

  const copyTenantId = async () => {
    try {
      await navigator.clipboard.writeText(id);
      setMsg("已复制租户 ID");
    } catch {
      setErr("复制失败");
    }
  };

  if (!tenant) {
    return <p className="text-sm cell-muted">加载中…</p>;
  }

  const tokenPct = pct(tenant.usage.tokens_used_month, tenant.max_tokens_monthly);
  const storagePct = pct(tenant.usage.storage_used_mb, tenant.max_storage_mb);

  return (
    <div className="space-y-6">
      <AdminDetailHeader
        backHref="/tenants"
        backLabel="返回租户列表"
        title={tenant.name}
        badges={
          <>
            <span className={`status-badge ${statusBadgeClass(tenant.status)}`}>
              {STATUS_LABEL[tenant.status] ?? tenant.status}
            </span>
            {tenant.plan_name && (
              <span className="badge bg-brand-light text-brand">{tenant.plan_name}</span>
            )}
          </>
        }
        description={
          <>
            创建于 {tenant.created_at.slice(0, 10)}
            <span className="mx-2 text-ink-faint">·</span>
            <button
              type="button"
              className="font-mono text-xs text-ink-faint hover:text-brand"
              onClick={() => void copyTenantId()}
              title="点击复制"
            >
              {id.slice(0, 8)}…
            </button>
          </>
        }
      />

      {msg && <p className="text-sm text-emerald-600">{msg}</p>}
      {err && <p className="text-sm text-red-600">{err}</p>}

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[
          { label: "Token 本月", value: `${tokenPct}%`, sub: `${tenant.usage.tokens_used_month.toLocaleString()} 已用` },
          { label: "存储空间", value: `${storagePct}%`, sub: `${tenant.usage.storage_used_mb} / ${tenant.max_storage_mb} MB` },
          { label: "租户用户", value: String(tenant.usage.users), sub: "活跃用户账号" },
          {
            label: "资源实例",
            value: String(
              tenant.usage.knowledge_bases +
                tenant.usage.agents +
                tenant.usage.flows,
            ),
            sub: `KB ${tenant.usage.knowledge_bases} · 智能体 ${tenant.usage.agents} · 流程 ${tenant.usage.flows}`,
          },
        ].map((s) => (
          <div key={s.label} className="card p-4">
            <p className="text-xs cell-muted">{s.label}</p>
            <p className="mt-1 text-2xl font-bold stat-value text-brand">{s.value}</p>
            <p className="mt-1 text-xs cell-muted">{s.sub}</p>
          </div>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <section className="card p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold text-ink">用量与配额</h2>
                <p className="mt-1 text-xs cell-muted">
                  左侧查看实时用量，右侧直接调整上限；文档 {tenant.usage.documents} 份
                </p>
              </div>
              <button
                type="button"
                className="btn-primary"
                disabled={savingQuota}
                onClick={() => void saveQuota()}
              >
                {savingQuota ? "保存中…" : "保存配额"}
              </button>
            </div>
            <div className="mt-4 space-y-3">
              <UsageQuotaRow
                label="Token（本月）"
                used={tenant.usage.tokens_used_month}
                max={tenant.max_tokens_monthly}
                onMaxChange={(v) => setTenant({ ...tenant, max_tokens_monthly: v })}
              />
              <UsageQuotaRow
                label="存储空间"
                used={tenant.usage.storage_used_mb}
                max={tenant.max_storage_mb}
                unit=" MB"
                onMaxChange={(v) => setTenant({ ...tenant, max_storage_mb: v })}
              />
              <UsageQuotaRow
                label="知识库数量"
                used={tenant.usage.knowledge_bases}
                max={tenant.max_knowledge_bases}
                onMaxChange={(v) => setTenant({ ...tenant, max_knowledge_bases: v })}
              />
              <UsageQuotaRow
                label="智能体"
                used={tenant.usage.agents}
                max={tenant.max_agents}
                onMaxChange={(v) => setTenant({ ...tenant, max_agents: v })}
              />
              <UsageQuotaRow
                label="流程"
                used={tenant.usage.flows}
                max={tenant.max_flows}
                onMaxChange={(v) => setTenant({ ...tenant, max_flows: v })}
              />
            </div>
          </section>

          <section className="card p-5">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-sm font-semibold text-ink">最近账单</h2>
              <Link href="/billing/bills" className="text-xs text-brand hover:underline">
                账单管理
              </Link>
            </div>
            {bills.length === 0 ? (
              <p className="mt-4 text-sm cell-muted">暂无账单记录</p>
            ) : (
              <div className="mt-4 admin-table-wrap border-0">
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th className="col-center col-numeric">周期</th>
                      <th className="col-center col-numeric">金额</th>
                      <th className="col-center">状态</th>
                    </tr>
                  </thead>
                  <tbody>
                    {bills.map((b) => (
                      <tr key={b.id}>
                        <td className="col-center col-numeric cell-numeric text-xs">
                          {b.period_start} ~ {b.period_end}
                        </td>
                        <td className="col-center col-numeric cell-numeric">¥{b.amount}</td>
                        <td className="col-center">
                          <span className="badge bg-brand-light text-ink">
                            {BILL_STATUS_LABEL[b.status] ?? b.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </div>

        <aside className="space-y-4">
          <section className="card p-5">
            <h2 className="text-sm font-semibold text-ink">订阅</h2>
            <div className="mt-4 space-y-3">
              <label className="block text-xs cell-muted">
                运营状态
                <select
                  className="input-field mt-1"
                  value={tenant.status}
                  onChange={(e) => setTenant({ ...tenant, status: e.target.value })}
                >
                  <option value="active">活跃</option>
                  <option value="trial">试用</option>
                  <option value="suspended">已停用</option>
                </select>
              </label>
              <label className="block text-xs cell-muted">
                计费套餐
                <select
                  className="input-field mt-1"
                  value={tenant.plan_id || ""}
                  onChange={(e) =>
                    setTenant({ ...tenant, plan_id: e.target.value || null })
                  }
                >
                  <option value="">无套餐</option>
                  {activePlans.map((p) => (
                    <option key={p.id} value={p.id} disabled={!p.is_active}>
                      {p.name}
                      {!p.is_active ? "（已停用）" : ""}
                      {p.price_monthly ? ` · ¥${p.price_monthly}/月` : ""}
                    </option>
                  ))}
                </select>
              </label>
              {selectedPlan && (
                <p className="rounded-lg bg-surface-muted px-3 py-2 text-xs cell-muted">
                  套餐默认：{selectedPlan.max_tokens_monthly.toLocaleString()} Token ·{" "}
                  {selectedPlan.max_storage_mb.toLocaleString()} MB · KB{" "}
                  {selectedPlan.max_knowledge_bases}
                </p>
              )}
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              <button
                type="button"
                className="btn-primary flex-1"
                disabled={savingSub}
                onClick={() => void saveSubscription()}
              >
                {savingSub ? "保存中…" : "保存订阅"}
              </button>
              <button
                type="button"
                className="btn-ghost"
                disabled={!selectedPlan}
                onClick={onApplyPlanQuota}
                title="将套餐默认配额填入左侧表单"
              >
                套用配额
              </button>
            </div>
          </section>

          <section className="card border-red-200 p-5">
            <h2 className="text-sm font-semibold text-red-700">危险操作</h2>
            <p className="mt-1 text-xs cell-muted">删除后租户业务数据不可恢复。</p>
            <button
              type="button"
              className="mt-3 text-sm text-red-600 hover:underline"
              onClick={() => void onDelete()}
            >
              删除租户
            </button>
          </section>
        </aside>
      </div>
    </div>
  );
}
