"use client";

/** 套餐详情页：ID 取自 URL query `?id=xxx`。 */

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Content from "./detail-content";

export default function BillingPlanDetailPage() {
  return (
    <Suspense fallback={null}>
      <BillingPlanDetailPageContent />
    </Suspense>
  );
}

function BillingPlanDetailPageContent() {
  const searchParams = useSearchParams();
  const id = searchParams.get("id") ?? "_";
  return <Content id={id} />;
}
