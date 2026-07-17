"use client";

import { Suspense } from "react";
import { FlowsPageView, useFlowsPage } from "@/features/flows";

export default function FlowsPage() {
  return (
    <Suspense fallback={null}>
      <FlowsPageContent />
    </Suspense>
  );
}

function FlowsPageContent() {
  const vm = useFlowsPage();
  return <FlowsPageView vm={vm} />;
}
