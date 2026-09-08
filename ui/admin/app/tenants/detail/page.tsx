"use client";

/** 租户详情页：ID 取自 URL query `?id=xxx`。 */

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Content from "@/features/tenant/components/TenantDetailContent";

export default function TenantDetailPage() {
  return (
    <Suspense fallback={null}>
      <TenantDetailPageContent />
    </Suspense>
  );
}

function TenantDetailPageContent() {
  const searchParams = useSearchParams();
  const id = searchParams.get("id") ?? "_";
  return <Content id={id} />;
}
