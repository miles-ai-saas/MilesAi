"use client";

import { TenantsPageView } from "@/components/tenant/TenantsPageView";
import { useTenantsPage } from "@/hooks/use-tenants-page";

export default function TenantsPage() {
  const vm = useTenantsPage();
  return <TenantsPageView vm={vm} />;
}
