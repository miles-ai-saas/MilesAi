"use client";

import { MarketplaceReviewPageView } from "@/components/marketplace/MarketplaceReviewPageView";
import { useMarketplaceReviewPage } from "@/hooks/use-marketplace-review-page";

export default function MarketplaceReviewPage() {
  const vm = useMarketplaceReviewPage();
  return <MarketplaceReviewPageView vm={vm} />;
}
