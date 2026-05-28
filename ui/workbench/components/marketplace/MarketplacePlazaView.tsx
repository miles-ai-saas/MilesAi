"use client";

import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import { TagFilterDropdown } from "@/components/tag/TagFilterDropdown";
import {
  MarketplaceAppCardActions,
  MarketplaceAppCardMeta,
} from "@/components/marketplace/MarketplaceAppCardParts";
import {
  MarketplaceInstallSuccessBanner,
  MarketplacePageMessage,
  MarketplaceStatChip,
} from "@/components/marketplace/marketplace-page-ui";
import { marketplaceCatalogSortOptions } from "@/lib/marketplace-labels";
import type { MarketplacePageVm } from "@/hooks/use-marketplace-page";

export function MarketplacePlazaView({ vm }: { vm: MarketplacePageVm }) {
  return (
    <ResourceListLayout
      {...vm.layoutCommon}
      searchPlaceholder="搜索应用名称、描述或标签"
      search={vm.search}
      onSearchChange={vm.setSearch}
      loading={vm.apps.loading}
      headerAction={
        <div className="flex flex-wrap items-center gap-2">
          <TagFilterDropdown value={vm.tagFilterIds} onChange={vm.setTagFilterIds} />
          <select
            className="input-field w-auto shrink-0 text-sm"
            value={vm.plazaSort}
            onChange={(e) => vm.setPlazaSort(e.target.value as "installs" | "rating")}
            aria-label="排序方式"
          >
            {marketplaceCatalogSortOptions(vm.marketplaceMeta).map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
      }
      footer={
        !vm.apps.loading ? (
          <ResourceListFooter
            page={vm.apps.page}
            size={vm.apps.size}
            total={vm.apps.total}
            onPageChange={vm.apps.setPage}
            onSizeChange={vm.apps.setSize}
          />
        ) : null
      }
    >
      {vm.msg ? <MarketplacePageMessage message={vm.msg} onDismiss={() => vm.setMsg("")} /> : null}
      {vm.lastResult ? (
        <MarketplaceInstallSuccessBanner result={vm.lastResult} onDismiss={() => vm.setLastResult(null)} />
      ) : null}
      <div className="col-span-full grid gap-3 sm:grid-cols-2">
        <MarketplaceStatChip label="广场应用" value={String(vm.apps.total)} hint="已上架可安装" />
        <MarketplaceStatChip
          label="本页已安装"
          value={String(vm.plazaInstalledOnPage)}
          hint={`本页共 ${vm.plazaFiltered.length} 个`}
        />
      </div>
      <div className="col-span-full flex flex-wrap gap-2 border-b border-line pb-4">
        {vm.categoryTabs.map((tab) => (
          <button
            key={tab.key || "all"}
            type="button"
            onClick={() => vm.setActiveCategory(tab.key)}
            className={`rounded-lg px-3 py-1.5 text-xs transition ${
              vm.activeCategory === tab.key
                ? "bg-brand-light font-medium text-brand"
                : "text-ink-muted hover:bg-surface-muted hover:text-ink"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>
      {!vm.apps.loading && vm.plazaFiltered.length === 0 ? (
        <p className="col-span-full py-12 text-center text-sm text-ink-faint">暂无匹配的应用</p>
      ) : null}
      {vm.plazaFiltered.map((app) => (
        <ResourceItemCard
          key={app.id}
          title={`${app.icon || "📦"} ${app.name}`}
          description={app.description ?? "应用模板"}
          badge={app.installed ? "已安装" : app.is_official ? "官方" : app.category_name || undefined}
          meta={<MarketplaceAppCardMeta app={app} marketplaceMeta={vm.marketplaceMeta} />}
          onClick={() => void vm.loadDetail(app.id)}
          actions={
            <MarketplaceAppCardActions
              app={app}
              mode="plaza"
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
