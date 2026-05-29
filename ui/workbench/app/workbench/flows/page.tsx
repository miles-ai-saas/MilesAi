"use client";

/** 标准列表页范例（链路 §3）：`useRequireAuth` → `usePagedList` → `ResourceListLayout` → `useFlowMeta`。 */

import { FlowsPageView } from "@/components/flow/FlowsPageView";
import { useFlowsPage } from "@/hooks/use-flows-page";

export default function FlowsPage() {
  const vm = useFlowsPage();
  return <FlowsPageView vm={vm} />;
}
