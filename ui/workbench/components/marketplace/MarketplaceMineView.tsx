"use client";

import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import { TagFilterDropdown } from "@/components/tag/TagFilterDropdown";
import {
  MarketplaceAppCardActions,
  MarketplaceAppCardMeta,
} from "@/components/marketplace/MarketplaceAppCardParts";
import { MarketplacePageMessage } from "@/components/marketplace/marketplace-page-ui";
import { marketplaceStatusLabel } from "@/lib/marketplace-labels";
import type { MarketplacePageVm } from "@/hooks/use-marketplace-page";

export function MarketplaceMineView({ vm }: { vm: MarketplacePageVm }) {
  return (
    <ResourceListLayout
      {...vm.layoutCommon}
      searchPlaceholder="搜索应用名称、描述或标签"
      search={vm.search}
      onSearchChange={vm.setSearch}
      loading={vm.myApps.loading}
      headerAction={
        <div className="flex flex-wrap items-center gap-2">
          <TagFilterDropdown value={vm.tagFilterIds} onChange={vm.setTagFilterIds} />
          <button type="button" className="btn-ghost shrink-0 text-sm" onClick={() => vm.switchView("publish")}>
            新建打包
          </button>
        </div>
      }
      footer={
        !vm.myApps.loading ? (
          <ResourceListFooter
            page={vm.myApps.page}
            size={vm.myApps.size}
            total={vm.myApps.total}
            onPageChange={vm.myApps.setPage}
            onSizeChange={vm.myApps.setSize}
          />
        ) : null
      }
    >
      {vm.msg ? <MarketplacePageMessage message={vm.msg} onDismiss={() => vm.setMsg("")} /> : null}
      {!vm.myApps.loading && vm.myFiltered.length === 0 ? (
        <p className="col-span-full py-12 text-center text-sm text-ink-faint">
          暂无草稿或上架记录，点击「新建打包」创建应用
        </p>
      ) : null}
      {vm.myFiltered.map((app) => (
        <ResourceItemCard
          key={app.id}
          title={`${app.icon || "📦"} ${app.name}`}
          description={
            app.status === "rejected" && app.review_note
              ? `驳回：${app.review_note}`
              : app.description ?? "租户应用"
          }
          badge={marketplaceStatusLabel(app.status, vm.marketplaceMeta)}
          meta={<MarketplaceAppCardMeta app={app} marketplaceMeta={vm.marketplaceMeta} />}
          onClick={() => void vm.loadDetail(app.id)}
          actions={
            <MarketplaceAppCardActions
              app={app}
              mode="mine"
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
          }
        />
      ))}
    </ResourceListLayout>
  );
}
