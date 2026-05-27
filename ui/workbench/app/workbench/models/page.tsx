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
  isBuiltinByok,
  isBuiltinPlatformMissing,
  isBuiltinReady,
  isCustomMissingKey,
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
  const [saveError, setSaveError] = useState("");

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
    setSaveError("");
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
    setSaveError("");
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
    if (!editing && !apiKey.trim()) {
      setSaveError("自定义模型必须填写 API Key");
      return;
    }
    setSaveError("");
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

  const onClearBuiltinByok = (m: ModelConfig) => {
    requestConfirm({
      title: "恢复使用平台密钥",
      message: (
        <>
          将清除 <span className="font-medium">{m.name}</span> 的租户自有 Key，恢复为平台托管密钥（若平台已配置）。
        </>
      ),
      confirmLabel: "确认清除",
      onConfirm: async () => {
        await api.deleteBuiltinModelCredentials(m.id);
        await reload();
      },
    });
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
        description="内置模型由平台统一提供密钥，可直接选用；自定义 OpenAI 兼容接入需自行配置 API Key。"
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
                {isBuiltinReady(m) && (
                  <span className="rounded border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-xs text-emerald-800">
                    可直接使用
                  </span>
                )}
                {isBuiltinByok(m) && (
                  <span className="rounded border border-sky-200 bg-sky-50 px-2 py-0.5 text-xs text-sky-800">
                    自有 Key
                  </span>
                )}
                {isBuiltinPlatformMissing(m) && (
                  <span className="rounded border border-amber-200 bg-amber-50 px-2 py-0.5 text-xs text-amber-800">
                    平台未配置
                  </span>
                )}
                {isCustomMissingKey(m) && (
                  <span className="rounded border border-amber-200 bg-amber-50 px-2 py-0.5 text-xs text-amber-800">
                    待配置 Key
                  </span>
                )}
              </div>
              <p className="mt-2 text-xs text-ink-muted">{credentialHint(m)}</p>
              <div className="mt-4 flex flex-wrap gap-2 border-t border-border pt-3">
                {m.source === "builtin" ? (
                  isBuiltinByok(m) ? (
                    <>
                      <button type="button" className="btn-ghost text-xs" onClick={() => openCred(m)}>
                        更新自有 Key
                      </button>
                      <button
                        type="button"
                        className="btn-ghost text-xs text-ink-muted"
                        onClick={() => onClearBuiltinByok(m)}
                      >
                        恢复平台密钥
                      </button>
                    </>
                  ) : (
                    <button type="button" className="btn-ghost text-xs" onClick={() => openCred(m)}>
                      使用自有 Key（可选）
                    </button>
                  )
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
        onClose={() => {
          setDialogOpen(false);
          setSaveError("");
        }}
        footer={
          <>
            <button
              type="button"
              className="btn-ghost"
              onClick={() => {
                setDialogOpen(false);
                setSaveError("");
              }}
            >
              取消
            </button>
            <button type="button" className="btn-primary" onClick={onSave}>
              保存
            </button>
          </>
        }
      >
        {saveError && (
          <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {saveError}
          </p>
        )}
        <p className="text-xs text-ink-muted">
          自定义模型由本租户自行维护接入参数；新建时必须填写 API Key，编辑时留空表示不修改密钥。
        </p>
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
          placeholder={editing ? "API Key（留空不修改）" : "API Key（必填）"}
          type="password"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
        />
      </ResourceDialog>

      <ResourceDialog
        open={credDialogOpen}
        title={credTarget ? `租户自有 Key · ${credTarget.name}` : "租户自有 Key"}
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
          内置模型默认使用平台统一密钥，无需租户配置。仅在合规或自付账单等场景下，可在此填写自有 Key（BYOK），将优先于平台密钥。
        </p>
        <input
          className="input-field w-full"
          placeholder="API Base（可选，留空用内置默认）"
          value={apiBase}
          onChange={(e) => setApiBase(e.target.value)}
        />
        <input
          className="input-field w-full"
          placeholder="租户 API Key（必填）"
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
