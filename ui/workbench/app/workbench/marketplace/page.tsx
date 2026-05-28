"use client";

/** 应用市场（链路 §12）：多主视图 + 分页列表 + `useMarketplaceMeta`。 */

import { MarketplaceInstallsView } from "@/components/marketplace/MarketplaceInstallsView";
import { MarketplaceMineView } from "@/components/marketplace/MarketplaceMineView";
import { MarketplacePageOverlays } from "@/components/marketplace/MarketplacePageOverlays";
import { MarketplacePlazaView } from "@/components/marketplace/MarketplacePlazaView";
import { MarketplacePublishView } from "@/components/marketplace/MarketplacePublishView";
import { MarketplaceReviewView } from "@/components/marketplace/MarketplaceReviewView";
import { useMarketplacePage } from "@/hooks/use-marketplace-page";

export default function MarketplacePage() {
  const vm = useMarketplacePage();
  const overlays = <MarketplacePageOverlays vm={vm} />;

  if (vm.mainView === "plaza") {
    return (
      <>
        <MarketplacePlazaView vm={vm} />
        {overlays}
      </>
    );
  }

  if (vm.mainView === "installs") {
    return (
      <>
        <MarketplaceInstallsView vm={vm} />
        {overlays}
      </>
    );
  }

  if (vm.mainView === "mine") {
    return (
      <>
        <MarketplaceMineView vm={vm} />
        {overlays}
      </>
    );
  }

  if (vm.mainView === "review" && vm.showReviewTab) {
    return (
      <>
        <MarketplaceReviewView vm={vm} />
        {overlays}
      </>
    );
  }

  return (
    <>
      <MarketplacePublishView vm={vm} />
      {overlays}
    </>
  );
}
