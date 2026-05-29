"use client";

import { AddResourceCard } from "@/components/resource/AddResourceCard";
import { ResourceListLayout } from "@/components/resource/ResourceListLayout";
import { TagFilterDropdown } from "@/components/tag/TagFilterDropdown";
import { ToolCard } from "@/features/tools/components/ToolCard";
import { FilterChip, StatChip } from "@/features/tools/components/tool-page-ui";
import { catalogSourceTabs } from "@/features/tools/lib/tool-labels";
import type { ToolsPageVm } from "@/features/tools/hooks/use-tools-page";

export function ToolsCatalogTab({ vm }: { vm: ToolsPageVm }) {
  return (
    <ResourceListLayout
      {...vm.layoutCommon}
      searchPlaceholder="搜索工具名称、编号或描述"
      search={vm.search}
      onSearchChange={vm.setSearch}
      loading={vm.loading}
      headerAction={
        <div className="flex flex-wrap items-center gap-2">
          <button type="button" className="btn-ghost shrink-0 text-sm" disabled={vm.loading} onClick={() => void vm.reloadCatalog()}>
            {vm.loading ? "刷新中…" : "刷新"}
          </button>
          <TagFilterDropdown value={vm.tagFilterIds} onChange={vm.setTagFilterIds} />
          <button type="button" className="btn-ghost border border-line text-sm" onClick={() => vm.setTagManageOpen(true)}>
            管理标签
          </button>
        </div>
      }
    >
      <div className="col-span-full rounded-xl border border-brand/20 bg-brand-light/30 px-4 py-3 text-xs text-brand">
        外部 MCP 工具不在此列表展示，请前往{" "}
        <a href="/workbench/mcp" className="font-medium underline">
          MCP 工作台
        </a>
        。
      </div>

      <div className="col-span-full grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <StatChip label="工具总数" value={String(vm.catalogStats.total)} hint="当前筛选条件下" />
        <StatChip label="内置" value={String(vm.catalogStats.builtin)} />
        <StatChip label="自定义" value={String(vm.catalogStats.custom)} hint={`本页展示 ${vm.filtered.length} 个`} />
      </div>

      <div className="col-span-full rounded-xl border border-line bg-surface-muted/40 p-4">
        <p className="mb-2 text-xs font-medium text-ink-muted">来源</p>
        <div className="flex flex-wrap gap-2">
          {catalogSourceTabs(vm.toolsMeta).map((tab) => (
            <FilterChip key={tab.key || "all"} active={vm.sourceTab === tab.key} label={tab.label} onClick={() => vm.setSourceTab(tab.key)} />
          ))}
        </div>
      </div>

      {vm.sourceTab !== "builtin" && <AddResourceCard label="添加新工具" hint="创建 HTTP 工具扩展智能体能力" onClick={vm.openCreate} />}

      {!vm.loading && vm.filtered.length === 0 && (
        <p className="col-span-full py-12 text-center text-sm text-ink-faint">暂无匹配的工具，可调整筛选或创建自定义工具</p>
      )}

      {vm.filtered.map((t) => (
        <ToolCard
          key={`${t.source}-${t.slug}-${t.tool_id ?? ""}`}
          tool={t}
          toolsMeta={vm.toolsMeta}
          onDetail={() => vm.openDetail(t)}
          onTest={() => vm.openTest(t)}
          onEdit={t.source === "custom" ? () => void vm.openEdit(t) : undefined}
          onDelete={t.source === "custom" ? () => vm.onDelete(t) : undefined}
        />
      ))}
    </ResourceListLayout>
  );
}
