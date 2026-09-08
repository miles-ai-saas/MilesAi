"use client";

export default function MarketplaceReviewPage() {
  const vm = useMarketplaceReviewPage();
  return <MarketplaceReviewPageView vm={vm} />;
}
import { MarketplaceReviewPageView, useMarketplaceReviewPage } from "@/features/marketplace";
