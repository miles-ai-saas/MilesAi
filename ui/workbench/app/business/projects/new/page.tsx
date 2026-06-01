"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, Suspense } from "react";
import { api } from "@/lib/api";
import type { BizClient } from "@/lib/types";

const SERVICE_LINES = [
  { key: "brand_identity", label: "品牌形象" },
  { key: "video_production", label: "影视拍摄" },
  { key: "exhibition", label: "展览展示" },
  { key: "event", label: "活动策划" },
  { key: "training", label: "会务培训" },
  { key: "signage", label: "标识设计" },
  { key: "cultural_product", label: "文创产品" },
  { key: "print", label: "宣传品设计印刷" },
];

function NewProjectForm() {
  const router = useRouter();
  const search = useSearchParams();
  const preselectedClientId = search.get("client_id");
  const [clients, setClients] = useState<BizClient[]>([]);
  const [clientId, setClientId] = useState(preselectedClientId || "");
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [desc, setDesc] = useState("");
  const [wps, setWps] = useState<{ service_line: string; name: string }[]>([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.listClients(1, 200).then((r) => setClients(r.items));
  }, []);

  const addWorkPackage = () => setWps([...wps, { service_line: "", name: "" }]);
  const removeWorkPackage = (i: number) => setWps(wps.filter((_, idx) => idx !== i));
  const updateWp = (i: number, f: "service_line" | "name", v: string) => {
    setWps(wps.map((w, idx) => (idx === i ? { ...w, [f]: v } : w)));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !clientId) return;
    setSaving(true);
    try {
      const project = await api.createProject({
        client_id: clientId,
        name: name.trim(),
        code: code.trim() || undefined,
        description: desc.trim() || undefined,
        work_packages: wps.filter((w) => w.service_line && w.name.trim()),
      });
      router.push(`/business/projects/${project.id}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mx-auto max-w-xl">
      <h1 className="text-xl font-semibold text-ink">新建项目</h1>
      <p className="mt-1 text-sm text-ink-muted">填写项目信息并添加服务线工作包</p>

      <form onSubmit={handleSubmit} className="mt-6 space-y-4">
        <label className="block">
          <span className="text-sm font-medium text-ink">客户 <span className="text-red-500">*</span></span>
          <select className="input-field mt-1 w-full" value={clientId} onChange={(e) => setClientId(e.target.value)} required>
            <option value="">— 请选择 —</option>
            {clients.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </label>
        <label className="block">
          <span className="text-sm font-medium text-ink">项目名称 <span className="text-red-500">*</span></span>
          <input className="input-field mt-1 w-full" value={name} onChange={(e) => setName(e.target.value)} placeholder="如：XX 展馆整体设计" required />
        </label>
        <label className="block">
          <span className="text-sm font-medium text-ink">项目编号</span>
          <input className="input-field mt-1 w-full" value={code} onChange={(e) => setCode(e.target.value)} placeholder="可选" />
        </label>
        <label className="block">
          <span className="text-sm font-medium text-ink">描述</span>
          <textarea className="input-field mt-1 w-full" rows={2} value={desc} onChange={(e) => setDesc(e.target.value)} placeholder="可选" />
        </label>

        <div>
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-ink">工作包</span>
            <button type="button" className="text-xs text-brand hover:underline" onClick={addWorkPackage}>+ 添加</button>
          </div>
          {wps.map((w, i) => (
            <div key={i} className="mt-2 flex items-center gap-2">
              <select className="input-field flex-1 text-sm" value={w.service_line} onChange={(e) => updateWp(i, "service_line", e.target.value)}>
                <option value="">— 类型 —</option>
                {SERVICE_LINES.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
              </select>
              <input className="input-field flex-1 text-sm" value={w.name} onChange={(e) => updateWp(i, "name", e.target.value)} placeholder="名称" />
              <button type="button" className="text-xs text-red-500 hover:underline" onClick={() => removeWorkPackage(i)}>移除</button>
            </div>
          ))}
        </div>

        <div className="flex items-center gap-3 pt-2">
          <button type="submit" disabled={saving || !name.trim() || !clientId} className="btn-primary">
            {saving ? "保存中…" : "保存"}
          </button>
          <button type="button" onClick={() => router.back()} className="btn-ghost text-sm text-ink-muted">取消</button>
        </div>
      </form>
    </div>
  );
}

export default function NewProjectPage() {
  return (
    <Suspense fallback={<p className="text-sm text-ink-muted">加载中…</p>}>
      <NewProjectForm />
    </Suspense>
  );
}
