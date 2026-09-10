"use client";

import { PageHeader } from "@/components/layout/PageHeader";
import {
  MarketplaceReviewDetailSection,
  MarketplaceReviewListSection,
  MarketplaceReviewRejectDialog,
} from "@/features/marketplace/components/MarketplaceReviewSections";
import type { MarketplaceReviewPageVm } from "@/features/marketplace/hooks/use-marketplace-review-page";
import { MARKETPLACE_REVIEW_FORBIDDEN_DESCRIPTION, MARKETPLACE_REVIEW_PAGE_DESCRIPTION } from "@/features/marketplace/lib/marketplace-review-page-shared";

export function MarketplaceReviewPageView({ vm }: { vm: MarketplaceReviewPageVm }) {
  const { forbidden, reviewMode, msg, err } = vm;

  if (forbidden) {
    return (
      <div className="admin-page-stack">
        <PageHeader title="应用审核" description={MARKETPLACE_REVIEW_FORBIDDEN_DESCRIPTION} />
        <p className="text-sm text-ink-muted">当前 review_mode={reviewMode}，请在工作台由租户侧审核。</p>
      </div>
    );
  }

  return (
    <>
      <div className="admin-page-stack">
        <PageHeader title="应用审核" description={MARKETPLACE_REVIEW_PAGE_DESCRIPTION} />

        {msg && <p className="admin-alert-ok">{msg}</p>}
        {err && <p className="admin-alert-err">{err}</p>}

        <MarketplaceReviewListSection vm={vm} />
        <MarketplaceReviewDetailSection vm={vm} />
      </div>
      <MarketplaceReviewRejectDialog vm={vm} />
    </>
  );
}
