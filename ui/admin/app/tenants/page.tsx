"use client";

export default function TenantsPage() {
  const vm = useTenantsPage();
  return <TenantsPageView vm={vm} />;
}
import { TenantsPageView, useTenantsPage } from "@/features/tenant";
