"use client";

/** 新建客户页。 */

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";

export default function NewClientPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [shortName, setShortName] = useState("");
  const [industry, setIndustry] = useState("");
  const [level, setLevel] = useState("normal");
  const [address, setAddress] = useState("");
  const [remark, setRemark] = useState("");
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    try {
      const client = await api.createClient({
        name: name.trim(),
        short_name: shortName.trim() || undefined,
        industry: industry || undefined,
        confidentiality_level: level,
        address: address.trim() || undefined,
        remark: remark.trim() || undefined,
      });
      router.push(`/business/clients/${client.id}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mx-auto max-w-lg">
      <h1 className="text-xl font-semibold text-ink">新建客户</h1>
      <p className="mt-1 text-sm text-ink-muted">填写客户基本信息</p>

      <form onSubmit={handleSubmit} className="mt-6 space-y-4">
        <label className="block">
          <span className="text-sm font-medium text-ink">客户名称 <span className="text-red-500">*</span></span>
          <input className="input-field mt-1 w-full" value={name} onChange={(e) => setName(e.target.value)} placeholder="如：某市文旅局" required />
        </label>
        <label className="block">
          <span className="text-sm font-medium text-ink">简称</span>
          <input className="input-field mt-1 w-full" value={shortName} onChange={(e) => setShortName(e.target.value)} placeholder="可选" />
        </label>
        <label className="block">
          <span className="text-sm font-medium text-ink">行业</span>
          <select className="input-field mt-1 w-full" value={industry} onChange={(e) => setIndustry(e.target.value)}>
            <option value="">—</option>
            <option value="government">政府机关</option>
            <option value="enterprise">企业</option>
            <option value="park">园区</option>
            <option value="commercial">商业综合体</option>
            <option value="tourism">文旅</option>
            <option value="other">其他</option>
          </select>
        </label>
        <label className="block">
          <span className="text-sm font-medium text-ink">保密等级</span>
          <select className="input-field mt-1 w-full" value={level} onChange={(e) => setLevel(e.target.value)}>
            <option value="normal">普通</option>
            <option value="internal">内部</option>
            <option value="restricted">涉密</option>
          </select>
        </label>
        <label className="block">
          <span className="text-sm font-medium text-ink">地址</span>
          <input className="input-field mt-1 w-full" value={address} onChange={(e) => setAddress(e.target.value)} placeholder="可选" />
        </label>
        <label className="block">
          <span className="text-sm font-medium text-ink">备注</span>
          <textarea className="input-field mt-1 w-full" rows={3} value={remark} onChange={(e) => setRemark(e.target.value)} placeholder="可选" />
        </label>

        <div className="flex items-center gap-3 pt-2">
          <button type="submit" disabled={saving || !name.trim()} className="btn-primary">
            {saving ? "保存中…" : "保存"}
          </button>
          <button type="button" onClick={() => router.back()} className="btn-ghost text-sm text-ink-muted">
            取消
          </button>
        </div>
      </form>
    </div>
  );
}
