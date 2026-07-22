"use client";

import { ModelCatalogDetailPageView } from "@/components/model-catalog/ModelCatalogDetailPageView";
import { useModelCatalogDetailPage } from "@/hooks/use-model-catalog-detail-page";

export default function ModelCatalogDetailPage({ id }: { id: string }) {
  const vm = useModelCatalogDetailPage(id);
  return <ModelCatalogDetailPageView vm={vm} />;
}
