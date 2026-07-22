"use client";

/** 供应商详情页：ID 取自 URL query `?id=xxx`。 */

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Content from "./detail-content";

export default function SupplierDetailPage() {
  return (
    <Suspense fallback={null}>
      <SupplierDetailPageContent />
    </Suspense>
  );
}

function SupplierDetailPageContent() {
  const searchParams = useSearchParams();
  const id = searchParams.get("id") ?? "_";
  return <Content id={id} />;
}
