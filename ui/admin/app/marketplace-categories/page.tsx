"use client";

import { MarketplaceCategoriesPageView } from "@/components/marketplace/MarketplaceCategoriesPageView";
import { useMarketplaceCategoriesPage } from "@/hooks/use-marketplace-categories-page";

export default function MarketplaceCategoriesPage() {
  const vm = useMarketplaceCategoriesPage();
  return <MarketplaceCategoriesPageView vm={vm} />;
}
