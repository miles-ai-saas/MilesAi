"use client";

import { Suspense } from "react";
import { ServiceTemplateMarketPageView, useServiceTemplateMarketPage } from "@/features/service-template-market";

export default function TemplateMarketPage() {
  return (
    <Suspense fallback={null}>
      <TemplateMarketPageContent />
    </Suspense>
  );
}

function TemplateMarketPageContent() {
  const vm = useServiceTemplateMarketPage();
  return <ServiceTemplateMarketPageView vm={vm} />;
}
