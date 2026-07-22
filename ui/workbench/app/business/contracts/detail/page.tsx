"use client";

/** 合同详情页：ID 取自 URL query `?id=xxx`。 */

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Content from "./detail-content";

export default function ContractDetailPage() {
  return (
    <Suspense fallback={null}>
      <ContractDetailPageContent />
    </Suspense>
  );
}

function ContractDetailPageContent() {
  const searchParams = useSearchParams();
  const id = searchParams.get("id") ?? "_";
  return <Content id={id} />;
}
