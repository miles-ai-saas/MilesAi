"use client";

import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import {
  SUPPLIER_CATEGORIES,
  SUPPLIER_CATEGORY_LABELS,
  SUPPLIER_STATUSES,
  SUPPLIER_STATUS_LABELS,
  supplierStatusBadgeClass,
} from "@/features/suppliers/lib/supplier-labels";
import type { SuppliersPageVm } from "@/features/suppliers/hooks/use-suppliers-page";
import type { BizSupplier } from "@/lib/types";

function SupplierRowActions({
  supplier,
  onOpen,
  onDelete,
}: {
  supplier: BizSupplier;
  onOpen: () => void;
  onDelete: () => void;
}) {
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

function SupplierMobileCard({
  supplier,
  onOpen,
  onDelete,
}: {
  supplier: BizSupplier;
  onOpen: () => void;
  onDelete: () => void;
}) {
  const contact = supplier.contact_name || supplier.contacts.find((c) => c.is_primary)?.name;

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
          <h3 className="truncate font-medium text-ink">{supplier.name}</h3>
          {supplier.short_name ? <p className="truncate text-xs text-ink-faint">{supplier.short_name}</p> : null}
        </div>
        <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs ${supplierStatusBadgeClass(supplier.status)}`}>
          {SUPPLIER_STATUS_LABELS[supplier.status] ?? supplier.status}
        </span>
      </div>
      <div className="mt-3 flex flex-wrap gap-2 text-xs text-ink-muted">
        <span className="rounded-full bg-surface-muted px-2 py-0.5">
          {SUPPLIER_CATEGORY_LABELS[supplier.category] ?? supplier.category}
        </span>
        <span>{supplier.project_count} 个项目</span>
        {contact ? <span>{contact}</span> : null}
      </div>
      <div className="mt-3 flex justify-end" onClick={(e) => e.stopPropagation()} onKeyDown={(e) => e.stopPropagation()}>
        <SupplierRowActions supplier={supplier} onOpen={onOpen} onDelete={onDelete} />
      </div>
    </article>
  );
}

function TableSkeleton() {
  return (
    <div className="divide-y divide-line-soft">
      {[1, 2, 3, 4, 5].map((i) => (
        <div key={i} className="flex gap-4 px-4 py-4">
          <div className="h-4 w-1/3 animate-pulse rounded bg-surface-muted" />
          <div className="h-4 w-16 animate-pulse rounded bg-surface-muted" />
          <div className="h-4 w-16 animate-pulse rounded bg-surface-muted hidden sm:block" />
        </div>
      ))}
    </div>
  );
}

export function SuppliersTable({ vm }: { vm: SuppliersPageVm }) {
  const { list, onDelete, openDetail } = vm;

  if (list.loading) {
    return <TableSkeleton />;
  }

  if (list.items.length === 0) {
    return (
      <div className="px-4 py-16 text-center">
        <p className="text-sm text-ink-muted">暂无匹配的供应商</p>
        <p className="mt-1 text-xs text-ink-faint">调整筛选条件，或点击右上角新建供应商</p>
      </div>
    );
  }

  return (
    <>
      <div className="space-y-3 p-3 md:hidden">
        {list.items.map((supplier) => (
          <SupplierMobileCard
            key={supplier.id}
            supplier={supplier}
            onOpen={() => openDetail(supplier.id)}
            onDelete={() => onDelete(supplier)}
          />
        ))}
      </div>

      <div className="hidden md:block overflow-x-auto">
        <table className="w-full min-w-[720px] text-left text-sm">
          <thead className="border-b border-line bg-surface-muted/60 text-xs text-ink-muted">
            <tr>
              <th className="px-4 py-2.5 font-medium">供应商</th>
              <th className="px-4 py-2.5 font-medium">类型</th>
              <th className="px-4 py-2.5 font-medium">状态</th>
              <th className="px-4 py-2.5 font-medium">合作项目</th>
              <th className="px-4 py-2.5 font-medium">主联系人</th>
              <th className="px-4 py-2.5 text-right font-medium">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line-soft">
            {list.items.map((supplier) => {
              const contact =
                supplier.contact_name || supplier.contacts.find((c) => c.is_primary)?.name || "—";
              return (
                <tr
                  key={supplier.id}
                  className="cursor-pointer transition hover:bg-surface-muted/40"
                  onClick={() => openDetail(supplier.id)}
                >
                  <td className="px-4 py-3">
                    <p className="font-medium text-ink">{supplier.name}</p>
                    {supplier.short_name ? (
                      <p className="text-xs text-ink-faint">{supplier.short_name}</p>
                    ) : null}
                  </td>
                  <td className="px-4 py-3">
                    <span className="rounded-full bg-surface-muted px-2 py-0.5 text-xs text-ink-muted">
                      {SUPPLIER_CATEGORY_LABELS[supplier.category] ?? supplier.category}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`rounded-full px-2 py-0.5 text-xs ${supplierStatusBadgeClass(supplier.status)}`}>
                      {SUPPLIER_STATUS_LABELS[supplier.status] ?? supplier.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 tabular-nums text-ink-muted">{supplier.project_count}</td>
                  <td className="px-4 py-3 text-ink-muted">{contact}</td>
                  <td className="px-4 py-3" onClick={(e) => e.stopPropagation()} onKeyDown={(e) => e.stopPropagation()}>
                    <SupplierRowActions
                      supplier={supplier}
                      onOpen={() => openDetail(supplier.id)}
                      onDelete={() => onDelete(supplier)}
                    />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}

export function SuppliersFilters({ vm }: { vm: SuppliersPageVm }) {
  const {
    search,
    category,
    status,
    onSearch,
    onCategory,
    onStatus,
    clearFilters,
    hasActiveFilters,
  } = vm;

  return (
    <div className="space-y-3 border-b border-line bg-surface-muted/20 px-4 py-4">
      <div className="flex flex-wrap items-center gap-3">
        <input
          type="search"
          placeholder="搜索供应商名称…"
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

      <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-ink-muted">类型</span>
          <button
            type="button"
            className={`rounded-full px-2.5 py-0.5 text-xs ${
              !category ? "bg-brand text-white" : "border border-line bg-surface text-ink-muted hover:text-ink"
            }`}
            onClick={() => onCategory("")}
          >
            全部
          </button>
          {SUPPLIER_CATEGORIES.map((item) => (
            <button
              key={item.key}
              type="button"
              className={`rounded-full px-2.5 py-0.5 text-xs ${
                category === item.key
                  ? "bg-brand/10 font-medium text-brand ring-1 ring-brand/30"
                  : "border border-line bg-surface text-ink-muted hover:border-brand/30 hover:text-ink"
              }`}
              onClick={() => onCategory(category === item.key ? "" : item.key)}
            >
              {item.label}
            </button>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-ink-muted">状态</span>
          <button
            type="button"
            className={`rounded-full px-2.5 py-0.5 text-xs ${
              !status ? "bg-brand text-white" : "border border-line bg-surface text-ink-muted hover:text-ink"
            }`}
            onClick={() => onStatus("")}
          >
            全部
          </button>
          {SUPPLIER_STATUSES.map((item) => (
            <button
              key={item.key}
              type="button"
              className={`rounded-full px-2.5 py-0.5 text-xs ${
                status === item.key
                  ? "bg-brand/10 font-medium text-brand ring-1 ring-brand/30"
                  : "border border-line bg-surface text-ink-muted hover:border-brand/30 hover:text-ink"
              }`}
              onClick={() => onStatus(status === item.key ? "" : item.key)}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

export function SuppliersListFooter({ vm }: { vm: SuppliersPageVm }) {
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
