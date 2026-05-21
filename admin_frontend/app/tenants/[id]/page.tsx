"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { adminApi, type AdminTenantDetail, type BillingPlan } from "@/lib/api";
import { useRequireAdmin } from "@/lib/auth-store";

export default function TenantDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
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
    setMsg("基本信息已保存");
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

  const onDelete = async () => {
    if (!tenant || !confirm(`确定删除租户「${tenant.name}」？将清空其业务数据。`)) return;
    await adminApi.deleteTenant(id);
    router.push("/tenants");
  };

  if (!tenant) return <p className="text-ink-muted">加载中…</p>;

  return (
    <div className="max-w-3xl">
      <div className="mb-4 text-sm text-ink-muted">
        <Link href="/tenants" className="text-brand hover:underline">
          租户管理
        </Link>
        <span> / </span>
        <span>{tenant.name}</span>
      </div>

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
              {plans.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
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
        <div className="mt-3 grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
          <div className="rounded bg-surface-muted p-3">知识库 {tenant.usage.knowledge_bases}</div>
          <div className="rounded bg-surface-muted p-3">文档 {tenant.usage.documents}</div>
          <div className="rounded bg-surface-muted p-3">智能体 {tenant.usage.agents}</div>
          <div className="rounded bg-surface-muted p-3">流程 {tenant.usage.flows}</div>
          <div className="rounded bg-surface-muted p-3">用户 {tenant.usage.users}</div>
          <div className="rounded bg-surface-muted p-3">存储 {tenant.usage.storage_used_mb} MB</div>
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
        </div>
        <button type="button" onClick={saveQuota} className="btn-ghost mt-4">
          更新配额
        </button>
      </section>
    </div>
  );
}
