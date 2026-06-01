"use client";

import { ResourceDialog } from "@/components/resource/ResourceDialog";
import {
  CLIENT_CONFIDENTIALITY_OPTIONS,
  CLIENT_INDUSTRY_OPTIONS,
  type ClientFormValues,
} from "@/features/clients/lib/client-form-options";

type Props = {
  open: boolean;
  form: ClientFormValues;
  saving: boolean;
  onClose: () => void;
  onChange: (form: ClientFormValues) => void;
  onSave: () => void;
};

export function ClientFormDialog({ open, form, saving, onClose, onChange, onSave }: Props) {
  const set = (patch: Partial<ClientFormValues>) => onChange({ ...form, ...patch });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim() || saving) return;
    onSave();
  };

  return (
    <ResourceDialog
      open={open}
      title="新建客户"
      description="填写客户基本信息，保存后可继续添加联系人"
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn-ghost" onClick={onClose} disabled={saving}>
            取消
          </button>
          <button
            type="submit"
            form="client-create-form"
            className="btn-primary"
            disabled={saving || !form.name.trim()}
          >
            {saving ? "保存中…" : "保存"}
          </button>
        </>
      }
    >
      <form id="client-create-form" onSubmit={handleSubmit} className="space-y-4">
        <label className="block">
          <span className="text-sm font-medium text-ink">
            客户名称 <span className="text-red-500">*</span>
          </span>
          <input
            className="input-field mt-1 w-full"
            value={form.name}
            onChange={(e) => set({ name: e.target.value })}
            placeholder="如：某市文旅局"
            required
            autoFocus
          />
        </label>
        <label className="block">
          <span className="text-sm font-medium text-ink">简称</span>
          <input
            className="input-field mt-1 w-full"
            value={form.short_name}
            onChange={(e) => set({ short_name: e.target.value })}
            placeholder="可选"
          />
        </label>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="text-sm font-medium text-ink">行业</span>
            <select
              className="input-field mt-1 w-full"
              value={form.industry}
              onChange={(e) => set({ industry: e.target.value })}
            >
              {CLIENT_INDUSTRY_OPTIONS.map((o) => (
                <option key={o.value || "empty"} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-sm font-medium text-ink">保密等级</span>
            <select
              className="input-field mt-1 w-full"
              value={form.confidentiality_level}
              onChange={(e) => set({ confidentiality_level: e.target.value })}
            >
              {CLIENT_CONFIDENTIALITY_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
        </div>
        <label className="block">
          <span className="text-sm font-medium text-ink">地址</span>
          <input
            className="input-field mt-1 w-full"
            value={form.address}
            onChange={(e) => set({ address: e.target.value })}
            placeholder="可选"
          />
        </label>
        <label className="block">
          <span className="text-sm font-medium text-ink">备注</span>
          <textarea
            className="input-field mt-1 w-full"
            rows={3}
            value={form.remark}
            onChange={(e) => set({ remark: e.target.value })}
            placeholder="可选"
          />
        </label>
      </form>
    </ResourceDialog>
  );
}
