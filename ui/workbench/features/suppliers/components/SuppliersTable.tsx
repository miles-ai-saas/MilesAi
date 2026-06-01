"use client";

import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import { SUPPLIER_CATEGORIES, SUPPLIER_CATEGORY_LABELS, SUPPLIER_STATUS_LABELS, supplierStatusBadgeClass } from "@/features/suppliers/lib/supplier-labels";
import type { SuppliersPageVm } from "@/features/suppliers/hooks/use-suppliers-page";
import type { BizSupplier } from "@/lib/types";

export function SuppliersTable({ vm }: { vm: SuppliersPageVm }) {
  const { list, onDelete, openDetail } = vm;

  if (list.loading) return <p className="text-sm text-ink-muted">加载中…</p>;

  return (
    <>
      <div className="card overflow-hidden">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-line bg-surface-muted text-xs text-ink-muted">
            <tr>
              <th className="px-4 py-2">供应商</th>
              <th className="px-4 py-2">类型</th>
              <th className="px-4 py-2">状态</th>
              <th className="px-4 py-2">合作项目</th>
              <th className="px-4 py-2">主联系人</th>
              <th className="px-4 py-2 text-right">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line-soft">
            {list.items.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-ink-faint">暂无供应商</td></tr>
            )}
            {list.items.map((s: BizSupplier) => (
              <tr key={s.id}>
                <td className="px-4 py-3">
                  <button type="button" onClick={() => openDetail(s.id)} className="font-medium text-ink hover:text-brand text-left">
                    {s.name}
                  </button>
                  {s.short_name && <span className="ml-2 text-xs text-ink-faint">{s.short_name}</span>}
                </td>
                <td className="px-4 py-3 text-ink-muted">{SUPPLIER_CATEGORY_LABELS[s.category] ?? s.category}</td>
                <td className="px-4 py-3">
                  <span className={`rounded px-2 py-0.5 text-xs ${supplierStatusBadgeClass(s.status)}`}>
                    {SUPPLIER_STATUS_LABELS[s.status] ?? s.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-ink-muted">{s.project_count}</td>
                <td className="px-4 py-3 text-ink-muted">{s.contact_name || s.contacts.find((c) => c.is_primary)?.name || "—"}</td>
                <td className="px-4 py-3 text-right">
                  <button type="button" className="mr-3 text-xs text-brand hover:underline" onClick={() => openDetail(s.id)}>详情</button>
                  <button type="button" className="text-xs text-red-600 hover:underline" onClick={() => onDelete(s)}>删除</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ResourceListFooter className="mt-3" page={list.page} size={list.size} total={list.total} onPageChange={list.setPage} onSizeChange={list.setSize} />
    </>
  );
}

export function SuppliersFilters({ vm }: { vm: SuppliersPageVm }) {
  const { search, category, status, onSearch, onCategory, onStatus } = vm;
  return (
    <div className="mb-4 flex flex-wrap gap-3">
      <input
        type="search"
        placeholder="搜索供应商名称…"
        value={search}
        onChange={(e) => onSearch(e.target.value)}
        className="input-field w-full max-w-xs text-sm"
      />
      <select className="input-field text-sm" value={category} onChange={(e) => onCategory(e.target.value)}>
        <option value="">全部类型</option>
        {SUPPLIER_CATEGORIES.map((c) => <option key={c.key} value={c.key}>{c.label}</option>)}
      </select>
      <select className="input-field text-sm" value={status} onChange={(e) => onStatus(e.target.value)}>
        <option value="">全部状态</option>
        <option value="active">合作中</option>
        <option value="inactive">暂停合作</option>
        <option value="blacklisted">黑名单</option>
      </select>
    </div>
  );
}
