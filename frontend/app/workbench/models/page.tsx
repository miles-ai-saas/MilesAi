"use client";

/** 模型目录（链路 §3）：列表 + `GET /models/meta` → model-catalog-ui。 */

import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth-store";
import { useConfirmAction } from "@/hooks/use-confirm-action";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import { PageHeader } from "@/components/layout/PageHeader";
import {
  credentialHint,
  modelTypeLabel,
  SOURCE_LABELS,
  vendorLabel,
} from "@/lib/model-catalog-ui";
import type { ModelCatalogMeta, ModelConfig } from "@/lib/types";

type SourceFilter = "" | "builtin" | "custom";

const VENDOR_ORDER = ["deepseek", "doubao", "qwen"];

export default function ModelsPage() {
  const { ready } = useRequireAuth();
  const [meta, setMeta] = useState<ModelCatalogMeta | null>(null);
  const [items, setItems] = useState<ModelConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [vendor, setVendor] = useState("");
  const [modelType, setModelType] = useState("");
  const [source, setSource] = useState<SourceFilter>("");

  const [dialogOpen, setDialogOpen] = useState(false);
  const [credDialogOpen, setCredDialogOpen] = useState(false);
  const [editing, setEditing] = useState<ModelConfig | null>(null);
  const [credTarget, setCredTarget] = useState<ModelConfig | null>(null);

  const [name, setName] = useState("");
  const [vendorField, setVendorField] = useState("deepseek");
  const [modelName, setModelName] = useState("");
  const [modelCode, setModelCode] = useState("");
  const [modelTypeField, setModelTypeField] = useState("llm");
  const [description, setDescription] = useState("");
  const [apiBase, setApiBase] = useState("");
  const [apiKey, setApiKey] = useState("");

  const { requestConfirm, confirmDialog } = useConfirmAction();

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      // 枚举字典：GET /models/meta → model-catalog-ui（见 lib/enum-meta.ts）
      const [m, list] = await Promise.all([
        api.getModelCatalogMeta(),
        api.listModelConfigs({
          vendor: vendor || undefined,
          model_type: modelType || undefined,
          source: source || undefined,
          q: search.trim() || undefined,
        }),
      ]);
      setMeta(m);
      setItems(list);
    } finally {
      setLoading(false);
    }
  }, [vendor, modelType, source, search]);

  useEffect(() => {
    if (!ready) return;
    reload();
  }, [ready, reload]);

  const vendors = useMemo(() => {
    const fromMeta = meta?.vendors ?? [];
    return [...fromMeta].sort(
      (a, b) => VENDOR_ORDER.indexOf(a.value) - VENDOR_ORDER.indexOf(b.value),
    );
  }, [meta]);

  const openCreate = () => {
    setEditing(null);
    setName("");
    setVendorField("deepseek");
    setModelName("");
    setModelCode("");
    setModelTypeField("llm");
    setDescription("");
    setApiBase("");
    setApiKey("");
    setDialogOpen(true);
  };

  const openEdit = (m: ModelConfig) => {
    if (m.source === "builtin") return;
    setEditing(m);
    setName(m.name);
    setVendorField(m.vendor);
    setModelName(m.model_name);
    setModelCode(m.model_code ?? "");
    setModelTypeField(m.model_type);
    setDescription(m.description ?? "");
    setApiBase(m.api_base ?? "");
    setApiKey("");
    setDialogOpen(true);
  };

  const openCred = (m: ModelConfig) => {
    setCredTarget(m);
    setApiBase(m.api_base ?? "");
    setApiKey("");
    setCredDialogOpen(true);
  };

  const onSave = async () => {
    if (!name.trim() || !modelName.trim()) return;
    const payload = {
      name: name.trim(),
      vendor: vendorField,
      model_name: modelName.trim(),
      model_code: modelCode.trim() || undefined,
      model_type: modelTypeField,
      description: description.trim() || undefined,
      api_base: apiBase || undefined,
      api_key: apiKey || undefined,
    };
    if (editing) {
      await api.updateModelConfig(editing.id, payload);
    } else {
      await api.createModelConfig(payload);
    }
    setDialogOpen(false);
    await reload();
  };

  const onSaveCred = async () => {
    if (!credTarget || !apiKey.trim()) return;
    await api.upsertBuiltinModelCredentials(credTarget.id, {
      api_key: apiKey.trim(),
      api_base: apiBase || undefined,
    });
    setCredDialogOpen(false);
    await reload();
  };

  const onDelete = (m: ModelConfig) => {
    if (m.source === "builtin") return;
    requestConfirm({
      title: "删除自定义模型",
      message: (
        <>
          确定删除自定义模型 <span className="font-medium">{m.name}</span>？
        </>
      ),
      destructive: true,
      confirmLabel: "确认删除",
      onConfirm: async () => {
        await api.deleteModelConfig(m.id);
        await reload();
      },
    });
  };

  return (
    <div className="resource-page-shell">
      <PageHeader
        title="模型供应商"
        description="使用运营发布的内置模型，或添加自定义 OpenAI 兼容接入。"
        action={
          <button type="button" className="btn-primary" onClick={openCreate}>
            + 自定义模型
          </button>
        }
      />

      <section className="mb-6 rounded-xl border border-border bg-surface p-4">
        <h2 className="mb-3 text-sm font-semibold text-ink">模型分类</h2>
        <div className="mb-3">
          <p className="mb-2 text-xs text-ink-muted">服务商</p>
          <div className="flex flex-wrap gap-2">
            <FilterChip active={!vendor} onClick={() => setVendor("")}>
              全部
            </FilterChip>
            {vendors.map((v) => (
              <FilterChip key={v.value} active={vendor === v.value} onClick={() => setVendor(v.value)}>
                {v.label}
              </FilterChip>
            ))}
          </div>
        </div>
        <div className="mb-3">
          <p className="mb-2 text-xs text-ink-muted">类型</p>
          <div className="flex flex-wrap gap-2">
            <FilterChip active={!modelType} onClick={() => setModelType("")}>
              全部
            </FilterChip>
            {(meta?.model_types ?? []).map((t) => (
              <FilterChip
                key={t.value}
                active={modelType === t.value}
                onClick={() => setModelType(t.value)}
              >
                {t.label}
              </FilterChip>
            ))}
          </div>
        </div>
        <div>
          <p className="mb-2 text-xs text-ink-muted">来源</p>
          <div className="flex flex-wrap gap-2">
            <FilterChip active={!source} onClick={() => setSource("")}>
              全部
            </FilterChip>
            <FilterChip active={source === "builtin"} onClick={() => setSource("builtin")}>
              内置模型
            </FilterChip>
            <FilterChip active={source === "custom"} onClick={() => setSource("custom")}>
              自定义模型
            </FilterChip>
          </div>
        </div>
        <div className="mt-4">
          <input
            className="input-field w-full max-w-md"
            placeholder="搜索模型名称或编码"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </section>

      <h2 className="mb-3 text-sm font-semibold text-ink">模型列表</h2>
      {loading ? (
        <p className="text-sm text-ink-muted">加载中…</p>
      ) : items.length === 0 ? (
        <p className="text-sm text-ink-muted">暂无匹配的模型。</p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {items.map((m) => (
            <article key={m.id} className="resource-card relative !min-h-0 flex-col !items-stretch !p-4">
              {m.badge === "latest" && (
                <span className="absolute right-3 top-3 rounded bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
                  最新
                </span>
              )}
              <div className="mb-2 flex items-center gap-2">
                <span className="rounded bg-surface-muted px-2 py-0.5 text-xs font-medium text-ink">
                  {vendorLabel(m.vendor, meta)}
                </span>
                <span className="text-xs text-ink-muted">{m.model_code ?? m.model_name}</span>
              </div>
              <h3 className="pr-12 text-base font-semibold text-ink">{m.name}</h3>
              <p className="mt-2 line-clamp-3 text-xs leading-relaxed text-ink-muted">
                {m.description ?? "暂无描述"}
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                <span className="rounded border border-border px-2 py-0.5 text-xs text-ink-muted">
                  {modelTypeLabel(m.model_type, meta)}
                </span>
                <span className="rounded border border-brand/20 bg-brand-light/30 px-2 py-0.5 text-xs text-brand">
                  {SOURCE_LABELS[m.source]}
                </span>
                {m.credential_status === "missing" && (
                  <span className="rounded border border-amber-200 bg-amber-50 px-2 py-0.5 text-xs text-amber-800">
                    待配置 Key
                  </span>
                )}
              </div>
              <p className="mt-2 text-xs text-ink-muted">{credentialHint(m)}</p>
              <div className="mt-4 flex flex-wrap gap-2 border-t border-border pt-3">
                {m.source === "builtin" ? (
                  <button type="button" className="btn-ghost text-xs" onClick={() => openCred(m)}>
                    配置 API Key
                  </button>
                ) : (
                  <>
                    <button type="button" className="btn-ghost text-xs" onClick={() => openEdit(m)}>
                      编辑
                    </button>
                    <button
                      type="button"
                      className="btn-ghost text-xs text-red-600"
                      onClick={() => onDelete(m)}
                    >
                      删除
                    </button>
                  </>
                )}
              </div>
            </article>
          ))}
        </div>
      )}

      <ResourceDialog
        open={dialogOpen}
        title={editing ? "编辑自定义模型" : "添加自定义模型"}
        size="lg"
        onClose={() => setDialogOpen(false)}
        footer={
          <>
            <button type="button" className="btn-ghost" onClick={() => setDialogOpen(false)}>
              取消
            </button>
            <button type="button" className="btn-primary" onClick={onSave}>
              保存
            </button>
          </>
        }
      >
        <input
          className="input-field w-full"
          placeholder="展示名称"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <select
          className="input-field w-full"
          value={vendorField}
          onChange={(e) => setVendorField(e.target.value)}
        >
          {vendors.map((v) => (
            <option key={v.value} value={v.value}>
              {v.label}
            </option>
          ))}
          <option value="other">其它</option>
        </select>
        <input
          className="input-field w-full"
          placeholder="模型编码（可选）"
          value={modelCode}
          onChange={(e) => setModelCode(e.target.value)}
        />
        <input
          className="input-field w-full"
          placeholder="请求体 model 参数"
          value={modelName}
          onChange={(e) => setModelName(e.target.value)}
        />
        <select
          className="input-field w-full"
          value={modelTypeField}
          onChange={(e) => setModelTypeField(e.target.value)}
        >
          {(meta?.model_types ?? []).map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </select>
        <textarea
          className="input-field w-full min-h-[72px]"
          placeholder="描述（可选）"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
        <input
          className="input-field w-full"
          placeholder="API Base（可选）"
          value={apiBase}
          onChange={(e) => setApiBase(e.target.value)}
        />
        <input
          className="input-field w-full"
          placeholder="API Key"
          type="password"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
        />
      </ResourceDialog>

      <ResourceDialog
        open={credDialogOpen}
        title={credTarget ? `配置密钥 · ${credTarget.name}` : "配置密钥"}
        onClose={() => setCredDialogOpen(false)}
        footer={
          <>
            <button type="button" className="btn-ghost" onClick={() => setCredDialogOpen(false)}>
              取消
            </button>
            <button type="button" className="btn-primary" onClick={onSaveCred}>
              保存
            </button>
          </>
        }
      >
        <p className="text-xs text-ink-muted">
          内置模型默认使用平台密钥；此处配置租户自有 Key（BYOK），优先于平台密钥。
        </p>
        <input
          className="input-field w-full"
          placeholder="API Base（可选，留空用内置默认）"
          value={apiBase}
          onChange={(e) => setApiBase(e.target.value)}
        />
        <input
          className="input-field w-full"
          placeholder="API Key（必填）"
          type="password"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
        />
      </ResourceDialog>
      {confirmDialog}
    </div>
  );
}

function FilterChip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        active
          ? "rounded-full border border-brand bg-brand-light/50 px-3 py-1 text-xs font-medium text-brand"
          : "rounded-full border border-border bg-surface px-3 py-1 text-xs text-ink-muted hover:border-brand/30"
      }
    >
      {children}
    </button>
  );
}
