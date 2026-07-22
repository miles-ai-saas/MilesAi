"use client";

/** 旧详情页路由：重定向到列表并打开详情弹窗。ID 取自 `?id=xxx`。 */

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Content from "./detail-content";

export default function ModelDetailPage() {
  return (
    <Suspense fallback={null}>
      <ModelDetailPageContent />
    </Suspense>
  );
}

function ModelDetailPageContent() {
  const searchParams = useSearchParams();
  const id = searchParams.get("id") ?? "_";
  return <Content id={id} />;
}
