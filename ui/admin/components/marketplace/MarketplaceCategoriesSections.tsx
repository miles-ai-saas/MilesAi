"use client";

import type { MarketplaceCategoriesPageVm } from "@/hooks/use-marketplace-categories-page";

export function MarketplaceCategoriesTableSection({ vm }: { vm: MarketplaceCategoriesPageVm }) {
  const { items, openEdit, onDelete } = vm;

  return (
    <div className="admin-table-wrap">
      <table className="admin-table">
        <thead>
          <tr>
            <th>名称</th>
            <th>标识 slug</th>
            <th className="col-center col-numeric">排序</th>
            <th className="col-center col-numeric">关联应用</th>
            <th className="col-actions">操作</th>
          </tr>
        </thead>
        <tbody>
          {items.map((row) => (
            <tr key={row.id}>
              <td className="cell-primary">{row.name}</td>
              <td className="cell-mono">{row.slug}</td>
              <td className="col-center col-numeric cell-numeric">{row.sort_order}</td>
              <td className="col-center col-numeric cell-numeric">{row.app_count}</td>
              <td className="col-actions">
                <button type="button" className="text-brand hover:underline" onClick={() => openEdit(row)}>
                  编辑
                </button>
                <button type="button" className="text-red-600 hover:underline" onClick={() => void onDelete(row)}>
                  删除
                </button>
              </td>
            </tr>
          ))}
          {items.length === 0 && (
            <tr>
              <td colSpan={5} className="px-4 py-8 text-center text-ink-muted">
                暂无分类。可点击「新建分类」或执行后端 <code className="text-brand">python cli.py seed marketplace</code>
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

export function MarketplaceCategoryFormDialog({ vm }: { vm: MarketplaceCategoriesPageVm }) {
  const { dialogOpen, setDialogOpen, editing, name, setName, slug, setSlug, sortOrder, setSortOrder, msg, onSave } = vm;
  if (!dialogOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-md rounded-xl border border-line bg-surface p-6 shadow-panel">
        <h2 className="text-lg font-semibold text-ink">{editing ? "编辑分类" : "新建分类"}</h2>
        <div className="mt-4 space-y-3">
          <label className="block text-sm">
            <span className="mb-1 block text-ink-muted">名称</span>
            <input className="input-field w-full" value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-ink-muted">slug（可选，留空自动生成）</span>
            <input className="input-field w-full font-mono text-xs" value={slug} onChange={(e) => setSlug(e.target.value)} placeholder="rag" />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-ink-muted">排序</span>
            <input type="number" className="input-field w-full" value={sortOrder} onChange={(e) => setSortOrder(Number(e.target.value))} />
          </label>
          {msg ? <p className="text-sm text-red-600">{msg}</p> : null}
        </div>
        <div className="mt-6 flex justify-end gap-2">
          <button type="button" className="btn-ghost" onClick={() => setDialogOpen(false)}>
            取消
          </button>
          <button type="button" className="btn-primary" onClick={() => void onSave()}>
            保存
          </button>
        </div>
      </div>
    </div>
  );
}
