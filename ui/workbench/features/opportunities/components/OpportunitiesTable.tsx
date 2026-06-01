"use client";

import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { BizTableSkeleton } from "@/features/business/components/BizListSkeleton";
import type { OpportunitiesPageVm } from "@/features/opportunities/hooks/use-opportunities-page";
import {
  OPPORTUNITY_STAGES,
  OPPORTUNITY_STAGE_LABELS,
  stageBadgeClass,
} from "@/features/opportunities/lib/opportunity-labels";
import type { BizOpportunity } from "@/lib/types";

function RowActions({ onOpen, onDelete }: { onOpen: () => void; onDelete: () => void }) {
  return (
    <div className="flex justify-end gap-2">
      <button type="button" className="text-xs text-brand hover:underline" onClick={onOpen}>
        详情
      </button>
      <button
        type="button"
        className="text-xs text-red-600 hover:underline"
        onClick={(e) => {
          e.stopPropagation();
          onDelete();
        }}
      >
        删除
      </button>
    </div>
  );
}

function OpportunityMobileCard({
  opportunity,
  onOpen,
  onDelete,
}: {
  opportunity: BizOpportunity;
  onOpen: () => void;
  onDelete: () => void;
}) {
  return (
    <article
      className="card cursor-pointer p-4 transition hover:border-brand/30 hover:shadow-sm"
      onClick={onOpen}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onOpen();
        }
      }}
      role="button"
      tabIndex={0}
    >
      <div className="flex items-start justify-between gap-3">
        <h3 className="min-w-0 truncate font-medium text-ink">{opportunity.name}</h3>
        <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs ${stageBadgeClass(opportunity.stage)}`}>
          {OPPORTUNITY_STAGE_LABELS[opportunity.stage] ?? opportunity.stage}
        </span>
      </div>
      <p className="mt-2 text-xs text-ink-muted">
        {opportunity.expected_value != null ? `¥${opportunity.expected_value.toLocaleString()}` : "—"}
        {opportunity.probability != null ? ` · ${opportunity.probability}%` : ""}
      </p>
      <div className="mt-3 flex justify-end" onClick={(e) => e.stopPropagation()} onKeyDown={(e) => e.stopPropagation()}>
        <RowActions onOpen={onOpen} onDelete={onDelete} />
      </div>
    </article>
  );
}

export function OpportunitiesFilters({ vm }: { vm: OpportunitiesPageVm }) {
  const { stage, onStage, clearFilters, hasActiveFilters } = vm;

  return (
    <div className="border-b border-line bg-surface-muted/20 px-4 py-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-ink-muted">阶段</span>
        <button
          type="button"
          className={`rounded-full px-2.5 py-0.5 text-xs ${
            !stage ? "bg-brand text-white" : "border border-line bg-surface text-ink-muted hover:text-ink"
          }`}
          onClick={() => onStage("")}
        >
          全部
        </button>
        {OPPORTUNITY_STAGES.map((item) => (
          <button
            key={item.key}
            type="button"
            className={`rounded-full px-2.5 py-0.5 text-xs ${
              stage === item.key
                ? "bg-brand/10 font-medium text-brand ring-1 ring-brand/30"
                : "border border-line bg-surface text-ink-muted hover:border-brand/30 hover:text-ink"
            }`}
            onClick={() => onStage(stage === item.key ? "" : item.key)}
          >
            {item.label}
          </button>
        ))}
        {hasActiveFilters ? (
          <button type="button" className="btn-ghost text-xs text-ink-muted" onClick={clearFilters}>
            清除筛选
          </button>
        ) : null}
      </div>
    </div>
  );
}

export function OpportunitiesTable({ vm }: { vm: OpportunitiesPageVm }) {
  const { list, onDelete, openDetail } = vm;

  if (list.loading) {
    return <BizTableSkeleton />;
  }

  if (list.items.length === 0) {
    return (
      <div className="px-4 py-16 text-center">
        <p className="text-sm text-ink-muted">暂无匹配的商机</p>
        <p className="mt-1 text-xs text-ink-faint">调整阶段筛选，或切换到看板视图</p>
      </div>
    );
  }

  return (
    <>
      <div className="space-y-3 p-3 md:hidden">
        {list.items.map((opportunity) => (
          <OpportunityMobileCard
            key={opportunity.id}
            opportunity={opportunity}
            onOpen={() => openDetail(opportunity.id)}
            onDelete={() => onDelete(opportunity)}
          />
        ))}
      </div>

      <div className="hidden overflow-x-auto md:block">
        <table className="w-full min-w-[600px] text-left text-sm">
          <thead className="border-b border-line bg-surface-muted/60 text-xs text-ink-muted">
            <tr>
              <th className="px-4 py-2.5 font-medium">商机名称</th>
              <th className="px-4 py-2.5 font-medium">阶段</th>
              <th className="px-4 py-2.5 font-medium">金额/概率</th>
              <th className="px-4 py-2.5 text-right font-medium">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line-soft">
            {list.items.map((opportunity) => (
              <tr
                key={opportunity.id}
                className="cursor-pointer transition hover:bg-surface-muted/40"
                onClick={() => openDetail(opportunity.id)}
              >
                <td className="px-4 py-3 font-medium text-ink">{opportunity.name}</td>
                <td className="px-4 py-3">
                  <span className={`rounded-full px-2 py-0.5 text-xs ${stageBadgeClass(opportunity.stage)}`}>
                    {OPPORTUNITY_STAGE_LABELS[opportunity.stage] ?? opportunity.stage}
                  </span>
                </td>
                <td className="px-4 py-3 text-xs text-ink-muted">
                  {opportunity.expected_value != null ? `¥${opportunity.expected_value.toLocaleString()}` : "—"}
                  {opportunity.probability != null ? ` / ${opportunity.probability}%` : ""}
                </td>
                <td className="px-4 py-3" onClick={(e) => e.stopPropagation()} onKeyDown={(e) => e.stopPropagation()}>
                  <RowActions
                    onOpen={() => openDetail(opportunity.id)}
                    onDelete={() => onDelete(opportunity)}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

export function OpportunitiesListFooter({ vm }: { vm: OpportunitiesPageVm }) {
  const { list } = vm;
  return (
    <ResourceListFooter
      className="border-t border-line px-4 py-3"
      page={list.page}
      size={list.size}
      total={list.total}
      onPageChange={list.setPage}
      onSizeChange={list.setSize}
    />
  );
}
