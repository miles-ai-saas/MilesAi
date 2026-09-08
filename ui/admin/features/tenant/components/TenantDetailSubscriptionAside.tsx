"use client";

import type { TenantDetailPageVm } from "@/features/tenant/hooks/use-tenant-detail-page";

export function TenantDetailSubscriptionAside({ vm }: { vm: TenantDetailPageVm }) {
  const { tenant, setTenant, activePlans, selectedPlan, savingSub, saveSubscription, onApplyPlanQuota, onDelete } = vm;
  if (!tenant) return null;

  return (
    <aside className="space-y-4">
      <section className="card p-5">
        <h2 className="text-sm font-semibold text-ink">订阅</h2>
        <div className="mt-4 space-y-3">
          <label className="block text-xs cell-muted">
            运营状态
            <select className="input-field mt-1" value={tenant.status} onChange={(e) => setTenant({ ...tenant, status: e.target.value })}>
              <option value="active">活跃</option>
              <option value="trial">试用</option>
              <option value="suspended">已停用</option>
            </select>
          </label>
          <label className="block text-xs cell-muted">
            计费套餐
            <select className="input-field mt-1" value={tenant.plan_id || ""} onChange={(e) => setTenant({ ...tenant, plan_id: e.target.value || null })}>
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
              套餐默认：{selectedPlan.max_tokens_monthly.toLocaleString()} Token · {selectedPlan.max_storage_mb.toLocaleString()} MB · KB{" "}
              {selectedPlan.max_knowledge_bases}
            </p>
          )}
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <button type="button" className="btn-primary flex-1" disabled={savingSub} onClick={() => void saveSubscription()}>
            {savingSub ? "保存中…" : "保存订阅"}
          </button>
          <button type="button" className="btn-ghost" disabled={!selectedPlan} onClick={onApplyPlanQuota} title="将套餐默认配额填入左侧表单">
            套用配额
          </button>
        </div>
      </section>

      <section className="card border-red-200 p-5">
        <h2 className="text-sm font-semibold text-red-700">危险操作</h2>
        <p className="mt-1 text-xs cell-muted">删除后租户业务数据不可恢复。</p>
        <button type="button" className="mt-3 text-sm text-red-600 hover:underline" onClick={() => void onDelete()}>
          删除租户
        </button>
      </section>
    </aside>
  );
}
