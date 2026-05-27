"use client";

import { useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { adminApi, type AdminMarketplaceCategory } from "@/lib/api";
import { useRequireAdmin } from "@/lib/auth-store";

export default function MarketplaceCategoriesPage() {
  const ready = useRequireAdmin();
  const [items, setItems] = useState<AdminMarketplaceCategory[]>([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<AdminMarketplaceCategory | null>(null);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [sortOrder, setSortOrder] = useState(0);
  const [msg, setMsg] = useState("");

  const reload = async () => {
    setItems(await adminApi.listMarketplaceCategories());
  };

  useEffect(() => {
    if (!ready) return;
    void reload();
  }, [ready]);

  const openCreate = () => {
    setEditing(null);
    setName("");
    setSlug("");
    setSortOrder((items.length + 1) * 10);
    setMsg("");
    setDialogOpen(true);
  };

  const openEdit = (row: AdminMarketplaceCategory) => {
    setEditing(row);
    setName(row.name);
    setSlug(row.slug);
    setSortOrder(row.sort_order);
    setMsg("");
    setDialogOpen(true);
  };

  const onSave = async () => {
    if (!name.trim()) return;
    setMsg("");
    try {
      if (editing) {
        await adminApi.updateMarketplaceCategory(editing.id, {
          name: name.trim(),
          slug: slug.trim() || undefined,
          sort_order: sortOrder,
        });
      } else {
        await adminApi.createMarketplaceCategory({
          name: name.trim(),
          slug: slug.trim() || undefined,
          sort_order: sortOrder,
        });
      }
      setDialogOpen(false);
      await reload();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "保存失败");
    }
  };

  const onDelete = async (row: AdminMarketplaceCategory) => {
    if (!confirm(`确定删除分类「${row.name}」？`)) return;
    try {
      await adminApi.deleteMarketplaceCategory(row.id);
      await reload();
    } catch (e) {
      alert(e instanceof Error ? e.message : "删除失败");
    }
  };

  return (
    <div>
      <PageHeader
        title="应用市场分类"
        description="平台级 mkt_categories，供租户应用市场 Tab 筛选与上架应用归类。"
        action={
          <button type="button" className="btn-primary" onClick={openCreate}>
            新建分类
          </button>
        }
      />

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
                  <button
                    type="button"
                    className="text-brand hover:underline"
                    onClick={() => openEdit(row)}
                  >
                    编辑
                  </button>
                  <button
                    type="button"
                    className="text-red-600 hover:underline"
                    onClick={() => void onDelete(row)}
                  >
                    删除
                  </button>
                </td>
              </tr>
            ))}
            {items.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-ink-muted">
                  暂无分类。可点击「新建分类」或执行后端{" "}
                  <code className="text-brand">python cli.py seed marketplace</code>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {dialogOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-xl border border-line bg-surface p-6 shadow-panel">
            <h2 className="text-lg font-semibold text-ink">
              {editing ? "编辑分类" : "新建分类"}
            </h2>
            <div className="mt-4 space-y-3">
              <label className="block text-sm">
                <span className="mb-1 block text-ink-muted">名称</span>
                <input
                  className="input-field w-full"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </label>
              <label className="block text-sm">
                <span className="mb-1 block text-ink-muted">slug（可选，留空自动生成）</span>
                <input
                  className="input-field w-full font-mono text-xs"
                  value={slug}
                  onChange={(e) => setSlug(e.target.value)}
                  placeholder="rag"
                />
              </label>
              <label className="block text-sm">
                <span className="mb-1 block text-ink-muted">排序</span>
                <input
                  type="number"
                  className="input-field w-full"
                  value={sortOrder}
                  onChange={(e) => setSortOrder(Number(e.target.value))}
                />
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
      )}
    </div>
  );
}
