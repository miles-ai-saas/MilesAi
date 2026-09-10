"use client";

import { AdminDetailHeader } from "@/components/layout/AdminDetailHeader";
import { ModelCatalogEditor } from "@/features/model-catalog/components/ModelCatalogEditor";
import { ModelCatalogDetailAside } from "@/features/model-catalog/components/ModelCatalogDetailAside";
import { STATUS_LABEL, statusBadgeClass, TYPE_LABEL, VENDOR_LABEL } from "@/features/model-catalog/lib/form-utils";
import type { ModelCatalogDetailPageVm } from "@/features/model-catalog/hooks/use-model-catalog-detail-page";

export function ModelCatalogDetailPageView({ vm }: { vm: ModelCatalogDetailPageVm }) {
  const { model, form, msg, err, saving, patchForm, onSave } = vm;

  if (!model || !form) {
    return <p className="text-sm cell-muted">加载中…</p>;
  }

  const modelId = model.model_code ?? model.model_name;

  return (
    <div className="admin-page-stack">
      <AdminDetailHeader
        backHref="/model-catalog"
        backLabel="返回模型列表"
        title={model.name}
        badges={
          <>
            <span className={`status-badge ${statusBadgeClass(model.publish_status)}`}>{STATUS_LABEL[model.publish_status] ?? model.publish_status}</span>
            <span className={model.has_api_key ? "key-badge-ready" : "key-badge-missing"}>{model.has_api_key ? "Key 已配置" : "Key 未配置"}</span>
          </>
        }
        description={
          <>
            {VENDOR_LABEL[model.vendor] ?? model.vendor}
            <span className="mx-2 text-ink-faint">·</span>
            {TYPE_LABEL[model.model_type] ?? model.model_type}
            {modelId && (
              <>
                <span className="mx-2 text-ink-faint">·</span>
                <span className="font-mono text-xs">{modelId}</span>
              </>
            )}
          </>
        }
        action={
          <button type="button" className="btn-primary" disabled={saving} onClick={() => void onSave()}>
            {saving ? "保存中…" : "保存更改"}
          </button>
        }
      />

      {msg && <p className="text-sm text-emerald-600">{msg}</p>}
      {err && <p className="text-sm text-red-600">{err}</p>}

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <ModelCatalogEditor form={form} onChange={patchForm} isCreate={false} model={model} />
        </div>
        <ModelCatalogDetailAside vm={vm} />
      </div>
    </div>
  );
}
