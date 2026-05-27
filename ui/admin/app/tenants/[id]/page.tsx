"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { adminApi, type AdminTenantDetail, type BillingPlan } from "@/lib/api";
import { useRequireAdmin } from "@/lib/auth-store";

function UsageBar({
  label,
  used,
  max,
  unit = "",
}: {
  label: string;
  used: number;
  max: number;
  unit?: string;
}) {
  const pct = max > 0 ? Math.min(100, Math.round((used / max) * 100)) : 0;
  const warn = pct >= 90;
  return (
    <div className="rounded-lg bg-surface-muted p-3">
      <div className="flex items-center justify-between text-xs text-ink-muted">
        <span>{label}</span>
        <span className={warn ? "text-amber-600" : ""}>
          {used.toLocaleString()}
          {unit} / {max.toLocaleString()}
          {unit} ({pct}%)
        </span>
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-line-soft">
        <div
          className={`h-full rounded-full ${warn ? "bg-amber-500" : "bg-brand"}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export default function TenantDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const ready = useRequireAdmin();
  const [tenant, setTenant] = useState<AdminTenantDetail | null>(null);
  const [plans, setPlans] = useState<BillingPlan[]>([]);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const reload = async () => {
    const [t, p, usage] = await Promise.all([
      adminApi.getTenant(id),
      adminApi.listPlans(),
      adminApi.getTenantUsage(id),
    ]);
    setTenant({ ...t, usage });
    setPlans(p);
  };

  useEffect(() => {
    if (!ready) return;
    reload().catch(() => undefined);
  }, [ready, id]);

  const save = async () => {
    if (!tenant) return;
    setErr("");
    try {
      await adminApi.updateTenant(id, {
        status: tenant.status,
        plan_id: tenant.plan_id,
        is_active: tenant.is_active,
      });
      setMsg("基本信息已保存");
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "保存失败");
    }
  };

  const saveQuota = async () => {
    if (!tenant) return;
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
    }
  };

  const onDelete = async () => {
    if (!tenant || !confirm(`确定删除租户「${tenant.name}」？将清空其业务数据。`)) return;
    await adminApi.deleteTenant(id);
    router.push("/tenants");
  };

  if (!tenant) return <p className="text-ink-muted">加载中…</p>;

  const activePlans = plans.filter((p) => p.is_active || p.id === tenant.plan_id);

  return (
    <div className="max-w-3xl">
      <PageHeader
        title={tenant.name}
        description={`创建于 ${tenant.created_at.slice(0, 10)}`}
        action={
          <button type="button" onClick={onDelete} className="text-sm text-red-600 hover:underline">
            删除租户
          </button>
        }
      />
      {msg && <p className="mb-4 text-sm text-emerald-600">{msg}</p>}
      {err && <p className="mb-4 text-sm text-red-600">{err}</p>}

      <section className="card mb-6 p-4">
        <h2 className="text-sm font-semibold">基本信息</h2>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <label className="text-xs text-ink-muted">
            状态
            <select
              className="input-field mt-1"
              value={tenant.status}
              onChange={(e) => setTenant({ ...tenant, status: e.target.value })}
            >
              <option value="active">active</option>
              <option value="trial">trial</option>
              <option value="suspended">suspended</option>
            </select>
          </label>
          <label className="text-xs text-ink-muted">
            套餐
            <select
              className="input-field mt-1"
              value={tenant.plan_id || ""}
              onChange={(e) => setTenant({ ...tenant, plan_id: e.target.value || null })}
            >
              <option value="">无</option>
              {activePlans.map((p) => (
                <option key={p.id} value={p.id} disabled={!p.is_active}>
                  {p.name}
                  {!p.is_active ? "（已停用）" : ""}
                </option>
              ))}
            </select>
          </label>
        </div>
        <button type="button" onClick={save} className="btn-primary mt-4">
          保存
        </button>
      </section>

      <section className="card mb-6 p-4">
        <h2 className="text-sm font-semibold">使用统计</h2>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <div className="rounded-lg bg-surface-muted p-3 text-sm">
            知识库 {tenant.usage.knowledge_bases} · 文档 {tenant.usage.documents}
          </div>
          <div className="rounded-lg bg-surface-muted p-3 text-sm">
            智能体 {tenant.usage.agents} · 流程 {tenant.usage.flows} · 用户 {tenant.usage.users}
          </div>
        </div>
        <div className="mt-4 space-y-3">
          <UsageBar
            label="Token（本月）"
            used={tenant.usage.tokens_used_month}
            max={tenant.max_tokens_monthly}
          />
          <UsageBar label="存储" used={tenant.usage.storage_used_mb} max={tenant.max_storage_mb} unit=" MB" />
          <UsageBar
            label="知识库数量"
            used={tenant.usage.knowledge_bases}
            max={tenant.max_knowledge_bases}
          />
          <UsageBar label="智能体" used={tenant.usage.agents} max={tenant.max_agents} />
          <UsageBar label="流程" used={tenant.usage.flows} max={tenant.max_flows} />
        </div>
      </section>

      <section className="card p-4">
        <h2 className="text-sm font-semibold">额度管理</h2>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <label className="text-xs text-ink-muted">
            Token 月额度
            <input
              type="number"
              className="input-field mt-1"
              value={tenant.max_tokens_monthly}
              onChange={(e) =>
                setTenant({ ...tenant, max_tokens_monthly: Number(e.target.value) })
              }
            />
          </label>
          <label className="text-xs text-ink-muted">
            存储 MB
            <input
              type="number"
              className="input-field mt-1"
              value={tenant.max_storage_mb}
              onChange={(e) => setTenant({ ...tenant, max_storage_mb: Number(e.target.value) })}
            />
          </label>
          <label className="text-xs text-ink-muted">
            知识库上限
            <input
              type="number"
              className="input-field mt-1"
              value={tenant.max_knowledge_bases}
              onChange={(e) =>
                setTenant({ ...tenant, max_knowledge_bases: Number(e.target.value) })
              }
            />
          </label>
          <label className="text-xs text-ink-muted">
            智能体上限
            <input
              type="number"
              className="input-field mt-1"
              value={tenant.max_agents}
              onChange={(e) => setTenant({ ...tenant, max_agents: Number(e.target.value) })}
            />
          </label>
          <label className="text-xs text-ink-muted">
            流程上限
            <input
              type="number"
              className="input-field mt-1"
              value={tenant.max_flows}
              onChange={(e) => setTenant({ ...tenant, max_flows: Number(e.target.value) })}
            />
          </label>
        </div>
        <button type="button" onClick={saveQuota} className="btn-ghost mt-4">
          更新配额
        </button>
      </section>
    </div>
  );
}
