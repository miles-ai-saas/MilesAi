"use client";

import Link from "next/link";
import { PageMessage } from "@/components/ui/PageMessage";
import { StatChip } from "@/components/ui/StatChip";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { ResourceItemCard } from "@/components/resource/ResourceItemCard";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import { TagFilterDropdown } from "@/components/tag/TagFilterDropdown";
import { MarketplaceAppCardActions, MarketplaceAppCardMeta } from "@/features/marketplace/components/MarketplaceAppCardParts";
import { marketplaceCatalogSortOptions } from "@/features/marketplace/lib/marketplace-labels";
import type { MarketplacePageVm } from "@/features/marketplace/hooks/use-marketplace-page";
import type { AppInstallResult } from "@/lib/types";
import { buildAgentsChatHref } from "@/features/agents/lib/agents-chat-href";

function agentChatHref(agentId: string): string {
  return buildAgentsChatHref({ agent: agentId });
}
function MarketplaceInstallSuccessBanner({ result, onDismiss }: { result: AppInstallResult; onDismiss: () => void }) {
  return (
    <div className="col-span-full rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">
      <div className="flex items-start justify-between gap-3">
        <p className="font-medium">{result.message || "安装完成"}</p>
        <button type="button" className="text-xs opacity-70 hover:opacity-100" onClick={onDismiss}>
          关闭
        </button>
      </div>
      <ul className="mt-2 space-y-1 text-xs">
        {result.kb_id ? (
          <li>
            知识库 →{" "}
            <Link href={`/workbench/kb/detail?id=${result.kb_id}`} className="underline">
              管理文档
            </Link>
          </li>
        ) : null}
        {result.flow_id ? (
          <li>
            流程 →{" "}
            <Link href={`/workbench/flows/edit?id=${result.flow_id}`} className="underline">
              编辑画布
            </Link>
          </li>
        ) : null}
        {result.agent_id ? (
          <li>
            智能体 →{" "}
            <Link href={agentChatHref(result.agent_id)} className="underline">
              去对话
            </Link>
          </li>
        ) : null}
      </ul>
    </div>
  );
}

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
          <ResourceListFooter page={vm.apps.page} size={vm.apps.size} total={vm.apps.total} onPageChange={vm.apps.setPage} onSizeChange={vm.apps.setSize} />
        ) : null
      }
    >
      {vm.msg ? <PageMessage message={vm.msg} onDismiss={() => vm.setMsg("")} /> : null}
      {vm.lastResult ? <MarketplaceInstallSuccessBanner result={vm.lastResult} onDismiss={() => vm.setLastResult(null)} /> : null}
      <div className="col-span-full grid gap-3 sm:grid-cols-2">
        <StatChip label="广场应用" value={String(vm.apps.total)} hint="已上架可安装" />
        <StatChip label="本页已安装" value={String(vm.plazaInstalledOnPage)} hint={`本页共 ${vm.plazaFiltered.length} 个`} />
      </div>
      <div className="col-span-full flex flex-wrap gap-2 border-b border-line pb-4">
        {vm.categoryTabs.map((tab) => (
          <button
            key={tab.key || "all"}
            type="button"
            onClick={() => vm.setActiveCategory(tab.key)}
            className={`rounded-lg px-3 py-1.5 text-xs transition ${
              vm.activeCategory === tab.key ? "bg-brand-light font-medium text-brand" : "text-ink-muted hover:bg-surface-muted hover:text-ink"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>
      {!vm.apps.loading && vm.plazaFiltered.length === 0 ? <p className="col-span-full py-12 text-center text-sm text-ink-faint">暂无匹配的应用</p> : null}
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
