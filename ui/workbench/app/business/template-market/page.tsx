"use client";

import { ServiceTemplateMarketPageView, useServiceTemplateMarketPage } from "@/features/service-template-market";

export default function TemplateMarketPage() {
  const vm = useServiceTemplateMarketPage();
  return <ServiceTemplateMarketPageView vm={vm} />;
}
