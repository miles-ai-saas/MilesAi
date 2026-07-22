"use client";

import { TenantDetailPageView } from "@/components/tenant/TenantDetailPageView";
import { useTenantDetailPage } from "@/hooks/use-tenant-detail-page";

export default function TenantDetailPage({ id }: { id: string }) {
  const vm = useTenantDetailPage(id);
  return <TenantDetailPageView vm={vm} />;
}
