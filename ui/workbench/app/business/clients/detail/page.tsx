"use client";

/** 客户详情页：ID 取自 URL query `?id=xxx`。 */

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Content from "./detail-content";

export default function ClientDetailPage() {
  return (
    <Suspense fallback={null}>
      <ClientDetailPageContent />
    </Suspense>
  );
}

function ClientDetailPageContent() {
  const searchParams = useSearchParams();
  const id = searchParams.get("id") ?? "_";
  return <Content id={id} />;
}
