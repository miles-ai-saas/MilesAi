"use client";

import { useCallback, useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { adminApi, type AdminSysCategory } from "@/lib/api";
import { useRequireAdmin } from "@/lib/auth-store";

const DOMAINS = [
  { key: "agent", label: "智能体" },
  { key: "prompt", label: "提示词" },
  { key: "skill", label: "技能包" },
  { key: "tool", label: "工具" },
] as const;

type DomainKey = (typeof DOMAINS)[number]["key"];

export default function SysCategoriesPage() {
  const ready = useRequireAdmin();
  const [domain, setDomain] = useState<DomainKey>("agent");
  const [items, setItems] = useState<AdminSysCategory[]>([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<AdminSysCategory | null>(null);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [sortOrder, setSortOrder] = useState(0);
  const [msg, setMsg] = useState("");

  const reload = useCallback(async () => {
    setItems(await adminApi.listSysCategories(domain));
  }, [domain]);

  useEffect(() => {
    if (!ready) return;
    void reload();
  }, [ready, reload]);

  const openCreate = () => {
    setEditing(null);
    setName("");
    setSlug("");
    setSortOrder((items.length + 1) * 10);
    setMsg("");
    setDialogOpen(true);
  };

  const openEdit = (row: AdminSysCategory) => {
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
        await adminApi.updateSysCategory(editing.id, {
          name: name.trim(),
          slug: slug.trim() || undefined,
          sort_order: sortOrder,
        });
      } else {
        await adminApi.createSysCategory(domain, {
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

  const onDelete = async (row: AdminSysCategory) => {
    if (!confirm(`确定删除分类「${row.name}」？全租户工作台将不可再选此项。`)) return;
    try {
      await adminApi.deleteSysCategory(row.id);
      await reload();
    } catch (e) {
      alert(e instanceof Error ? e.message : "删除失败");
    }
  };

  return (
    <div>
      <PageHeader
        title="工作台分类"
        description="全平台全局 sys_categories，各租户共用；租户不可增删改，个性化请用标签。"
        action={
          <button type="button" className="btn-primary" onClick={openCreate}>
            新建分类
          </button>
        }
      />

      <div className="mb-4 flex flex-wrap gap-2 border-b border-line pb-3">
        {DOMAINS.map((d) => (
          <button
            key={d.key}
            type="button"
            onClick={() => setDomain(d.key)}
            className={`rounded-lg px-3 py-1.5 text-sm ${domain === d.key ? "bg-brand-light font-medium text-brand" : "text-ink-muted hover:bg-surface-muted"}`}
          >
            {d.label}
          </button>
        ))}
      </div>

      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead>
            <tr>
              <th>名称</th>
              <th>slug</th>
              <th className="col-center col-numeric">排序</th>
              <th className="col-actions">操作</th>
            </tr>
          </thead>
          <tbody>
            {items.map((row) => (
              <tr key={row.id}>
                <td className="cell-primary">{row.name}</td>
                <td className="cell-mono">{row.slug}</td>
                <td className="col-center col-numeric cell-numeric">{row.sort_order}</td>
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
                <td colSpan={4} className="px-4 py-8 text-center text-ink-muted">
                  暂无分类，请新建或执行 seed categories
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {dialogOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-xl border border-line bg-surface p-6 shadow-panel">
            <h2 className="text-lg font-semibold">{editing ? "编辑分类" : "新建分类"}</h2>
            <p className="mt-1 text-xs text-ink-muted">域：{DOMAINS.find((d) => d.key === domain)?.label}</p>
            <div className="mt-4 space-y-3">
              <label className="block text-sm">
                <span className="mb-1 block text-ink-muted">名称</span>
                <input className="input-field w-full" value={name} onChange={(e) => setName(e.target.value)} />
              </label>
              <label className="block text-sm">
                <span className="mb-1 block text-ink-muted">slug</span>
                <input className="input-field w-full font-mono text-xs" value={slug} onChange={(e) => setSlug(e.target.value)} />
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
      )}
    </div>
  );
}
