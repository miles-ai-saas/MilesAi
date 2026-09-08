"use client";

/** 模型详情页：ID 取自 URL query `?id=xxx`。 */

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Content from "@/features/model-catalog/components/ModelCatalogDetailContent";

export default function ModelCatalogDetailPage() {
  return (
    <Suspense fallback={null}>
      <ModelCatalogDetailPageContent />
    </Suspense>
  );
}

function ModelCatalogDetailPageContent() {
  const searchParams = useSearchParams();
  const id = searchParams.get("id") ?? "_";
  return <Content id={id} />;
}
