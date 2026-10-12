"use client";

/** Agent 评测工作台（数据集 / 运行 / 详情）。 */

import { Suspense } from "react";
import { EvalPageView, useEvalPage } from "@/features/eval";

function EvalPageInner() {
  const vm = useEvalPage();
  return <EvalPageView vm={vm} />;
}

export default function EvalPage() {
  return (
    <Suspense fallback={<p className="p-8 text-sm text-ink-muted animate-pulse">加载中…</p>}>
      <EvalPageInner />
    </Suspense>
  );
}
