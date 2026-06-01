"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { SUPPLIER_CATEGORIES } from "@/features/suppliers/lib/supplier-labels";

export default function NewSupplierPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [shortName, setShortName] = useState("");
  const [category, setCategory] = useState("other");
  const [status, setStatus] = useState("active");
  const [contactName, setContactName] = useState("");
  const [contactPhone, setContactPhone] = useState("");
  const [contactEmail, setContactEmail] = useState("");
  const [address, setAddress] = useState("");
  const [bankName, setBankName] = useState("");
  const [bankAccount, setBankAccount] = useState("");
  const [remark, setRemark] = useState("");
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    try {
      const supplier = await api.createSupplier({
        name: name.trim(),
        short_name: shortName.trim() || undefined,
        category,
        status,
        contact_name: contactName.trim() || undefined,
        contact_phone: contactPhone.trim() || undefined,
        contact_email: contactEmail.trim() || undefined,
        address: address.trim() || undefined,
        bank_name: bankName.trim() || undefined,
        bank_account: bankAccount.trim() || undefined,
        remark: remark.trim() || undefined,
      });
      router.push(`/business/suppliers/${supplier.id}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mx-auto max-w-lg">
      <h1 className="text-xl font-semibold text-ink">新建供应商</h1>
      <p className="mt-1 text-sm text-ink-muted">填写外包合作方基本信息</p>

      <form onSubmit={handleSubmit} className="mt-6 space-y-4">
        <label className="block">
          <span className="text-sm font-medium text-ink">名称 <span className="text-red-500">*</span></span>
          <input className="input-field mt-1 w-full" value={name} onChange={(e) => setName(e.target.value)} placeholder="如：某某印刷厂" required />
        </label>
        <label className="block">
          <span className="text-sm font-medium text-ink">简称</span>
          <input className="input-field mt-1 w-full" value={shortName} onChange={(e) => setShortName(e.target.value)} />
        </label>
        <label className="block">
          <span className="text-sm font-medium text-ink">类型</span>
          <select className="input-field mt-1 w-full" value={category} onChange={(e) => setCategory(e.target.value)}>
            {SUPPLIER_CATEGORIES.map((c) => <option key={c.key} value={c.key}>{c.label}</option>)}
          </select>
        </label>
        <label className="block">
          <span className="text-sm font-medium text-ink">状态</span>
          <select className="input-field mt-1 w-full" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="active">合作中</option>
            <option value="inactive">暂停合作</option>
            <option value="blacklisted">黑名单</option>
          </select>
        </label>
        <label className="block">
          <span className="text-sm font-medium text-ink">主联系人</span>
          <input className="input-field mt-1 w-full" value={contactName} onChange={(e) => setContactName(e.target.value)} />
        </label>
        <label className="block">
          <span className="text-sm font-medium text-ink">联系电话</span>
          <input className="input-field mt-1 w-full" value={contactPhone} onChange={(e) => setContactPhone(e.target.value)} />
        </label>
        <label className="block">
          <span className="text-sm font-medium text-ink">邮箱</span>
          <input type="email" className="input-field mt-1 w-full" value={contactEmail} onChange={(e) => setContactEmail(e.target.value)} />
        </label>
        <label className="block">
          <span className="text-sm font-medium text-ink">地址</span>
          <input className="input-field mt-1 w-full" value={address} onChange={(e) => setAddress(e.target.value)} />
        </label>
        <label className="block">
          <span className="text-sm font-medium text-ink">开户行</span>
          <input className="input-field mt-1 w-full" value={bankName} onChange={(e) => setBankName(e.target.value)} />
        </label>
        <label className="block">
          <span className="text-sm font-medium text-ink">银行账号</span>
          <input className="input-field mt-1 w-full" value={bankAccount} onChange={(e) => setBankAccount(e.target.value)} />
        </label>
        <label className="block">
          <span className="text-sm font-medium text-ink">备注</span>
          <textarea className="input-field mt-1 w-full" rows={3} value={remark} onChange={(e) => setRemark(e.target.value)} />
        </label>
        <div className="flex items-center gap-3 pt-2">
          <button type="submit" disabled={saving || !name.trim()} className="btn-primary">{saving ? "保存中…" : "保存"}</button>
          <button type="button" onClick={() => router.back()} className="btn-ghost text-sm text-ink-muted">取消</button>
        </div>
      </form>
    </div>
  );
}
