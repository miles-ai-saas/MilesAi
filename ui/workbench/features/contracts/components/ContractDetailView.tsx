"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { ContractDetailPageVm } from "@/features/contracts/hooks/use-contract-detail-page";
import {
  CONTRACT_STATUS_LABELS,
  CONTRACT_TYPE_LABELS,
  PAYMENT_DIRECTION_LABELS,
  PAYMENT_STATUS_LABELS,
  contractStatusBadgeClass,
} from "@/features/contracts/lib/contract-labels";
import type { BizContract, BizPayment } from "@/lib/types";

export function ContractDetailView({
  vm,
  embedded = false,
}: {
  vm: ContractDetailPageVm;
  embedded?: boolean;
}) {
  const { contract, payments, loading, error, tab, handleTabChange, loadPayments, onMutated } = vm;

  if (loading) return <p className="text-sm text-ink-muted">加载中…</p>;
  if (error || !contract) return <p className="text-sm text-red-600">{error || "合同不存在"}</p>;

  const subtitle = [
    CONTRACT_TYPE_LABELS[contract.type] ?? contract.type,
    contract.contract_no,
  ].filter(Boolean).join(" · ");

  return (
    <div className={embedded ? "w-full" : undefined}>
      {!embedded ? (
        <div className="flex items-start justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold text-ink">{contract.name}</h1>
            {subtitle ? <p className="text-sm text-ink-muted">{subtitle}</p> : null}
          </div>
          <span className={`rounded px-2 py-0.5 text-xs ${contractStatusBadgeClass(contract.status)}`}>
            {CONTRACT_STATUS_LABELS[contract.status] ?? contract.status}
          </span>
        </div>
      ) : (
        <div className="mb-4 flex items-center justify-end">
          <span className={`rounded px-2 py-0.5 text-xs ${contractStatusBadgeClass(contract.status)}`}>
            {CONTRACT_STATUS_LABELS[contract.status] ?? contract.status}
          </span>
        </div>
      )}

      <div className={`flex gap-1 border-b border-line ${embedded ? "mt-0" : "mt-6"}`}>
        {(["info", "payments"] as const).map((t) => (
          <button
            key={t}
            type="button"
            className={`px-4 py-2 text-sm font-medium transition ${tab === t ? "-mb-px border-b-2 border-brand text-brand" : "text-ink-muted hover:text-ink"}`}
            onClick={() => handleTabChange(t)}
          >
            {t === "info" ? "基本信息" : `收付款${tab === "payments" || payments.length > 0 ? ` (${payments.length})` : ""}`}
          </button>
        ))}
      </div>

      {tab === "info" && <ContractInfoTab contract={contract} embedded={embedded} />}
      {tab === "payments" && (
        <ContractPaymentsTab
          contractId={contract.id}
          projectId={contract.project_id}
          payments={payments}
          onRefresh={() => {
            void loadPayments();
            onMutated?.();
          }}
          embedded={embedded}
        />
      )}
    </div>
  );
}

function ContractInfoTab({ contract, embedded }: { contract: BizContract; embedded?: boolean }) {
  return (
    <div className={`grid gap-4 sm:grid-cols-2 ${embedded ? "mt-4" : "mt-6"}`}>
      <InfoCard label="合同金额" value={contract.total_amount != null ? `¥${contract.total_amount.toLocaleString()}` : "—"} />
      <InfoCard label="付款条款" value={contract.payment_terms || "—"} />
      <InfoCard label="签署日期" value={contract.signed_date || "—"} />
      <InfoCard label="有效期" value={contract.start_date ? `${contract.start_date} ~ ${contract.end_date || "—"}` : "—"} />
      <InfoCard label="描述" value={contract.description || "—"} className="sm:col-span-2" />
    </div>
  );
}

function ContractPaymentsTab({
  contractId,
  projectId,
  payments,
  onRefresh,
  embedded,
}: {
  contractId: string;
  projectId: string;
  payments: BizPayment[];
  onRefresh: () => void;
  embedded?: boolean;
}) {
  const [name, setName] = useState("");
  const [direction, setDirection] = useState("in");
  const [amount, setAmount] = useState("");
  const [plannedDate, setPlannedDate] = useState("");
  const [saving, setSaving] = useState(false);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !amount) return;
    setSaving(true);
    try {
      await api.createPayment({
        contract_id: contractId,
        project_id: projectId,
        name: name.trim(),
        direction,
        amount: Number(amount),
        planned_date: plannedDate || undefined,
      });
      setName("");
      setAmount("");
      setPlannedDate("");
      onRefresh();
    } finally {
      setSaving(false);
    }
  };

  const handleStatus = async (p: BizPayment, status: string) => {
    await api.updatePayment(p.id, {
      status,
      paid_date: status === "paid" ? new Date().toISOString().slice(0, 10) : undefined,
    });
    onRefresh();
  };

  const totalIn = payments.filter((p) => p.direction === "in").reduce((s, p) => s + p.amount, 0);
  const totalOut = payments.filter((p) => p.direction === "out").reduce((s, p) => s + p.amount, 0);

  return (
    <div className={`space-y-4 ${embedded ? "mt-4" : "mt-4"}`}>
      <div className="grid grid-cols-2 gap-4">
        <div className="card p-4">
          <p className="text-xs text-ink-faint">应收合计</p>
          <p className="mt-1 text-lg font-semibold text-emerald-700">¥{totalIn.toLocaleString()}</p>
        </div>
        <div className="card p-4">
          <p className="text-xs text-ink-faint">应付合计</p>
          <p className="mt-1 text-lg font-semibold text-amber-700">¥{totalOut.toLocaleString()}</p>
        </div>
      </div>

      <form onSubmit={handleAdd} className="card flex flex-wrap items-end gap-3 p-4">
        <label className="min-w-[8rem] flex-1">
          <span className="text-xs text-ink-muted">摘要</span>
          <input className="input-field mt-1 w-full text-sm" value={name} onChange={(e) => setName(e.target.value)} placeholder="如：第一期款项" required />
        </label>
        <label>
          <span className="text-xs text-ink-muted">方向</span>
          <select className="input-field mt-1 text-sm" value={direction} onChange={(e) => setDirection(e.target.value)}>
            <option value="in">收款</option>
            <option value="out">付款</option>
          </select>
        </label>
        <label>
          <span className="text-xs text-ink-muted">金额</span>
          <input className="input-field mt-1 w-28 text-sm" type="number" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="¥" required />
        </label>
        <label>
          <span className="text-xs text-ink-muted">计划日期</span>
          <input className="input-field mt-1 w-32 text-sm" type="date" value={plannedDate} onChange={(e) => setPlannedDate(e.target.value)} />
        </label>
        <button type="submit" disabled={saving} className="btn-primary text-sm">{saving ? "添加中…" : "添加"}</button>
      </form>

      {payments.length === 0 && <p className="text-sm text-ink-faint">暂无收付款记录</p>}
      {payments.map((p) => (
        <div key={p.id} className="card flex flex-wrap items-center justify-between gap-3 p-4">
          <div>
            <div className="flex items-center gap-2">
              <span className={`rounded px-2 py-0.5 text-xs ${p.direction === "in" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}`}>
                {PAYMENT_DIRECTION_LABELS[p.direction] ?? p.direction}
              </span>
              <span className="font-medium text-ink">{p.name}</span>
            </div>
            {p.planned_date && (
              <p className="mt-1 text-xs text-ink-muted">
                计划 {p.planned_date}{p.paid_date ? ` · 实付 ${p.paid_date}` : ""}
              </p>
            )}
          </div>
          <div className="flex items-center gap-3">
            <span className="font-medium text-ink">¥{p.amount.toLocaleString()}</span>
            <span className={`rounded px-2 py-0.5 text-xs ${p.status === "paid" ? "bg-green-50 text-green-700" : "bg-surface-muted text-ink-muted"}`}>
              {PAYMENT_STATUS_LABELS[p.status] ?? p.status}
            </span>
            {p.status === "pending" && (
              <button type="button" className="text-xs text-brand hover:underline" onClick={() => void handleStatus(p, "paid")}>
                确认
              </button>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

function InfoCard({ label, value, className = "" }: { label: string; value: string; className?: string }) {
  return (
    <div className={`card p-4 ${className}`}>
      <p className="text-xs text-ink-faint">{label}</p>
      <p className="mt-1 text-sm font-medium text-ink">{value}</p>
    </div>
  );
}
