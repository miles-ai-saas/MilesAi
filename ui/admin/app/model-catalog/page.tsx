"use client";

import { ModelCatalogPageView } from "@/components/model-catalog/ModelCatalogPageView";
import { useModelCatalogPage } from "@/hooks/use-model-catalog-page";

export default function ModelCatalogPage() {
  const vm = useModelCatalogPage();
  return <ModelCatalogPageView vm={vm} />;
}
