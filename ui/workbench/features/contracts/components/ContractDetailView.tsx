"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useBizPermissions } from "@/features/business/lib/biz-permissions";
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
  const { contract, payments, loading, error, tab, handleTabChange, loadPayments, onMutated, editingInfo, setEditingInfo, infoForm, setInfoForm, savingInfo, saveContractInfo } = vm;

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

      {tab === "info" && (
        <ContractInfoTab
          contract={contract}
          embedded={embedded}
          editing={editingInfo}
          onEdit={() => setEditingInfo(true)}
          onCancelEdit={() => setEditingInfo(false)}
          form={infoForm}
          setForm={setInfoForm}
          saving={savingInfo}
          onSave={saveContractInfo}
        />
      )}
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

function ContractInfoTab({
  contract,
  embedded,
  editing,
  onEdit,
  onCancelEdit,
  form,
  setForm,
  saving,
  onSave,
}: {
  contract: BizContract;
  embedded?: boolean;
  editing: boolean;
  onEdit: () => void;
  onCancelEdit: () => void;
  form: ContractDetailPageVm["infoForm"];
  setForm: React.Dispatch<React.SetStateAction<ContractDetailPageVm["infoForm"]>>;
  saving: boolean;
  onSave: (e: React.FormEvent) => void;
}) {
  const { canWriteContract } = useBizPermissions();

  if (editing) {
    return (
      <form onSubmit={onSave} className={`card space-y-3 p-4 ${embedded ? "mt-4" : "mt-6"}`}>
        <label className="block">
          <span className="text-xs text-ink-muted">合同名称</span>
          <input className="input-field mt-1 w-full text-sm" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} required />
        </label>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block">
            <span className="text-xs text-ink-muted">合同编号</span>
            <input className="input-field mt-1 w-full text-sm" value={form.contract_no} onChange={(e) => setForm((f) => ({ ...f, contract_no: e.target.value }))} />
          </label>
          <label className="block">
            <span className="text-xs text-ink-muted">类型</span>
            <select className="input-field mt-1 w-full text-sm" value={form.type} onChange={(e) => setForm((f) => ({ ...f, type: e.target.value }))}>
              {Object.entries(CONTRACT_TYPE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </label>
        </div>
        <label className="block">
          <span className="text-xs text-ink-muted">状态</span>
          <select className="input-field mt-1 w-full text-sm" value={form.status} onChange={(e) => setForm((f) => ({ ...f, status: e.target.value }))}>
            {Object.entries(CONTRACT_STATUS_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <label className="block">
          <span className="text-xs text-ink-muted">合同金额</span>
          <input type="number" className="input-field mt-1 w-full text-sm" value={form.total_amount} onChange={(e) => setForm((f) => ({ ...f, total_amount: e.target.value }))} />
        </label>
        <div className="grid gap-3 sm:grid-cols-3">
          <label className="block">
            <span className="text-xs text-ink-muted">签署日期</span>
            <input type="date" className="input-field mt-1 w-full text-sm" value={form.signed_date} onChange={(e) => setForm((f) => ({ ...f, signed_date: e.target.value }))} />
          </label>
          <label className="block">
            <span className="text-xs text-ink-muted">开始日期</span>
            <input type="date" className="input-field mt-1 w-full text-sm" value={form.start_date} onChange={(e) => setForm((f) => ({ ...f, start_date: e.target.value }))} />
          </label>
          <label className="block">
            <span className="text-xs text-ink-muted">结束日期</span>
            <input type="date" className="input-field mt-1 w-full text-sm" value={form.end_date} onChange={(e) => setForm((f) => ({ ...f, end_date: e.target.value }))} />
          </label>
        </div>
        <label className="block">
          <span className="text-xs text-ink-muted">付款条款</span>
          <input className="input-field mt-1 w-full text-sm" value={form.payment_terms} onChange={(e) => setForm((f) => ({ ...f, payment_terms: e.target.value }))} />
        </label>
        <label className="block">
          <span className="text-xs text-ink-muted">描述</span>
          <textarea className="input-field mt-1 w-full text-sm" rows={3} value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} />
        </label>
        <div className="flex gap-2">
          <button type="submit" disabled={saving} className="btn-primary text-sm">{saving ? "保存中…" : "保存"}</button>
          <button type="button" className="btn-ghost text-sm" onClick={onCancelEdit}>取消</button>
        </div>
      </form>
    );
  }

  return (
    <div className={`${embedded ? "mt-4" : "mt-6"}`}>
      {canWriteContract && (
        <div className="mb-3 flex justify-end">
          <button type="button" className="text-xs text-brand hover:underline" onClick={onEdit}>编辑</button>
        </div>
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        <InfoCard label="合同金额" value={contract.total_amount != null ? `¥${contract.total_amount.toLocaleString()}` : "—"} />
        <InfoCard label="付款条款" value={contract.payment_terms || "—"} />
        <InfoCard label="签署日期" value={contract.signed_date || "—"} />
        <InfoCard label="有效期" value={contract.start_date ? `${contract.start_date} ~ ${contract.end_date || "—"}` : "—"} />
        <InfoCard label="描述" value={contract.description || "—"} className="sm:col-span-2" />
      </div>
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
  const { canWritePayment } = useBizPermissions();
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

      {canWritePayment && (
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
      )}

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
            {canWritePayment && p.status === "pending" && (
              <button type="button" className="text-xs text-brand hover:underline" onClick={() => void handleStatus(p, "paid")}>
                确认结清
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
