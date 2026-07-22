"use client";

/** 商机详情页：ID 取自 URL query `?id=xxx`。 */

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Content from "./detail-content";

export default function OpportunityDetailPage() {
  return (
    <Suspense fallback={null}>
      <OpportunityDetailPageContent />
    </Suspense>
  );
}

function OpportunityDetailPageContent() {
  const searchParams = useSearchParams();
  const id = searchParams.get("id") ?? "_";
  return <Content id={id} />;
}
