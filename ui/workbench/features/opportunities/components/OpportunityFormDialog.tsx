"use client";

import { ResourceDialog } from "@/components/resource/ResourceDialog";
import {
  EMPTY_OPPORTUNITY_FORM,
  OPPORTUNITY_CREATE_STAGES,
  type OpportunityFormValues,
} from "@/features/opportunities/lib/opportunity-form-options";
import type { BizClient } from "@/lib/types";

type Props = {
  open: boolean;
  form: OpportunityFormValues;
  clients: BizClient[];
  clientsLoading: boolean;
  saving: boolean;
  onClose: () => void;
  onChange: (form: OpportunityFormValues) => void;
  onSave: () => void;
};

export function OpportunityFormDialog({
  open,
  form,
  clients,
  clientsLoading,
  saving,
  onClose,
  onChange,
  onSave,
}: Props) {
  const set = (patch: Partial<OpportunityFormValues>) => onChange({ ...form, ...patch });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim() || !form.client_id || saving) return;
    onSave();
  };

  return (
    <ResourceDialog
      open={open}
      title="新建商机"
      description="关联客户并填写商机基本信息"
      onClose={onClose}
      size="lg"
      footer={
        <>
          <button type="button" className="btn-ghost" onClick={onClose} disabled={saving}>
            取消
          </button>
          <button
            type="submit"
            form="opportunity-create-form"
            className="btn-primary"
            disabled={saving || !form.name.trim() || !form.client_id}
          >
            {saving ? "保存中…" : "保存"}
          </button>
        </>
      }
    >
      <form id="opportunity-create-form" onSubmit={handleSubmit} className="space-y-4">
        <label className="block">
          <span className="text-sm font-medium text-ink">
            客户 <span className="text-red-500">*</span>
          </span>
          <select
            className="input-field mt-1 w-full"
            value={form.client_id}
            onChange={(e) => set({ client_id: e.target.value })}
            required
            disabled={clientsLoading}
          >
            <option value="">— 请选择 —</option>
            {clients.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="text-sm font-medium text-ink">
            商机名称 <span className="text-red-500">*</span>
          </span>
          <input
            className="input-field mt-1 w-full"
            value={form.name}
            onChange={(e) => set({ name: e.target.value })}
            placeholder="如：XX 公司年度品牌全案"
            required
            autoFocus={Boolean(form.client_id)}
          />
        </label>
        <label className="block">
          <span className="text-sm font-medium text-ink">阶段</span>
          <select
            className="input-field mt-1 w-full"
            value={form.stage}
            onChange={(e) => set({ stage: e.target.value })}
          >
            {OPPORTUNITY_CREATE_STAGES.map((s) => (
              <option key={s.key} value={s.key}>
                {s.label}
              </option>
            ))}
          </select>
        </label>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="text-sm font-medium text-ink">预估金额</span>
            <input
              className="input-field mt-1 w-full"
              type="number"
              value={form.expected_value}
              onChange={(e) => set({ expected_value: e.target.value })}
              placeholder="¥"
            />
          </label>
          <label className="block">
            <span className="text-sm font-medium text-ink">赢单概率 (%)</span>
            <input
              className="input-field mt-1 w-full"
              type="number"
              min="0"
              max="100"
              value={form.probability}
              onChange={(e) => set({ probability: e.target.value })}
              placeholder="0-100"
            />
          </label>
        </div>
        <label className="block">
          <span className="text-sm font-medium text-ink">描述</span>
          <textarea
            className="input-field mt-1 w-full"
            rows={2}
            value={form.description}
            onChange={(e) => set({ description: e.target.value })}
          />
        </label>
      </form>
    </ResourceDialog>
  );
}
