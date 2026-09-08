"use client";

export default function MarketplaceCategoriesPage() {
  const vm = useMarketplaceCategoriesPage();
  return <MarketplaceCategoriesPageView vm={vm} />;
}
import { MarketplaceCategoriesPageView, useMarketplaceCategoriesPage } from "@/features/marketplace";
