"use client";

import { ResourceDialog } from "@/components/resource/ResourceDialog";
import {
  CONTRACT_TYPE_OPTIONS,
  type ContractFormValues,
} from "@/features/contracts/lib/contract-form-options";
import type { BizClient, BizProject } from "@/lib/types";

type Props = {
  open: boolean;
  form: ContractFormValues;
  projects: BizProject[];
  clients: BizClient[];
  optionsLoading: boolean;
  saving: boolean;
  onClose: () => void;
  onChange: (form: ContractFormValues) => void;
  onSave: () => void;
};

export function ContractFormDialog({
  open,
  form,
  projects,
  clients,
  optionsLoading,
  saving,
  onClose,
  onChange,
  onSave,
}: Props) {
  const set = (patch: Partial<ContractFormValues>) => onChange({ ...form, ...patch });

  const handleProjectChange = (projectId: string) => {
    const project = projects.find((p) => p.id === projectId);
    onChange({
      ...form,
      project_id: projectId,
      client_id: project?.client_id ?? form.client_id,
    });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim() || !form.project_id || !form.client_id || saving) return;
    onSave();
  };

  return (
    <ResourceDialog
      open={open}
      title="新建合同"
      description="关联项目与客户，登记合同基本信息"
      onClose={onClose}
      size="lg"
      footer={
        <>
          <button type="button" className="btn-ghost" onClick={onClose} disabled={saving}>
            取消
          </button>
          <button
            type="submit"
            form="contract-create-form"
            className="btn-primary"
            disabled={saving || !form.name.trim() || !form.project_id || !form.client_id}
          >
            {saving ? "保存中…" : "保存"}
          </button>
        </>
      }
    >
      <form id="contract-create-form" onSubmit={handleSubmit} className="space-y-4">
        <label className="block">
          <span className="text-sm font-medium text-ink">
            所属项目 <span className="text-red-500">*</span>
          </span>
          <select
            className="input-field mt-1 w-full"
            value={form.project_id}
            onChange={(e) => handleProjectChange(e.target.value)}
            required
            disabled={optionsLoading}
          >
            <option value="">— 请选择 —</option>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="text-sm font-medium text-ink">
            客户 <span className="text-red-500">*</span>
          </span>
          <select
            className="input-field mt-1 w-full"
            value={form.client_id}
            onChange={(e) => set({ client_id: e.target.value })}
            required
            disabled={optionsLoading}
          >
            <option value="">— 请选择 —</option>
            {clients.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="text-sm font-medium text-ink">
            合同名称 <span className="text-red-500">*</span>
          </span>
          <input
            className="input-field mt-1 w-full"
            value={form.name}
            onChange={(e) => set({ name: e.target.value })}
            placeholder="如：XX 项目服务合同"
            required
          />
        </label>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="text-sm font-medium text-ink">合同编号</span>
            <input
              className="input-field mt-1 w-full"
              value={form.contract_no}
              onChange={(e) => set({ contract_no: e.target.value })}
              placeholder="如 HT-2024-001"
            />
          </label>
          <label className="block">
            <span className="text-sm font-medium text-ink">类型</span>
            <select className="input-field mt-1 w-full" value={form.type} onChange={(e) => set({ type: e.target.value })}>
              {CONTRACT_TYPE_OPTIONS.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </label>
        </div>
        <label className="block">
          <span className="text-sm font-medium text-ink">合同金额</span>
          <input
            className="input-field mt-1 w-full"
            type="number"
            value={form.total_amount}
            onChange={(e) => set({ total_amount: e.target.value })}
            placeholder="¥"
          />
        </label>
        <label className="block">
          <span className="text-sm font-medium text-ink">付款条款</span>
          <input
            className="input-field mt-1 w-full"
            value={form.payment_terms}
            onChange={(e) => set({ payment_terms: e.target.value })}
            placeholder="如：30% 预付 + 70% 验收后"
          />
        </label>
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
