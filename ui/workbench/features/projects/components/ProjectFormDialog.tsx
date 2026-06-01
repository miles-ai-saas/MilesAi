"use client";

import { useEffect, useState } from "react";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import {
  EMPTY_PROJECT_FORM,
  type ProjectFormValues,
  type WorkPackageDraft,
} from "@/features/projects/lib/project-form-options";
import { SERVICE_LINES } from "@/features/projects/lib/biz-labels";
import type { BizClient } from "@/lib/types";

type Props = {
  open: boolean;
  form: ProjectFormValues;
  clients: BizClient[];
  clientsLoading: boolean;
  saving: boolean;
  createError?: string;
  onClose: () => void;
  onChange: (form: ProjectFormValues) => void;
  onSave: () => void;
};

export function ProjectFormDialog({
  open,
  form,
  clients,
  clientsLoading,
  saving,
  createError,
  onClose,
  onChange,
  onSave,
}: Props) {
  const [step, setStep] = useState<1 | 2>(1);
  const set = (patch: Partial<ProjectFormValues>) => onChange({ ...form, ...patch });

  useEffect(() => {
    if (!open) setStep(1);
  }, [open]);

  const canNext = Boolean(form.client_id && form.name.trim());
  const addWorkPackage = () => set({ work_packages: [...form.work_packages, { service_line: "", name: "" }] });
  const removeWorkPackage = (index: number) => set({ work_packages: form.work_packages.filter((_, i) => i !== index) });
  const updateWorkPackage = (index: number, patch: Partial<WorkPackageDraft>) => {
    set({
      work_packages: form.work_packages.map((wp, i) => (i === index ? { ...wp, ...patch } : wp)),
    });
  };

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    if (!canNext || saving) return;
    onSave();
  };

  return (
    <ResourceDialog
      open={open}
      title="新建项目"
      description={step === 1 ? "第 1 步：填写项目基本信息" : "第 2 步：添加服务线工作包（可选）"}
      onClose={onClose}
      size="lg"
      footer={
        step === 1 ? (
          <>
            <button type="button" className="btn-ghost" onClick={onClose} disabled={saving}>
              取消
            </button>
            <button type="button" className="btn-primary" disabled={!canNext} onClick={() => setStep(2)}>
              下一步
            </button>
          </>
        ) : (
          <>
            <button type="button" className="btn-ghost" onClick={() => setStep(1)} disabled={saving}>
              上一步
            </button>
            <button
              type="submit"
              form="project-create-form"
              className="btn-primary"
              disabled={saving || !canNext}
            >
              {saving ? "保存中…" : "保存并进入项目"}
            </button>
          </>
        )
      }
    >
      {createError ? (
        <p className="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{createError}</p>
      ) : null}
      {step === 1 ? (
        <div className="space-y-4">
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
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-sm font-medium text-ink">
              项目名称 <span className="text-red-500">*</span>
            </span>
            <input
              className="input-field mt-1 w-full"
              value={form.name}
              onChange={(e) => set({ name: e.target.value })}
              placeholder="如：XX 展馆整体设计"
              required
              autoFocus={Boolean(form.client_id)}
            />
          </label>
          <label className="block">
            <span className="text-sm font-medium text-ink">项目编号</span>
            <input
              className="input-field mt-1 w-full"
              value={form.code}
              onChange={(e) => set({ code: e.target.value })}
              placeholder="可选"
            />
          </label>
          <label className="block">
            <span className="text-sm font-medium text-ink">描述</span>
            <textarea
              className="input-field mt-1 w-full"
              rows={2}
              value={form.description}
              onChange={(e) => set({ description: e.target.value })}
              placeholder="可选"
            />
          </label>
        </div>
      ) : (
        <form id="project-create-form" onSubmit={handleSave} className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-ink-muted">可按服务线预先创建工作包，也可稍后在项目详情中添加。</p>
            <button type="button" className="text-xs text-brand hover:underline" onClick={addWorkPackage}>
              + 添加工作包
            </button>
          </div>
          {form.work_packages.length === 0 ? (
            <p className="rounded-lg border border-dashed border-line py-8 text-center text-sm text-ink-faint">
              暂无工作包，可跳过直接保存
            </p>
          ) : (
            <div className="space-y-2">
              {form.work_packages.map((wp, index) => (
                <div key={index} className="flex flex-wrap items-center gap-2">
                  <select
                    className="input-field min-w-[8rem] flex-1 text-sm"
                    value={wp.service_line}
                    onChange={(e) => updateWorkPackage(index, { service_line: e.target.value })}
                  >
                    <option value="">— 服务线 —</option>
                    {SERVICE_LINES.map((line) => (
                      <option key={line.key} value={line.key}>{line.label}</option>
                    ))}
                  </select>
                  <input
                    className="input-field min-w-[8rem] flex-1 text-sm"
                    value={wp.name}
                    onChange={(e) => updateWorkPackage(index, { name: e.target.value })}
                    placeholder="工作包名称"
                  />
                  <button type="button" className="text-xs text-red-500 hover:underline" onClick={() => removeWorkPackage(index)}>
                    移除
                  </button>
                </div>
              ))}
            </div>
          )}
        </form>
      )}
    </ResourceDialog>
  );
}
