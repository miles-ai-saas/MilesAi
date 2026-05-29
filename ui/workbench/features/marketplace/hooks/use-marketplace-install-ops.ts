"use client";

import { useMarketplaceInstallReviewOps } from "@/features/marketplace/hooks/use-marketplace-install-review-ops";
import { useMarketplaceVersionOps } from "@/features/marketplace/hooks/use-marketplace-version-ops";
import type { MarketplaceMainView } from "@/features/marketplace/hooks/use-marketplace-page";

type Params = {
  setMsg: (msg: string) => void;
  mainView: MarketplaceMainView;
  reviewMode: string;
  showReviewTab: boolean;
  detailAppId: string | null;
  reloadDetail: (appId: string) => Promise<void>;
  reloadApps: () => Promise<void>;
  reloadInstalls: () => Promise<void>;
  reloadMyApps: () => Promise<void>;
  reloadPendingApps: () => Promise<void>;
};

export function useMarketplaceInstallOps(params: Params) {
  const version = useMarketplaceVersionOps({
    setMsg: params.setMsg,
    reloadInstalls: params.reloadInstalls,
  });

  const installReview = useMarketplaceInstallReviewOps(params);

  return {
    ...version,
    ...installReview,
  };
}

export type MarketplaceInstallOps = ReturnType<typeof useMarketplaceInstallOps>;
