"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { BizPageHero } from "@/features/business-dashboard/components/BizPageHero";
import { BizListPageSkeleton } from "@/features/business/components/BizListSkeleton";
import { ExportCsvButton } from "@/features/business/components/ExportCsvButton";
import { useBizPermissions } from "@/features/business/lib/biz-permissions";
import {
  PAYMENT_DIRECTION_LABELS,
  PAYMENT_STATUS_LABELS,
} from "@/features/contracts/lib/contract-labels";
import { StatChip } from "@/components/ui/StatChip";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import type { BizPayment, FinancialSummary } from "@/lib/types";

function paymentDirectionBadge(direction: string): string {
  return direction === "in" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700";
}

export function useFinancePage() {
  const { ready } = useRequireAuth();
  const [summary, setSummary] = useState<FinancialSummary | null>(null);
  const [pending, setPending] = useState<BizPayment[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionId, setActionId] = useState<string | null>(null);

  const reload = useCallback(async () => {
    const [s, p] = await Promise.all([api.getFinancialSummary(), api.listPendingPayments()]);
    setSummary(s);
    setPending(p);
  }, []);

  useEffect(() => {
    if (!ready) return;
    reload().finally(() => setLoading(false));
  }, [ready, reload]);

  const markPaid = async (paymentId: string) => {
    setActionId(paymentId);
    try {
      await api.updatePayment(paymentId, {
        status: "paid",
        paid_date: new Date().toISOString().slice(0, 10),
      });
      await reload();
    } finally {
      setActionId(null);
    }
  };

  return { ready, summary, pending, loading, actionId, markPaid, reload };
}

export type FinancePageVm = ReturnType<typeof useFinancePage>;

function PendingPaymentMobileCard({
  payment,
  canWrite,
  actionId,
  onMarkPaid,
}: {
  payment: BizPayment;
  canWrite: boolean;
  actionId: string | null;
  onMarkPaid: (id: string) => void;
}) {
  return (
    <article className="card p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate font-medium text-ink">{payment.name}</h3>
          <p className="mt-1 text-sm tabular-nums text-ink">¥{payment.amount.toLocaleString()}</p>
        </div>
        <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs ${paymentDirectionBadge(payment.direction)}`}>
          {PAYMENT_DIRECTION_LABELS[payment.direction] ?? payment.direction}
        </span>
      </div>
      <div className="mt-3 flex flex-wrap gap-2 text-xs text-ink-muted">
        <span>{payment.planned_date ?? "无计划日期"}</span>
        <span>{PAYMENT_STATUS_LABELS[payment.status] ?? payment.status}</span>
      </div>
      <div className="mt-3 flex flex-wrap gap-3">
        {canWrite && payment.status === "pending" ? (
          <button
            type="button"
            className="text-xs text-brand hover:underline disabled:opacity-50"
            disabled={actionId === payment.id}
            onClick={() => onMarkPaid(payment.id)}
          >
            {actionId === payment.id ? "处理中…" : "标记结清"}
          </button>
        ) : null}
        <Link
          href={`/business/contracts?id=${payment.contract_id}`}
          className="text-xs text-ink-muted hover:text-brand hover:underline"
        >
          查看合同
        </Link>
      </div>
    </article>
  );
}

function PendingPaymentsList({
  pending,
  canWrite,
  actionId,
  onMarkPaid,
}: {
  pending: BizPayment[];
  canWrite: boolean;
  actionId: string | null;
  onMarkPaid: (id: string) => void;
}) {
  if (pending.length === 0) {
    return (
      <div className="px-4 py-16 text-center">
        <p className="text-sm text-ink-muted">暂无待收付记录</p>
        <p className="mt-1 text-xs text-ink-faint">可在合同详情中创建收付款计划</p>
      </div>
    );
  }

  return (
    <>
      <div className="space-y-3 p-3 md:hidden">
        {pending.map((payment) => (
          <PendingPaymentMobileCard
            key={payment.id}
            payment={payment}
            canWrite={canWrite}
            actionId={actionId}
            onMarkPaid={onMarkPaid}
          />
        ))}
      </div>

      <div className="hidden overflow-x-auto md:block">
        <table className="w-full min-w-[720px] text-left text-sm">
          <thead className="border-b border-line bg-surface-muted/60 text-xs text-ink-muted">
            <tr>
              <th className="px-4 py-2.5 font-medium">名称</th>
              <th className="px-4 py-2.5 font-medium">方向</th>
              <th className="px-4 py-2.5 font-medium">金额</th>
              <th className="px-4 py-2.5 font-medium">计划日期</th>
              <th className="px-4 py-2.5 font-medium">状态</th>
              <th className="px-4 py-2.5 text-right font-medium">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line-soft">
            {pending.map((payment) => (
              <tr key={payment.id} className="transition hover:bg-surface-muted/40">
                <td className="px-4 py-3 font-medium text-ink">{payment.name}</td>
                <td className="px-4 py-3">
                  <span className={`rounded-full px-2 py-0.5 text-xs ${paymentDirectionBadge(payment.direction)}`}>
                    {PAYMENT_DIRECTION_LABELS[payment.direction] ?? payment.direction}
                  </span>
                </td>
                <td className="px-4 py-3 tabular-nums text-ink-muted">¥{payment.amount.toLocaleString()}</td>
                <td className="px-4 py-3 text-ink-muted">{payment.planned_date ?? "—"}</td>
                <td className="px-4 py-3 text-xs text-ink-muted">
                  {PAYMENT_STATUS_LABELS[payment.status] ?? payment.status}
                </td>
                <td className="px-4 py-3 text-right">
                  <div className="flex flex-wrap items-center justify-end gap-2">
                    {canWrite && payment.status === "pending" ? (
                      <button
                        type="button"
                        className="text-xs text-brand hover:underline disabled:opacity-50"
                        disabled={actionId === payment.id}
                        onClick={() => onMarkPaid(payment.id)}
                      >
                        {actionId === payment.id ? "处理中…" : "标记结清"}
                      </button>
                    ) : null}
                    <Link
                      href={`/business/contracts?id=${payment.contract_id}`}
                      className="text-xs text-ink-muted hover:text-brand hover:underline"
                    >
                      查看合同
                    </Link>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

export function FinancePageView({ vm }: { vm: FinancePageVm }) {
  const { summary, pending, loading, actionId, markPaid, ready } = vm;
  const { canWritePayment } = useBizPermissions();

  const pendingIn = useMemo(
    () => pending.filter((p) => p.direction === "in").reduce((sum, p) => sum + p.amount, 0),
    [pending],
  );
  const pendingOut = useMemo(
    () => pending.filter((p) => p.direction === "out").reduce((sum, p) => sum + p.amount, 0),
    [pending],
  );

  if (!ready || loading || !summary) {
    return <BizListPageSkeleton statCount={5} />;
  }

  return (
    <div className="w-full">
      <BizPageHero
        flowStep="finance"
        compact
        subtitle="合同应收应付、待收付清单与结清操作"
        actions={
          <>
            <ExportCsvButton url={api.exportPaymentsCsv()} filename="biz-payments.csv" />
            <Link href="/business/contracts" className="btn-sm-outline text-sm">
              合同管理
            </Link>
          </>
        }
      />

      <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <Link href="/business/contracts" className="block transition hover:opacity-90">
          <StatChip label="合同总数" value={String(summary.contract_count)} hint="跳转合同列表" />
        </Link>
        <StatChip label="应收合计" value={`¥${summary.total_income.toLocaleString()}`} hint="全部合同应收" />
        <StatChip label="已结清" value={`¥${summary.total_paid.toLocaleString()}`} hint="已完成收付" />
        <StatChip
          label="待收款"
          value={`¥${summary.total_pending_in.toLocaleString()}`}
          hint={pendingIn > 0 ? `清单中 ¥${pendingIn.toLocaleString()}` : "无待收"}
        />
        <StatChip
          label="待付款"
          value={`¥${summary.total_pending_out.toLocaleString()}`}
          hint={pendingOut > 0 ? `清单中 ¥${pendingOut.toLocaleString()}` : "无待付"}
        />
      </div>

      <section className="card overflow-hidden">
        <div className="flex items-center justify-between border-b border-line bg-surface-muted/30 px-4 py-3">
          <h2 className="text-sm font-semibold text-ink">待收付清单</h2>
          <span className="text-xs text-ink-muted">{pending.length} 条</span>
        </div>
        <PendingPaymentsList
          pending={pending}
          canWrite={canWritePayment}
          actionId={actionId}
          onMarkPaid={(id) => void markPaid(id)}
        />
      </section>
    </div>
  );
}
