"use client";

/** 模型目录（链路 §3）：列表 + `GET /models/meta` → model-catalog-ui。 */

import { ModelCatalogGrid } from "@/components/model/ModelCatalogGrid";
import { ModelFilterPanel } from "@/components/model/ModelFilterPanel";
import { ModelsPageOverlays } from "@/components/model/ModelsPageOverlays";
import { PageHeader } from "@/components/layout/PageHeader";
import { useModelsPage } from "@/hooks/use-models-page";
import { MODELS_PAGE_DESC } from "@/lib/model-page-shared";

export default function ModelsPage() {
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
      <ModelsPageOverlays vm={vm} />
    </div>
  );
}
