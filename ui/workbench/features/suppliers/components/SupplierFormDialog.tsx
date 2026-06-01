"use client";

import { ResourceDialog } from "@/components/resource/ResourceDialog";
import {
  EMPTY_SUPPLIER_FORM,
  SUPPLIER_CATEGORIES,
  SUPPLIER_STATUS_OPTIONS,
  type SupplierFormValues,
} from "@/features/suppliers/lib/supplier-form-options";

type Props = {
  open: boolean;
  form: SupplierFormValues;
  saving: boolean;
  onClose: () => void;
  onChange: (form: SupplierFormValues) => void;
  onSave: () => void;
};

export function SupplierFormDialog({ open, form, saving, onClose, onChange, onSave }: Props) {
  const set = (patch: Partial<SupplierFormValues>) => onChange({ ...form, ...patch });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim() || saving) return;
    onSave();
  };

  return (
    <ResourceDialog
      open={open}
      title="新建供应商"
      description="填写外包合作方基本信息，保存后可继续添加联系人"
      onClose={onClose}
      size="lg"
      footer={
        <>
          <button type="button" className="btn-ghost" onClick={onClose} disabled={saving}>
            取消
          </button>
          <button
            type="submit"
            form="supplier-create-form"
            className="btn-primary"
            disabled={saving || !form.name.trim()}
          >
            {saving ? "保存中…" : "保存"}
          </button>
        </>
      }
    >
      <form id="supplier-create-form" onSubmit={handleSubmit} className="space-y-4">
        <label className="block">
          <span className="text-sm font-medium text-ink">
            名称 <span className="text-red-500">*</span>
          </span>
          <input
            className="input-field mt-1 w-full"
            value={form.name}
            onChange={(e) => set({ name: e.target.value })}
            placeholder="如：某某印刷厂"
            required
            autoFocus
          />
        </label>
        <label className="block">
          <span className="text-sm font-medium text-ink">简称</span>
          <input className="input-field mt-1 w-full" value={form.short_name} onChange={(e) => set({ short_name: e.target.value })} />
        </label>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="text-sm font-medium text-ink">类型</span>
            <select className="input-field mt-1 w-full" value={form.category} onChange={(e) => set({ category: e.target.value })}>
              {SUPPLIER_CATEGORIES.map((c) => (
                <option key={c.key} value={c.key}>{c.label}</option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-sm font-medium text-ink">状态</span>
            <select className="input-field mt-1 w-full" value={form.status} onChange={(e) => set({ status: e.target.value })}>
              {SUPPLIER_STATUS_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </label>
        </div>
        <label className="block">
          <span className="text-sm font-medium text-ink">主联系人</span>
          <input className="input-field mt-1 w-full" value={form.contact_name} onChange={(e) => set({ contact_name: e.target.value })} />
        </label>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="text-sm font-medium text-ink">联系电话</span>
            <input className="input-field mt-1 w-full" value={form.contact_phone} onChange={(e) => set({ contact_phone: e.target.value })} />
          </label>
          <label className="block">
            <span className="text-sm font-medium text-ink">邮箱</span>
            <input type="email" className="input-field mt-1 w-full" value={form.contact_email} onChange={(e) => set({ contact_email: e.target.value })} />
          </label>
        </div>
        <label className="block">
          <span className="text-sm font-medium text-ink">地址</span>
          <input className="input-field mt-1 w-full" value={form.address} onChange={(e) => set({ address: e.target.value })} />
        </label>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="text-sm font-medium text-ink">开户行</span>
            <input className="input-field mt-1 w-full" value={form.bank_name} onChange={(e) => set({ bank_name: e.target.value })} />
          </label>
          <label className="block">
            <span className="text-sm font-medium text-ink">银行账号</span>
            <input className="input-field mt-1 w-full" value={form.bank_account} onChange={(e) => set({ bank_account: e.target.value })} />
          </label>
        </div>
        <label className="block">
          <span className="text-sm font-medium text-ink">备注</span>
          <textarea className="input-field mt-1 w-full" rows={3} value={form.remark} onChange={(e) => set({ remark: e.target.value })} />
        </label>
      </form>
    </ResourceDialog>
  );
}
