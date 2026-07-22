"use client";

/** 流程画布编辑页：ID 取自 URL query `?id=xxx`。 */

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Content from "./detail-content";

export default function FlowEditPage() {
  return (
    <Suspense fallback={null}>
      <FlowEditPageContent />
    </Suspense>
  );
}

function FlowEditPageContent() {
  const searchParams = useSearchParams();
  const id = searchParams.get("id") ?? "_";
  return <Content id={id} />;
}
