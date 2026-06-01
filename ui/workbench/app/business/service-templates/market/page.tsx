"use client";

import { ServiceTemplateMarketPageView, useServiceTemplateMarketPage } from "@/features/service-template-market";

export default function ServiceTemplateMarketPage() {
  const vm = useServiceTemplateMarketPage();
  return <ServiceTemplateMarketPageView vm={vm} />;
}
