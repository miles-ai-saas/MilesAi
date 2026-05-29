"use client";

import { PageHeader } from "@/components/layout/PageHeader";
import {
  MarketplaceReviewDetailSection,
  MarketplaceReviewListSection,
  MarketplaceReviewRejectDialog,
} from "@/components/marketplace/MarketplaceReviewSections";
import type { MarketplaceReviewPageVm } from "@/hooks/use-marketplace-review-page";
import { MARKETPLACE_REVIEW_FORBIDDEN_DESCRIPTION, MARKETPLACE_REVIEW_PAGE_DESCRIPTION } from "@/lib/marketplace-review-page-shared";

export function MarketplaceReviewPageView({ vm }: { vm: MarketplaceReviewPageVm }) {
  const { forbidden, reviewMode, msg, err } = vm;

  if (forbidden) {
    return (
      <div>
        <PageHeader title="应用审核" description={MARKETPLACE_REVIEW_FORBIDDEN_DESCRIPTION} />
        <p className="text-sm text-ink-muted">当前 review_mode={reviewMode}，请在工作台由租户侧审核。</p>
      </div>
    );
  }

  return (
    <div>
      <PageHeader title="应用审核" description={MARKETPLACE_REVIEW_PAGE_DESCRIPTION} />

      {msg && <p className="mb-4 text-sm text-emerald-600">{msg}</p>}
      {err && <p className="mb-4 text-sm text-red-600">{err}</p>}

      <MarketplaceReviewListSection vm={vm} />
      <MarketplaceReviewDetailSection vm={vm} />
      <MarketplaceReviewRejectDialog vm={vm} />
    </div>
  );
}
