"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, Suspense } from "react";
import { api } from "@/lib/api";
import type { BizClient } from "@/lib/types";

const STAGES = [
  { key: "prospecting", label: "线索" },
  { key: "qualification", label: "资质确认" },
  { key: "proposal", label: "方案报价" },
  { key: "negotiation", label: "谈判" },
  { key: "won", label: "赢单" },
];

function NewOpportunityForm() {
  const router = useRouter();
  const search = useSearchParams();
  const preselectedClientId = search.get("client_id");
  const [clients, setClients] = useState<BizClient[]>([]);
  const [clientId, setClientId] = useState(preselectedClientId || "");
  const [name, setName] = useState("");
  const [stage, setStage] = useState("prospecting");
  const [expectedValue, setExpectedValue] = useState("");
  const [probability, setProbability] = useState("");
  const [desc, setDesc] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => { api.listClients(1, 100).then((r) => setClients(r.items)); }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !clientId) return;
    setSaving(true);
    try {
      const o = await api.createOpportunity({
        client_id: clientId, name: name.trim(), stage,
        expected_value: expectedValue ? Number(expectedValue) : undefined,
        probability: probability ? Number(probability) : undefined,
        description: desc.trim() || undefined,
      });
      router.push(`/business/opportunities/${o.id}`);
    } finally { setSaving(false); }
  };

  return (
    <div className="mx-auto max-w-xl">
      <h1 className="text-xl font-semibold text-ink">新建商机</h1>
      <form onSubmit={handleSubmit} className="mt-6 space-y-4">
        <label className="block">
          <span className="text-sm font-medium text-ink">客户 <span className="text-red-500">*</span></span>
          <select className="input-field mt-1 w-full" value={clientId} onChange={(e) => setClientId(e.target.value)} required>
            <option value="">— 请选择 —</option>
            {clients.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </label>
        <label className="block">
          <span className="text-sm font-medium text-ink">商机名称 <span className="text-red-500">*</span></span>
          <input className="input-field mt-1 w-full" value={name} onChange={(e) => setName(e.target.value)} placeholder="如：XX 公司年度品牌全案" required />
        </label>
        <label className="block">
          <span className="text-sm font-medium text-ink">阶段</span>
          <select className="input-field mt-1 w-full" value={stage} onChange={(e) => setStage(e.target.value)}>
            {STAGES.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
          </select>
        </label>
        <div className="grid grid-cols-2 gap-4">
          <label className="block">
            <span className="text-sm font-medium text-ink">预估金额</span>
            <input className="input-field mt-1 w-full" type="number" value={expectedValue} onChange={(e) => setExpectedValue(e.target.value)} placeholder="¥" />
          </label>
          <label className="block">
            <span className="text-sm font-medium text-ink">赢单概率 (%)</span>
            <input className="input-field mt-1 w-full" type="number" min="0" max="100" value={probability} onChange={(e) => setProbability(e.target.value)} placeholder="0-100" />
          </label>
        </div>
        <label className="block">
          <span className="text-sm font-medium text-ink">描述</span>
          <textarea className="input-field mt-1 w-full" rows={2} value={desc} onChange={(e) => setDesc(e.target.value)} />
        </label>
        <div className="flex items-center gap-3 pt-2">
          <button type="submit" disabled={saving || !name.trim() || !clientId} className="btn-primary">{saving ? "保存中…" : "保存"}</button>
          <button type="button" onClick={() => router.back()} className="btn-ghost text-sm text-ink-muted">取消</button>
        </div>
      </form>
    </div>
  );
}

export default function NewOpportunityPage() {
  return (
    <Suspense fallback={<p className="text-sm text-ink-muted">加载中…</p>}>
      <NewOpportunityForm />
    </Suspense>
  );
}
