"use client";

import { TenantDetailPageView } from "@/components/tenant/TenantDetailPageView";
import { useTenantDetailPage } from "@/hooks/use-tenant-detail-page";

export default function TenantDetailPage() {
  const vm = useTenantDetailPage();
  return <TenantDetailPageView vm={vm} />;
}
