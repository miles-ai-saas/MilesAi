"use client";

import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import { TagFilterDropdown } from "@/components/tag/TagFilterDropdown";
import { TagChips } from "@/components/tag/TagChips";
import { MarketplaceAppCardActions } from "@/features/marketplace/components/MarketplaceAppCardParts";
import { PageMessage } from "@/components/ui/PageMessage";
import { StatChip } from "@/components/ui/StatChip";
import type { MarketplacePageVm } from "@/features/marketplace/hooks/use-marketplace-page";

export function MarketplaceReviewView({ vm }: { vm: MarketplacePageVm }) {
  return (
    <ResourceListLayout
      {...vm.layoutCommon}
      searchPlaceholder="搜索应用名称、描述或标签"
      search={vm.search}
      onSearchChange={vm.setSearch}
      loading={vm.pendingApps.loading}
      headerAction={<TagFilterDropdown value={vm.tagFilterIds} onChange={vm.setTagFilterIds} />}
      footer={
        !vm.pendingApps.loading ? (
          <ResourceListFooter
            page={vm.pendingApps.page}
            size={vm.pendingApps.size}
            total={vm.pendingApps.total}
            onPageChange={vm.pendingApps.setPage}
            onSizeChange={vm.pendingApps.setSize}
          />
        ) : null
      }
    >
      {vm.msg ? <PageMessage message={vm.msg} onDismiss={() => vm.setMsg("")} /> : null}
      <div className="col-span-full">
        <StatChip label="待审核" value={String(vm.pendingApps.total)} hint="通过后将在应用广场展示" />
      </div>
      <div className="col-span-full space-y-3">
        {!vm.pendingApps.loading && vm.pendingFiltered.length === 0 ? (
          <p className="rounded-xl border border-dashed border-line py-12 text-center text-sm text-ink-faint">暂无待审核应用</p>
        ) : null}
        {vm.pendingFiltered.map((app) => (
          <article
            key={app.id}
            className="flex flex-col gap-4 rounded-xl border border-line bg-surface p-4 shadow-card sm:flex-row sm:items-center sm:justify-between"
          >
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="text-base font-semibold text-ink">
                  {app.icon || "📦"} {app.name}
                </h3>
                <span className="badge bg-amber-50 text-amber-800">待审核</span>
                {app.category_name ? <span className="text-xs text-ink-muted">{app.category_name}</span> : null}
              </div>
              <p className="mt-2 line-clamp-2 text-sm text-ink-muted">{app.description ?? "无描述"}</p>
              <div className="mt-2">
                <TagChips tags={app.tags} />
              </div>
              <p className="mt-2 text-xs text-ink-faint">提交于 {app.submitted_at ? new Date(app.submitted_at).toLocaleString("zh-CN") : "—"}</p>
            </div>
            <div className="flex shrink-0 sm:min-w-[12rem]">
              <MarketplaceAppCardActions
                app={app}
                mode="review"
                installing={vm.installing}
                publishing={vm.publishing}
                reviewing={vm.reviewing}
                onDetail={(id) => void vm.loadDetail(id)}
                onInstall={vm.onInstall}
                onTrial={vm.onTrial}
                onSubmitReview={vm.onSubmitReview}
                onApprove={vm.onApprove}
                onReject={vm.onReject}
              />
            </div>
          </article>
        ))}
      </div>
    </ResourceListLayout>
  );
}
