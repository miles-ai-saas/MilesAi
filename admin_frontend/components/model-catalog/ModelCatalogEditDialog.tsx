"use client";

import { useEffect, useState, type ReactNode } from "react";
import type { AdminModelCatalog } from "@/lib/api";

const VENDORS = [
  { value: "deepseek", label: "深度求索" },
  { value: "doubao", label: "豆包" },
  { value: "qwen", label: "通义千问" },
];

const MODEL_TYPES = [
  { value: "llm", label: "大语言模型" },
  { value: "reasoning", label: "推理模型" },
  { value: "vision", label: "图像理解" },
];

const DEFAULT_API_BASE: Record<string, string> = {
  deepseek: "https://api.deepseek.com/v1",
  doubao: "https://ark.cn-beijing.volces.com/api/v3",
  qwen: "https://dashscope.aliyuncs.com/compatible-mode/v1",
};

export type ModelCatalogFormValues = {
  name: string;
  vendor: string;
  model_name: string;
  model_code: string;
  model_type: string;
  description: string;
  context_window: string;
  api_base: string;
  api_key: string;
  clear_api_key: boolean;
  badge: string;
  sort_order: number;
  is_featured: boolean;
  is_active: boolean;
};

type Props = {
  open: boolean;
  title: string;
  initial?: AdminModelCatalog | null;
  isCreate?: boolean;
  onClose: () => void;
  onSave: (values: ModelCatalogFormValues) => Promise<void>;
};

function emptyForm(): ModelCatalogFormValues {
  return {
    name: "",
    vendor: "deepseek",
    model_name: "",
    model_code: "",
    model_type: "llm",
    description: "",
    context_window: "",
    api_base: DEFAULT_API_BASE.deepseek,
    api_key: "",
    clear_api_key: false,
    badge: "",
    sort_order: 0,
    is_featured: false,
    is_active: true,
  };
}

function fromRow(m: AdminModelCatalog): ModelCatalogFormValues {
  return {
    name: m.name,
    vendor: m.vendor,
    model_name: m.model_name,
    model_code: m.model_code ?? "",
    model_type: m.model_type,
    description: m.description ?? "",
    context_window: m.context_window ?? "",
    api_base: m.api_base ?? DEFAULT_API_BASE[m.vendor] ?? "",
    api_key: "",
    clear_api_key: false,
    badge: m.badge ?? "",
    sort_order: m.sort_order,
    is_featured: m.is_featured,
    is_active: m.is_active,
  };
}

export function ModelCatalogEditDialog({
  open,
  title,
  initial,
  isCreate,
  onClose,
  onSave,
}: Props) {
  const [form, setForm] = useState<ModelCatalogFormValues>(emptyForm);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setForm(initial ? fromRow(initial) : emptyForm());
  }, [open, initial]);

  if (!open) return null;

  const set = (patch: Partial<ModelCatalogFormValues>) =>
    setForm((f) => ({ ...f, ...patch }));

  const onVendorChange = (vendor: string) => {
    setForm((f) => ({
      ...f,
      vendor,
      api_base: f.api_base || DEFAULT_API_BASE[vendor] || "",
    }));
  };

  const submit = async () => {
    setSaving(true);
    try {
      await onSave(form);
      onClose();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div
        className="card flex max-h-[90vh] w-full max-w-lg flex-col"
        role="dialog"
        aria-modal="true"
      >
        <header className="flex items-center justify-between border-b border-line px-5 py-4">
          <h2 className="text-lg font-semibold text-ink">{title}</h2>
          <button type="button" className="btn-ghost px-2 py-1" onClick={onClose}>
            关闭
          </button>
        </header>
        <div className="flex-1 space-y-3 overflow-y-auto px-5 py-4">
          <Field label="展示名称">
            <input
              className="input-field"
              value={form.name}
              onChange={(e) => set({ name: e.target.value })}
            />
          </Field>
          <Field label="服务商">
            <select
              className="input-field"
              value={form.vendor}
              onChange={(e) => onVendorChange(e.target.value)}
              disabled={!isCreate}
            >
              {VENDORS.map((v) => (
                <option key={v.value} value={v.value}>
                  {v.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="模型编码 model_code" hint={isCreate ? "全局唯一" : "已发布后慎改"}>
            <input
              className="input-field font-mono text-xs"
              value={form.model_code}
              onChange={(e) => set({ model_code: e.target.value })}
              disabled={!isCreate}
            />
          </Field>
          <Field label="请求参数 model_name">
            <input
              className="input-field font-mono text-xs"
              value={form.model_name}
              onChange={(e) => set({ model_name: e.target.value })}
            />
          </Field>
          <Field label="类型">
            <select
              className="input-field"
              value={form.model_type}
              onChange={(e) => set({ model_type: e.target.value })}
            >
              {MODEL_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="描述">
            <textarea
              className="input-field min-h-[72px]"
              value={form.description}
              onChange={(e) => set({ description: e.target.value })}
            />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="上下文">
              <input
                className="input-field"
                placeholder="如 128K"
                value={form.context_window}
                onChange={(e) => set({ context_window: e.target.value })}
              />
            </Field>
            <Field label="角标 badge">
              <input
                className="input-field"
                placeholder="如 latest"
                value={form.badge}
                onChange={(e) => set({ badge: e.target.value })}
              />
            </Field>
          </div>
          <Field label="排序 sort_order">
            <input
              type="number"
              className="input-field"
              value={form.sort_order}
              onChange={(e) => set({ sort_order: Number(e.target.value) || 0 })}
            />
          </Field>
          <div className="flex flex-wrap gap-4 text-sm">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={form.is_featured}
                onChange={(e) => set({ is_featured: e.target.checked })}
              />
              推荐展示
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(e) => set({ is_active: e.target.checked })}
              />
              启用
            </label>
          </div>

          <div className="rounded-lg border border-line bg-surface-muted/80 p-4">
            <p className="mb-3 text-sm font-medium text-ink">平台接入（租户默认使用）</p>
            <Field label="API Base">
              <input
                className="input-field font-mono text-xs"
                value={form.api_base}
                onChange={(e) => set({ api_base: e.target.value })}
              />
            </Field>
            <Field
              label="平台 API Key"
              hint={
                initial?.has_api_key
                  ? "已配置平台密钥；留空不修改，填写则覆盖"
                  : "未配置；填写后租户可不配 BYOK 直接使用"
              }
            >
              <input
                type="password"
                className="input-field"
                placeholder="sk-..."
                value={form.api_key}
                onChange={(e) => set({ api_key: e.target.value, clear_api_key: false })}
                autoComplete="new-password"
              />
            </Field>
            {initial?.has_api_key && !isCreate && (
              <label className="mt-2 flex items-center gap-2 text-sm text-ink-muted">
                <input
                  type="checkbox"
                  checked={form.clear_api_key}
                  onChange={(e) =>
                    set({ clear_api_key: e.target.checked, api_key: e.target.checked ? "" : form.api_key })
                  }
                />
                清除平台 Key（清除后租户须自行配置 BYOK）
              </label>
            )}
          </div>
        </div>
        <footer className="flex justify-end gap-2 border-t border-line px-5 py-4">
          <button type="button" className="btn-ghost" onClick={onClose} disabled={saving}>
            取消
          </button>
          <button type="button" className="btn-primary" onClick={submit} disabled={saving}>
            {saving ? "保存中…" : "保存"}
          </button>
        </footer>
      </div>
    </div>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-ink-muted">{label}</span>
      {children}
      {hint ? <span className="mt-1 block text-xs text-ink-muted">{hint}</span> : null}
    </label>
  );
}
