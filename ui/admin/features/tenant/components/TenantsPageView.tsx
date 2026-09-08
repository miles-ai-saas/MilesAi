"use client";

import { PageHeader } from "@/components/layout/PageHeader";
import { TenantsCreateSection, TenantsStatusFilterSection, TenantsTableSection } from "@/features/tenant/components/TenantsSections";
import type { TenantsPageVm } from "@/features/tenant/hooks/use-tenants-page";
import { TENANTS_PAGE_DESCRIPTION } from "@/features/tenant/lib/tenants-page-shared";

export function TenantsPageView({ vm }: { vm: TenantsPageVm }) {
  return (
    <div>
      <PageHeader title="租户管理" description={TENANTS_PAGE_DESCRIPTION} />
      <TenantsStatusFilterSection vm={vm} />
      <TenantsCreateSection vm={vm} />
      <TenantsTableSection vm={vm} />
    </div>
  );
}
