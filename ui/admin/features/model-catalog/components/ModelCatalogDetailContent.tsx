"use client";

import { ModelCatalogDetailPageView } from "@/features/model-catalog/components/ModelCatalogDetailPageView";
import { useModelCatalogDetailPage } from "@/features/model-catalog/hooks/use-model-catalog-detail-page";

export default function ModelCatalogDetailPage({ id }: { id: string }) {
  const vm = useModelCatalogDetailPage(id);
  return <ModelCatalogDetailPageView vm={vm} />;
}
