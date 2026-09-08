"use client";

export default function ModelCatalogPage() {
  const vm = useModelCatalogPage();
  return <ModelCatalogPageView vm={vm} />;
}
import { ModelCatalogPageView, useModelCatalogPage } from "@/features/model-catalog";
