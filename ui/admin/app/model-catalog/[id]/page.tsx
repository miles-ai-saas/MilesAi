"use client";

import { ModelCatalogDetailPageView } from "@/components/model-catalog/ModelCatalogDetailPageView";
import { useModelCatalogDetailPage } from "@/hooks/use-model-catalog-detail-page";

export default function ModelCatalogDetailPage() {
  const vm = useModelCatalogDetailPage();
  return <ModelCatalogDetailPageView vm={vm} />;
}
