"use client";

import { Suspense } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { ModelCatalogGrid, ModelDetailDialog, ModelFilterPanel, ModelsPageOverlays, useModelsPage } from "@/features/models";

const MODELS_PAGE_DESC = "内置模型由平台统一提供密钥，可直接选用；自定义 OpenAI 兼容接入需自行配置 API Key。";

function ModelsPageContent() {
  const vm = useModelsPage();

  return (
    <div className="resource-page-shell">
      <PageHeader
        title="模型供应商"
        description={MODELS_PAGE_DESC}
        action={
          <button type="button" className="btn-primary" onClick={vm.openCreate}>
            + 自定义模型
          </button>
        }
      />
      <ModelFilterPanel vm={vm} />
      <h2 className="mb-3 text-sm font-semibold text-ink">模型列表</h2>
      <ModelCatalogGrid vm={vm} />
      <ModelDetailDialog
        open={!!vm.detailModelId}
        modelId={vm.detailModelId}
        meta={vm.meta}
        reloadKey={vm.detailReloadKey}
        onClose={vm.closeDetail}
        onEdit={vm.openEdit}
        onDelete={vm.onDelete}
        onCred={vm.openCred}
        onClearBuiltinByok={vm.onClearBuiltinByok}
      />
      <ModelsPageOverlays vm={vm} />
    </div>
  );
}

export default function ModelsPage() {
  return (
    <Suspense fallback={<div className="py-12 text-center text-sm text-ink-muted">加载模型列表…</div>}>
      <ModelsPageContent />
    </Suspense>
  );
}
