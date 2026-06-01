"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { BizProjectSupplier, BizSupplier } from "@/lib/types";
import { PROJECT_SUPPLIER_STATUS_LABELS, SUPPLIER_CATEGORY_LABELS } from "@/features/suppliers/lib/supplier-labels";
import type { ProjectDetailPageVm } from "@/features/projects/hooks/use-project-detail-page";

export function ProjectSuppliersTab({ vm }: { vm: ProjectDetailPageVm }) {
  const { project, projectId } = vm;
  const [rows, setRows] = useState<BizProjectSupplier[]>([]);
  const [suppliers, setSuppliers] = useState<BizSupplier[]>([]);
  const [supplierId, setSupplierId] = useState("");
  const [role, setRole] = useState("");
  const [amount, setAmount] = useState("");
  const [saving, setSaving] = useState(false);

  const load = async () => {
    const [ps, all] = await Promise.all([
      api.listProjectSuppliers(projectId),
      api.listSuppliers(1, 100),
    ]);
    setRows(ps);
    setSuppliers(all.items);
  };

  useEffect(() => {
    void load();
  }, [projectId]);

  if (!project) return null;

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!supplierId) return;
    setSaving(true);
    try {
      await api.addProjectSupplier(projectId, {
        supplier_id: supplierId,
        role_description: role.trim() || undefined,
        contracted_amount: amount ? Number(amount) : undefined,
      });
      setSupplierId("");
      setRole("");
      setAmount("");
      await load();
    } finally {
      setSaving(false);
    }
  };

  const handleRemove = async (sid: string) => {
    if (!window.confirm("确定移除此供应商？")) return;
    await api.removeProjectSupplier(projectId, sid);
    await load();
  };

  const linkedIds = new Set(rows.map((r) => r.supplier_id));
  const available = suppliers.filter((s) => !linkedIds.has(s.id) && s.status === "active");

  return (
    <div className="mt-4 space-y-4">
      <form onSubmit={handleAdd} className="card flex flex-wrap items-end gap-3 p-4">
        <label className="min-w-[12rem] flex-1">
          <span className="text-xs text-ink-muted">供应商</span>
          <select className="input-field mt-1 w-full text-sm" value={supplierId} onChange={(e) => setSupplierId(e.target.value)} required>
            <option value="">— 请选择 —</option>
            {available.map((s) => (
              <option key={s.id} value={s.id}>{s.name}（{SUPPLIER_CATEGORY_LABELS[s.category] ?? s.category}）</option>
            ))}
          </select>
        </label>
        <label className="min-w-[10rem]">
          <span className="text-xs text-ink-muted">分工说明</span>
          <input className="input-field mt-1 w-full text-sm" value={role} onChange={(e) => setRole(e.target.value)} placeholder="如：展台搭建" />
        </label>
        <label>
          <span className="text-xs text-ink-muted">合同金额</span>
          <input type="number" className="input-field mt-1 w-32 text-sm" value={amount} onChange={(e) => setAmount(e.target.value)} />
        </label>
        <button type="submit" disabled={saving || !supplierId} className="btn-primary text-sm">{saving ? "添加中…" : "关联供应商"}</button>
      </form>

      {rows.length === 0 ? (
        <p className="text-sm text-ink-faint">暂无关联供应商</p>
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b border-line bg-surface-muted text-xs text-ink-muted">
              <tr>
                <th className="px-4 py-2 text-left">供应商</th>
                <th className="px-4 py-2 text-left">类型</th>
                <th className="px-4 py-2 text-left">分工</th>
                <th className="px-4 py-2 text-left">合同金额</th>
                <th className="px-4 py-2 text-left">状态</th>
                <th className="px-4 py-2 text-right">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line-soft">
              {rows.map((r) => (
                <tr key={r.supplier_id}>
                  <td className="px-4 py-3">
                    <Link href={`/business/suppliers?id=${r.supplier_id}`} className="text-brand hover:underline">{r.supplier_name}</Link>
                  </td>
                  <td className="px-4 py-3 text-ink-muted">{SUPPLIER_CATEGORY_LABELS[r.supplier_category] ?? r.supplier_category}</td>
                  <td className="px-4 py-3">{r.role_description || "—"}</td>
                  <td className="px-4 py-3">{r.contracted_amount != null ? `¥${r.contracted_amount.toLocaleString()}` : "—"}</td>
                  <td className="px-4 py-3">{PROJECT_SUPPLIER_STATUS_LABELS[r.status] ?? r.status}</td>
                  <td className="px-4 py-3 text-right">
                    <button type="button" className="text-xs text-red-600 hover:underline" onClick={() => void handleRemove(r.supplier_id)}>移除</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
