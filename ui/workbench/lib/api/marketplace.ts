import type {
  AppCategory,
  MarketplaceApp,
  MarketplaceAppDetail,
  AppRating,
  AppInstall,
  AppInstallResult,
} from "../types";
import type { ApiResponse } from "../types";
import { get, getPage, post, put, patch, http, unwrap, postWithTrace } from "./client";
import { appendTagIds } from "./query";
import { buildPageQuery, DEFAULT_PAGE_SIZE } from "../pagination";

export const marketplaceApi = {
  listMarketplaceCategories: () => get<AppCategory[]>("/marketplace/categories"),

  listMarketplaceApps: (
    page = 1,
    size = DEFAULT_PAGE_SIZE,
    category?: string,
    sort: "installs" | "rating" = "installs",
    tagIds?: string[],
  ) => {
    let q = `${buildPageQuery(page, size)}&sort=${sort}`;
    if (category) q += `&category=${encodeURIComponent(category)}`;
    return getPage<MarketplaceApp>(`/marketplace/apps?${appendTagIds(q, tagIds)}`);
  },

  listPendingMarketplaceApps: (page = 1, size = DEFAULT_PAGE_SIZE, tagIds?: string[]) =>
    getPage<MarketplaceApp>(
      `/marketplace/apps/pending?${appendTagIds(buildPageQuery(page, size), tagIds)}`,
    ),

  listMyMarketplaceApps: (page = 1, size = DEFAULT_PAGE_SIZE, tagIds?: string[]) =>
    getPage<MarketplaceApp>(
      `/marketplace/apps/mine?${appendTagIds(buildPageQuery(page, size), tagIds)}`,
    ),

  getMarketplaceApp: (appId: string) => get<MarketplaceAppDetail>(`/marketplace/apps/${appId}`),

  listMarketplaceAppRatings: (appId: string, page = 1, size = 10) =>
    getPage<AppRating>(`/marketplace/apps/${appId}/ratings?${buildPageQuery(page, size)}`),

  createMarketplaceAppFromResources: (body: {
    name: string;
    description?: string;
    icon?: string;
    category_slug?: string;
    flow_id?: string;
    agent_id?: string;
    kb_id?: string;
    tag_ids?: string[];
    visibility?: "public" | "tenant_only";
  }) => post<MarketplaceApp>("/marketplace/apps/from-resources", body),

  publishMarketplaceApp: (appId: string) =>
    post<MarketplaceApp>(`/marketplace/apps/${appId}/publish`),

  approveMarketplaceApp: (appId: string) =>
    post<MarketplaceApp>(`/marketplace/apps/${appId}/approve`),

  rejectMarketplaceApp: (appId: string, note?: string) =>
    post<MarketplaceApp>(`/marketplace/apps/${appId}/reject`, { note }),

  rateMarketplaceApp: (appId: string, body: { score: number; comment?: string }) =>
    post<AppRating>(`/marketplace/apps/${appId}/ratings`, body),

  deleteMyMarketplaceRating: (appId: string) =>
    http.delete(`/marketplace/apps/${appId}/ratings/mine`).then(() => undefined),

  installMarketplaceApp: (appId: string) =>
    post<AppInstallResult>(`/marketplace/apps/${appId}/install`),

  trialMarketplaceApp: (appId: string) =>
    post<AppInstallResult>(`/marketplace/apps/${appId}/trial`),

  getMarketplaceUpgradePreview: (appId: string) =>
    get<import("../types").AppUpgradePreview>(`/marketplace/apps/${appId}/upgrade-preview`),

  getMarketplaceRollbackPreview: (appId: string) =>
    get<import("../types").AppRollbackPreview>(`/marketplace/apps/${appId}/rollback-preview`),

  rollbackMarketplaceApp: (appId: string) =>
    post<{ message: string }>(`/marketplace/apps/${appId}/rollback`, {}),

  upgradeMarketplaceApp: (appId: string) =>
    post<import("../types").AppUpgradeResult>(`/marketplace/apps/${appId}/upgrade`, {}),

  listAppInstalls: (page = 1, size = DEFAULT_PAGE_SIZE) =>
    getPage<AppInstall>(`/marketplace/installs?${buildPageQuery(page, size)}`),
};
