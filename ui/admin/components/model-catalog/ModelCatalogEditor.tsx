"use client";

import type { AdminModelCatalog } from "@/lib/api";
import {
  DEFAULT_API_BASE,
  MODEL_TYPES,
  type ModelCatalogFormValues,
  VENDORS,
} from "./form-utils";

type Props = {
  form: ModelCatalogFormValues;
  onChange: (patch: Partial<ModelCatalogFormValues>) => void;
  isCreate: boolean;
  model?: AdminModelCatalog | null;
};

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-ink-muted">{label}</span>
      {children}
      {hint ? <span className="mt-1 block text-xs text-ink-faint">{hint}</span> : null}
    </label>
  );
}

function Section({ title, description, children }: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="card p-5">
      <h2 className="text-sm font-semibold text-ink">{title}</h2>
      {description && <p className="mt-1 text-xs cell-muted">{description}</p>}
      <div className="mt-4 space-y-3">{children}</div>
    </section>
  );
}

export function ModelCatalogEditor({ form, onChange, isCreate, model }: Props) {
  const set = onChange;

  const onVendorChange = (vendor: string) => {
    onChange({
      vendor,
      api_base: form.api_base || DEFAULT_API_BASE[vendor] || "",
    });
  };

  const onModelCodeChange = (model_code: string) => {
    const patch: Partial<ModelCatalogFormValues> = { model_code };
    if (isCreate && (!form.model_name || form.model_name === form.model_code)) {
      patch.model_name = model_code;
    }
    onChange(patch);
  };

  return (
    <div className="space-y-4">
      <Section title="展示信息" description="租户在模型目录中看到的名称与说明。">
        <Field label="展示名称">
          <input
            className="input-field"
            value={form.name}
            onChange={(e) => set({ name: e.target.value })}
            placeholder="如 DeepSeek V3"
          />
        </Field>
        <Field label="能力类型">
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
            className="input-field min-h-[88px] resize-y"
            value={form.description}
            onChange={(e) => set({ description: e.target.value })}
            placeholder="面向租户的能力说明"
          />
        </Field>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="上下文窗口" hint="如 128K、32K">
            <input
              className="input-field"
              value={form.context_window}
              onChange={(e) => set({ context_window: e.target.value })}
            />
          </Field>
          <Field label="角标" hint="如 latest，展示在卡片右上角">
            <input
              className="input-field"
              value={form.badge}
              onChange={(e) => set({ badge: e.target.value })}
            />
          </Field>
        </div>
        <Field label="排序权重" hint="数值越小越靠前">
          <input
            type="number"
            className="input-field max-w-[10rem]"
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
            启用（下架模型通常关闭）
          </label>
        </div>
      </Section>

      <Section
        title="调用标识"
        description="创建后 model_code 不可修改；model_name 为实际 API 请求参数。"
      >
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
        <Field
          label="模型编码"
          hint={isCreate ? "全局唯一，如 deepseek-chat" : "已创建，不可修改"}
        >
          <input
            className="input-field font-mono text-xs"
            value={form.model_code}
            onChange={(e) => onModelCodeChange(e.target.value)}
            disabled={!isCreate}
          />
        </Field>
        <Field label="API 模型名" hint="请求体中的 model 字段值">
          <input
            className="input-field font-mono text-xs"
            value={form.model_name}
            onChange={(e) => set({ model_name: e.target.value })}
          />
        </Field>
      </Section>

      <Section
        title="平台接入"
        description="配置后租户可不填 BYOK 直接使用；密钥仅保存在服务端。"
      >
        <Field label="API Base">
          <div className="flex gap-2">
            <input
              className="input-field min-w-0 flex-1 font-mono text-xs"
              value={form.api_base}
              onChange={(e) => set({ api_base: e.target.value })}
            />
            <button
              type="button"
              className="btn-ghost shrink-0 px-3 text-xs"
              onClick={() =>
                set({ api_base: DEFAULT_API_BASE[form.vendor] ?? "" })
              }
            >
              默认
            </button>
          </div>
        </Field>
        <Field
          label="平台 API Key"
          hint={
            model?.has_api_key
              ? "已配置；留空不修改，填写则覆盖"
              : "未配置；填写后租户可直接调用"
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
        {model?.has_api_key && !isCreate && (
          <label className="flex items-center gap-2 text-sm cell-muted">
            <input
              type="checkbox"
              checked={form.clear_api_key}
              onChange={(e) =>
                set({
                  clear_api_key: e.target.checked,
                  api_key: e.target.checked ? "" : form.api_key,
                })
              }
            />
            清除平台 Key（清除后租户须自行配置 BYOK）
          </label>
        )}
      </Section>
    </div>
  );
}
