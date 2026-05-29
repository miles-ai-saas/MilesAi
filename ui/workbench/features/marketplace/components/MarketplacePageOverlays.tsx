"use client";

import { MarketplaceAppDetailDrawer } from "@/features/marketplace/components/MarketplaceAppDetailDrawer";
import { MarketplaceUpgradeDialog } from "@/features/marketplace/components/MarketplaceUpgradeDialog";
import { PromptDialog } from "@/components/resource/PromptDialog";
import type { MarketplacePageVm } from "@/features/marketplace/hooks/use-marketplace-page";

export function MarketplacePageOverlays({ vm }: { vm: MarketplacePageVm }) {
  return (
    <>
      <MarketplaceAppDetailDrawer
        open={vm.detailAppId !== null}
        loading={vm.detailLoading}
        detail={vm.detail}
        ratings={vm.detailRatings}
        installingId={vm.installing}
        rateScore={vm.rateScore}
        rateComment={vm.rateComment}
        rateSaving={vm.rateSaving}
        marketplaceMeta={vm.marketplaceMeta}
        onClose={vm.closeDetail}
        onInstall={vm.onInstall}
        onRateScoreChange={vm.setRateScore}
        onRateCommentChange={vm.setRateComment}
        onSaveRating={() => void vm.onSaveRating()}
        onDeleteRating={() => void vm.onDeleteRating()}
      />
      <MarketplaceUpgradeDialog
        open={vm.upgradeTarget !== null}
        loading={vm.upgradePreviewLoading}
        preview={vm.upgradePreview}
        upgrading={vm.upgrading !== null}
        onClose={vm.closeUpgradeDialog}
        onConfirm={() => void vm.onConfirmUpgrade()}
        mode="upgrade"
      />
      <MarketplaceUpgradeDialog
        open={vm.rollbackTarget !== null}
        loading={vm.rollbackPreviewLoading}
        preview={vm.rollbackPreview}
        upgrading={vm.rollingBack !== null}
        onClose={vm.closeRollbackDialog}
        onConfirm={() => void vm.onConfirmRollback()}
        mode="rollback"
      />
      <PromptDialog
        open={vm.rejectTarget !== null}
        title="驳回应用"
        description="驳回原因将展示给发布方。"
        label="驳回原因（可选）"
        placeholder="请填写驳回原因"
        confirmLabel="确认驳回"
        destructive
        loading={vm.rejectLoading}
        onClose={() => {
          if (!vm.rejectLoading) vm.setRejectTarget(null);
        }}
        onConfirm={vm.onConfirmReject}
      />
    </>
  );
}
