"use client";

import { TenantDetailPageView } from "@/features/tenant/components/TenantDetailPageView";
import { useTenantDetailPage } from "@/features/tenant/hooks/use-tenant-detail-page";

export default function TenantDetailPage({ id }: { id: string }) {
  const vm = useTenantDetailPage(id);
  return <TenantDetailPageView vm={vm} />;
}
