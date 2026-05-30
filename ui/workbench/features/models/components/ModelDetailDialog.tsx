"use client";

import { useCallback, useEffect, useState } from "react";
import { ResourceDialog } from "@/components/resource/ResourceDialog";
import {
  isBuiltinByok,
  isBuiltinPlatformMissing,
  isBuiltinReady,
  isCustomMissingKey,
  modelCredentialHint,
  modelCredentialStatusLabel,
  modelSourceLabel,
  modelTypeLabel,
  modelVendorLabel,
} from "@/features/models/lib/model-labels";
import { api } from "@/lib/api";
import { getApiErrorMessage } from "@/lib/api-error";
import type { ModelCatalogMeta, ModelConfig } from "@/lib/types";

type Props = {
  open: boolean;
  modelId: string | null;
  meta: ModelCatalogMeta | null;
  reloadKey?: number;
  onClose: () => void;
  onEdit: (m: ModelConfig) => void;
  onDelete: (m: ModelConfig) => void;
  onCred: (m: ModelConfig) => void;
  onClearBuiltinByok: (m: ModelConfig) => void;
};

function DetailField({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="grid gap-1 border-b border-line-soft py-2.5 sm:grid-cols-3 sm:gap-3">
      <dt className="text-xs text-ink-muted">{label}</dt>
      <dd className={`break-all text-sm text-ink sm:col-span-2 ${mono ? "font-mono text-xs" : ""}`}>{value}</dd>
    </div>
  );
}

export function ModelDetailDialog({ open, modelId, meta, reloadKey = 0, onClose, onEdit, onDelete, onCred, onClearBuiltinByok }: Props) {
  const [model, setModel] = useState<ModelConfig | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    if (!modelId) return;
    setLoading(true);
    setError(null);
    try {
      setModel(await api.getModelConfig(modelId));
    } catch (e) {
      setError(getApiErrorMessage(e, "加载失败"));
      setModel(null);
    } finally {
      setLoading(false);
    }
  }, [modelId]);

  useEffect(() => {
    if (!open || !modelId) {
      setModel(null);
      setError(null);
      return;
    }
    void reload();
  }, [open, modelId, reloadKey, reload]);

  const extra = model?.extra ?? {};

  const footer = model ? (
    <div className="flex flex-wrap items-center justify-end gap-2">
      {model.source === "builtin" ? (
        isBuiltinByok(model) ? (
          <>
            <button type="button" className="btn-sm-outline" onClick={() => onCred(model)}>
              更新自有 Key
            </button>
            <button type="button" className="btn-sm-ghost" onClick={() => onClearBuiltinByok(model)}>
              恢复平台密钥
            </button>
          </>
        ) : (
          <button type="button" className="btn-sm-outline" onClick={() => onCred(model)}>
            使用自有 Key
          </button>
        )
      ) : (
        <>
          <button type="button" className="btn-sm-outline" onClick={() => onEdit(model)}>
            编辑
          </button>
          <button type="button" className="btn-sm-outline text-red-600" onClick={() => onDelete(model)}>
            删除
          </button>
        </>
      )}
      <button type="button" className="btn-ghost" onClick={onClose}>
        关闭
      </button>
    </div>
  ) : (
    <button type="button" className="btn-ghost" onClick={onClose}>
      关闭
    </button>
  );

  return (
    <ResourceDialog open={open} title={model?.name ?? "模型详情"} size="lg" onClose={onClose} footer={footer}>
      {loading ? <p className="text-sm text-ink-muted">加载中…</p> : null}
      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      {model && !loading ? (
        <div className="space-y-4">
          {model.description ? <p className="text-sm text-ink-muted">{model.description}</p> : null}
          <div className="flex flex-wrap gap-2">
            <span className="rounded border border-border px-2 py-0.5 text-xs text-ink-muted">{modelVendorLabel(model.vendor, meta)}</span>
            <span className="rounded border border-border px-2 py-0.5 text-xs text-ink-muted">{modelTypeLabel(model.model_type, meta)}</span>
            <span className="rounded border border-brand/20 bg-brand-light/30 px-2 py-0.5 text-xs text-brand">{modelSourceLabel(model.source)}</span>
            {isBuiltinReady(model) && <span className="rounded border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-xs text-emerald-800">可直接使用</span>}
            {isBuiltinByok(model) && <span className="rounded border border-sky-200 bg-sky-50 px-2 py-0.5 text-xs text-sky-800">自有 Key</span>}
            {isBuiltinPlatformMissing(model) && (
              <span className="rounded border border-amber-200 bg-amber-50 px-2 py-0.5 text-xs text-amber-800">平台未配置</span>
            )}
            {isCustomMissingKey(model) && <span className="rounded border border-amber-200 bg-amber-50 px-2 py-0.5 text-xs text-amber-800">待配置 Key</span>}
          </div>
          <p className="text-xs text-ink-muted">{modelCredentialHint(model)}</p>
          <dl>
            <DetailField label="模型 ID" value={model.id} mono />
            <DetailField label="供应商标识" value={model.provider} mono />
            <DetailField label="模型编码" value={model.model_code ?? "—"} mono />
            <DetailField label="请求参数 model" value={model.model_name} mono />
            <DetailField label="凭证状态" value={modelCredentialStatusLabel(model.credential_status)} />
            <DetailField label="API Key" value={model.has_api_key ? "已配置" : "未配置"} />
            <DetailField label="API Base" value={model.api_base ?? "—"} mono />
            <DetailField label="上下文窗口" value={model.context_window ?? "—"} />
            <DetailField label="启用状态" value={model.is_active ? "启用" : "禁用"} />
            {model.publish_status ? <DetailField label="发布状态" value={model.publish_status} /> : null}
            {extra.embedding_dimension != null ? <DetailField label="向量维度" value={String(extra.embedding_dimension)} /> : null}
            {extra.invoke_mode ? <DetailField label="调用模式" value={String(extra.invoke_mode)} mono /> : null}
            {extra.litellm_model ? <DetailField label="LiteLLM 模型" value={String(extra.litellm_model)} mono /> : null}
            <DetailField label="创建时间" value={new Date(model.created_at).toLocaleString("zh-CN")} />
          </dl>
        </div>
      ) : null}
    </ResourceDialog>
  );
}
