/** 合同详情页 —— 两个标签页：
 * - 基本信息：合同属性、类型、金额、付款条款
 * - 收付款记录：合同项下收付款 CRUD，含财务概览和状态确认
 */

"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { BizContract, BizPayment } from "@/lib/types";

const STATUS_LABELS: Record<string, string> = { draft: "草稿", pending_sign: "待签署", signed: "已签署", active: "履约中", completed: "已完结", terminated: "已终止" };
const TYPE_LABELS: Record<string, string> = { service: "服务合同", nda: "保密协议", framework: "框架协议", other: "其他" };
const PAY_STATUS: Record<string, string> = { pending: "待收付", processing: "处理中", paid: "已结清", cancelled: "已取消" };
const DIR_LABEL: Record<string, string> = { in: "收款", out: "付款" };

export default function ContractDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [contract, setContract] = useState<BizContract | null>(null);
  const [payments, setPayments] = useState<BizPayment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<"info" | "payments">("info");

  useEffect(() => {
    api.getContract(id).then(setContract).catch((e) => setError(e?.message ?? "加载失败")).finally(() => setLoading(false));
  }, [id]);

  const loadPayments = () => api.listPayments(id).then(setPayments);

  const handleTabChange = (t: "info" | "payments") => {
    setTab(t);
    if (t === "payments") loadPayments();
  };

  if (loading) return <p className="text-sm text-ink-muted">加载中…</p>;
  if (error || !contract) return <p className="text-sm text-red-600">{error || "合同不存在"}</p>;

  return (
    <div>
      <button type="button" onClick={() => router.back()} className="mb-4 text-xs text-brand hover:underline">← 返回合同列表</button>
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold text-ink">{contract.name}</h1>
          <p className="text-sm text-ink-muted">
            {TYPE_LABELS[contract.type] ?? contract.type}
            {contract.contract_no ? ` · ${contract.contract_no}` : ""}
          </p>
        </div>
        <span className={`rounded px-2 py-0.5 text-xs ${contract.status === "active" ? "bg-brand-light text-brand" : contract.status === "signed" ? "bg-green-50 text-green-700" : contract.status === "terminated" ? "bg-red-50 text-red-600" : "bg-surface-muted text-ink-muted"}`}>
          {STATUS_LABELS[contract.status] ?? contract.status}
        </span>
      </div>

      <div className="mt-6 flex gap-1 border-b border-line">
        {(["info", "payments"] as const).map((t) => (
          <button key={t} type="button" className={`px-4 py-2 text-sm font-medium transition ${tab === t ? "-mb-px border-b-2 border-brand text-brand" : "text-ink-muted hover:text-ink"}`} onClick={() => handleTabChange(t)}>
            {t === "info" ? "基本信息" : `收付款 (${payments.length})`}
          </button>
        ))}
      </div>

      {tab === "info" && <InfoTab contract={contract} />}
      {tab === "payments" && <PaymentsTab contractId={id} projectId={contract.project_id} payments={payments} onRefresh={loadPayments} />}
    </div>
  );
}

function InfoTab({ contract }: { contract: BizContract }) {
  return (
    <div className="mt-6 grid gap-4 sm:grid-cols-2">
      <div className="card p-4"><p className="text-xs text-ink-faint">合同金额</p><p className="mt-1 text-sm font-medium text-ink">{contract.total_amount != null ? `¥${contract.total_amount.toLocaleString()}` : "—"}</p></div>
      <div className="card p-4"><p className="text-xs text-ink-faint">付款条款</p><p className="mt-1 text-sm font-medium text-ink">{contract.payment_terms || "—"}</p></div>
      <div className="card p-4"><p className="text-xs text-ink-faint">签署日期</p><p className="mt-1 text-sm font-medium text-ink">{contract.signed_date || "—"}</p></div>
      <div className="card p-4"><p className="text-xs text-ink-faint">有效期</p><p className="mt-1 text-sm font-medium text-ink">{contract.start_date ? `${contract.start_date} ~ ${contract.end_date || "—"}` : "—"}</p></div>
      <div className="card p-4 sm:col-span-2"><p className="text-xs text-ink-faint">描述</p><p className="mt-1 text-sm text-ink">{contract.description || "—"}</p></div>
    </div>
  );
}

function PaymentsTab({ contractId, projectId, payments, onRefresh }: { contractId: string; projectId: string; payments: BizPayment[]; onRefresh: () => void }) {
  const [name, setName] = useState("");
  const [direction, setDirection] = useState("in");
  const [amount, setAmount] = useState("");
  const [plannedDate, setPlannedDate] = useState("");
  const [method, setMethod] = useState("");
  const [saving, setSaving] = useState(false);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !amount) return;
    setSaving(true);
    try {
      await api.createPayment({ contract_id: contractId, project_id: projectId, name: name.trim(), direction, amount: Number(amount), planned_date: plannedDate || undefined, method: method || undefined });
      setName(""); setAmount(""); setPlannedDate("");
      onRefresh();
    } finally { setSaving(false); }
  };

  const handleStatus = async (p: BizPayment, status: string) => {
    await api.updatePayment(p.id, { status, paid_date: status === "paid" ? new Date().toISOString().slice(0, 10) : undefined });
    onRefresh();
  };

  const totalIn = payments.filter((p) => p.direction === "in").reduce((s, p) => s + p.amount, 0);
  const totalOut = payments.filter((p) => p.direction === "out").reduce((s, p) => s + p.amount, 0);

  return (
    <div className="mt-4 space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div className="card p-4"><p className="text-xs text-ink-faint">应收合计</p><p className="mt-1 text-lg font-semibold text-emerald-700">¥{totalIn.toLocaleString()}</p></div>
        <div className="card p-4"><p className="text-xs text-ink-faint">应付合计</p><p className="mt-1 text-lg font-semibold text-amber-700">¥{totalOut.toLocaleString()}</p></div>
      </div>

      <form onSubmit={handleAdd} className="card flex flex-wrap items-end gap-3 p-4">
        <label className="flex-1">
          <span className="text-xs text-ink-muted">摘要</span>
          <input className="input-field mt-1 w-full text-sm" value={name} onChange={(e) => setName(e.target.value)} placeholder="如：第一期款项" required />
        </label>
        <label>
          <span className="text-xs text-ink-muted">方向</span>
          <select className="input-field mt-1 text-sm" value={direction} onChange={(e) => setDirection(e.target.value)}>
            <option value="in">收款</option><option value="out">付款</option>
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
        <div key={p.id} className="card flex items-center justify-between p-4">
          <div>
            <div className="flex items-center gap-2">
              <span className={`rounded px-2 py-0.5 text-xs ${p.direction === "in" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}`}>{DIR_LABEL[p.direction] ?? p.direction}</span>
              <span className="font-medium text-ink">{p.name}</span>
            </div>
            {p.planned_date && <p className="mt-1 text-xs text-ink-muted">计划 {p.planned_date}{p.paid_date ? ` · 实付 ${p.paid_date}` : ""}</p>}
          </div>
          <div className="flex items-center gap-3">
            <span className="font-medium text-ink">¥{p.amount.toLocaleString()}</span>
            <span className={`rounded px-2 py-0.5 text-xs ${p.status === "paid" ? "bg-green-50 text-green-700" : "bg-surface-muted text-ink-muted"}`}>{PAY_STATUS[p.status] ?? p.status}</span>
            {p.status === "pending" && (
              <button type="button" className="text-xs text-brand hover:underline" onClick={() => handleStatus(p, "paid")}>确认</button>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
