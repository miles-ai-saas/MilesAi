"use client";

import Link from "next/link";
import { UsageQuotaRow } from "@/features/tenant/components/UsageQuotaRow";
import type { TenantDetailPageVm } from "@/features/tenant/hooks/use-tenant-detail-page";
import { TENANT_BILL_STATUS_LABEL } from "@/features/tenant/lib/tenant-detail-shared";

export function TenantDetailQuotaSection({ vm }: { vm: TenantDetailPageVm }) {
  const { tenant, setTenant, savingQuota, saveQuota } = vm;
  if (!tenant) return null;

  return (
    <section className="card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-ink">用量与配额</h2>
          <p className="mt-1 text-xs cell-muted">左侧查看实时用量，右侧直接调整上限；文档 {tenant.usage.documents} 份</p>
        </div>
        <button type="button" className="btn-primary" disabled={savingQuota} onClick={() => void saveQuota()}>
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
        <UsageQuotaRow label="智能体" used={tenant.usage.agents} max={tenant.max_agents} onMaxChange={(v) => setTenant({ ...tenant, max_agents: v })} />
        <UsageQuotaRow label="流程" used={tenant.usage.flows} max={tenant.max_flows} onMaxChange={(v) => setTenant({ ...tenant, max_flows: v })} />
      </div>
    </section>
  );
}

export function TenantDetailBillsSection({ vm }: { vm: TenantDetailPageVm }) {
  const { bills } = vm;

  return (
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
                    <span className="badge bg-brand-light text-ink">{TENANT_BILL_STATUS_LABEL[b.status] ?? b.status}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
