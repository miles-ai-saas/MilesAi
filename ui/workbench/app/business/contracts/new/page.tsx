"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, Suspense } from "react";
import { api } from "@/lib/api";
import type { BizClient, BizProject } from "@/lib/types";

const CONTRACT_TYPES = [{ key: "service", label: "服务合同" }, { key: "nda", label: "保密协议" }, { key: "framework", label: "框架协议" }, { key: "other", label: "其他" }];

function NewContractForm() {
  const router = useRouter();
  const [projects, setProjects] = useState<BizProject[]>([]);
  const [clients, setClients] = useState<BizClient[]>([]);
  const [projectId, setProjectId] = useState("");
  const [clientId, setClientId] = useState("");
  const [name, setName] = useState("");
  const [contractNo, setContractNo] = useState("");
  const [type, setType] = useState("service");
  const [totalAmount, setTotalAmount] = useState("");
  const [paymentTerms, setPaymentTerms] = useState("");
  const [desc, setDesc] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => { api.listProjects(1, 200).then((r) => setProjects(r.items)); api.listClients(1, 200).then((r) => setClients(r.items)); }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !projectId || !clientId) return;
    setSaving(true);
    try {
      const c = await api.createContract({
        project_id: projectId, client_id: clientId, name: name.trim(),
        contract_no: contractNo.trim() || undefined, type,
        total_amount: totalAmount ? Number(totalAmount) : undefined,
        payment_terms: paymentTerms.trim() || undefined,
        description: desc.trim() || undefined,
      });
      router.push(`/business/contracts/${c.id}`);
    } finally { setSaving(false); }
  };

  return (
    <div className="mx-auto max-w-xl">
      <h1 className="text-xl font-semibold text-ink">新建合同</h1>
      <form onSubmit={handleSubmit} className="mt-6 space-y-4">
        <label className="block">
          <span className="text-sm font-medium text-ink">所属项目 <span className="text-red-500">*</span></span>
          <select className="input-field mt-1 w-full" value={projectId} onChange={(e) => setProjectId(e.target.value)} required>
            <option value="">— 请选择 —</option>
            {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </label>
        <label className="block">
          <span className="text-sm font-medium text-ink">客户 <span className="text-red-500">*</span></span>
          <select className="input-field mt-1 w-full" value={clientId} onChange={(e) => setClientId(e.target.value)} required>
            <option value="">— 请选择 —</option>
            {clients.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </label>
        <label className="block">
          <span className="text-sm font-medium text-ink">合同名称 <span className="text-red-500">*</span></span>
          <input className="input-field mt-1 w-full" value={name} onChange={(e) => setName(e.target.value)} placeholder="如：XX 项目服务合同" required />
        </label>
        <div className="grid grid-cols-2 gap-4">
          <label className="block">
            <span className="text-sm font-medium text-ink">合同编号</span>
            <input className="input-field mt-1 w-full" value={contractNo} onChange={(e) => setContractNo(e.target.value)} placeholder="如 HT-2024-001" />
          </label>
          <label className="block">
            <span className="text-sm font-medium text-ink">类型</span>
            <select className="input-field mt-1 w-full" value={type} onChange={(e) => setType(e.target.value)}>
              {CONTRACT_TYPES.map((t) => <option key={t.key} value={t.key}>{t.label}</option>)}
            </select>
          </label>
        </div>
        <label className="block">
          <span className="text-sm font-medium text-ink">合同金额</span>
          <input className="input-field mt-1 w-full" type="number" value={totalAmount} onChange={(e) => setTotalAmount(e.target.value)} placeholder="¥" />
        </label>
        <label className="block">
          <span className="text-sm font-medium text-ink">付款条款</span>
          <input className="input-field mt-1 w-full" value={paymentTerms} onChange={(e) => setPaymentTerms(e.target.value)} placeholder="如：30% 预付 + 70% 验收后" />
        </label>
        <label className="block">
          <span className="text-sm font-medium text-ink">描述</span>
          <textarea className="input-field mt-1 w-full" rows={2} value={desc} onChange={(e) => setDesc(e.target.value)} />
        </label>
        <div className="flex items-center gap-3 pt-2">
          <button type="submit" disabled={saving || !name.trim() || !projectId || !clientId} className="btn-primary">{saving ? "保存中…" : "保存"}</button>
          <button type="button" onClick={() => router.back()} className="btn-ghost text-sm text-ink-muted">取消</button>
        </div>
      </form>
    </div>
  );
}

export default function NewContractPage() {
  return (
    <Suspense fallback={<p className="text-sm text-ink-muted">加载中…</p>}>
      <NewContractForm />
    </Suspense>
  );
}
