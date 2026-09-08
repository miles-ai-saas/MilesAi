/** 租户管理 feature 对外入口。 */

export { useTenantsPage, type TenantsPageVm } from "./hooks/use-tenants-page";
export { useTenantDetailPage, type TenantDetailPageVm } from "./hooks/use-tenant-detail-page";

export { TenantsPageView } from "./components/TenantsPageView";
export { TenantDetailPageView } from "./components/TenantDetailPageView";

export { default as TenantDetailContent } from "./components/TenantDetailContent";
