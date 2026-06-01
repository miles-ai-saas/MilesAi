"use client";

import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { BizTableSkeleton } from "@/features/business/components/BizListSkeleton";
import type { ClientsPageVm } from "@/features/clients/hooks/use-clients-page";
import {
  CLIENT_CONFIDENTIALITY_LABELS,
  CLIENT_INDUSTRY_LABELS,
  clientConfBadgeClass,
} from "@/features/clients/lib/client-labels";
import type { BizClient } from "@/lib/types";

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

function ClientMobileCard({
  client,
  onOpen,
  onDelete,
}: {
  client: BizClient;
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
        <div className="min-w-0">
          <h3 className="truncate font-medium text-ink">{client.name}</h3>
          {client.short_name ? <p className="truncate text-xs text-ink-faint">{client.short_name}</p> : null}
        </div>
        <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs ${clientConfBadgeClass(client.confidentiality_level)}`}>
          {CLIENT_CONFIDENTIALITY_LABELS[client.confidentiality_level] ?? client.confidentiality_level}
        </span>
      </div>
      <div className="mt-3 flex flex-wrap gap-2 text-xs text-ink-muted">
        <span className="rounded-full bg-surface-muted px-2 py-0.5">
          {CLIENT_INDUSTRY_LABELS[client.industry ?? ""] ?? client.industry ?? "—"}
        </span>
        <span>{client.project_count} 个项目</span>
      </div>
      <div className="mt-3 flex justify-end" onClick={(e) => e.stopPropagation()} onKeyDown={(e) => e.stopPropagation()}>
        <RowActions onOpen={onOpen} onDelete={onDelete} />
      </div>
    </article>
  );
}

export function ClientsFilters({ vm }: { vm: ClientsPageVm }) {
  const { search, onSearch, clearFilters, hasActiveFilters } = vm;

  return (
    <div className="border-b border-line bg-surface-muted/20 px-4 py-4">
      <div className="flex flex-wrap items-center gap-3">
        <input
          type="search"
          placeholder="搜索客户名称…"
          value={search}
          onChange={(e) => onSearch(e.target.value)}
          className="input-field h-9 w-full max-w-xs text-sm"
        />
        {hasActiveFilters ? (
          <button type="button" className="btn-ghost text-xs text-ink-muted" onClick={clearFilters}>
            清除筛选
          </button>
        ) : null}
      </div>
    </div>
  );
}

export function ClientsTable({ vm }: { vm: ClientsPageVm }) {
  const { list, onDelete, openDetail } = vm;

  if (list.loading) {
    return <BizTableSkeleton />;
  }

  if (list.items.length === 0) {
    return (
      <div className="px-4 py-16 text-center">
        <p className="text-sm text-ink-muted">暂无匹配的客户</p>
        <p className="mt-1 text-xs text-ink-faint">调整搜索条件，或点击右上角新建客户</p>
      </div>
    );
  }

  return (
    <>
      <div className="space-y-3 p-3 md:hidden">
        {list.items.map((client) => (
          <ClientMobileCard
            key={client.id}
            client={client}
            onOpen={() => openDetail(client.id)}
            onDelete={() => onDelete(client)}
          />
        ))}
      </div>

      <div className="hidden overflow-x-auto md:block">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead className="border-b border-line bg-surface-muted/60 text-xs text-ink-muted">
            <tr>
              <th className="px-4 py-2.5 font-medium">客户名称</th>
              <th className="px-4 py-2.5 font-medium">行业</th>
              <th className="px-4 py-2.5 font-medium">保密等级</th>
              <th className="px-4 py-2.5 font-medium">项目数</th>
              <th className="px-4 py-2.5 text-right font-medium">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line-soft">
            {list.items.map((client) => (
              <tr
                key={client.id}
                className="cursor-pointer transition hover:bg-surface-muted/40"
                onClick={() => openDetail(client.id)}
              >
                <td className="px-4 py-3">
                  <p className="font-medium text-ink">{client.name}</p>
                  {client.short_name ? <p className="text-xs text-ink-faint">{client.short_name}</p> : null}
                </td>
                <td className="px-4 py-3">
                  <span className="rounded-full bg-surface-muted px-2 py-0.5 text-xs text-ink-muted">
                    {CLIENT_INDUSTRY_LABELS[client.industry ?? ""] ?? client.industry ?? "—"}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className={`rounded-full px-2 py-0.5 text-xs ${clientConfBadgeClass(client.confidentiality_level)}`}>
                    {CLIENT_CONFIDENTIALITY_LABELS[client.confidentiality_level] ?? client.confidentiality_level}
                  </span>
                </td>
                <td className="px-4 py-3 tabular-nums text-ink-muted">{client.project_count}</td>
                <td className="px-4 py-3" onClick={(e) => e.stopPropagation()} onKeyDown={(e) => e.stopPropagation()}>
                  <RowActions onOpen={() => openDetail(client.id)} onDelete={() => onDelete(client)} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

export function ClientsListFooter({ vm }: { vm: ClientsPageVm }) {
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
