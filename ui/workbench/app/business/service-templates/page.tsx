"use client";

import { ServiceTemplatesPageView, useServiceTemplatesPage } from "@/features/service-templates";

export default function ServiceTemplatesPage() {
  const vm = useServiceTemplatesPage();
  return <ServiceTemplatesPageView vm={vm} />;
}
