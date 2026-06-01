"use client";

import type { SupplierDetailPageVm } from "@/features/suppliers/hooks/use-supplier-detail-page";
import { SUPPLIER_CATEGORY_LABELS, SUPPLIER_STATUS_LABELS, supplierStatusBadgeClass } from "@/features/suppliers/lib/supplier-labels";

export function SupplierDetailView({
  vm,
  embedded = false,
}: {
  vm: SupplierDetailPageVm;
  embedded?: boolean;
  onClose?: () => void;
}) {
  const {
    supplier, loading, error, tab, handleTabChange,
    contactForm, setContactForm,
    editingContactId, savingContact, resetContactForm, startEditContact,
    handleContactSubmit, handleDeleteContact,
  } = vm;

  if (loading) return <p className="text-sm text-ink-muted">加载中…</p>;
  if (error || !supplier) return <p className="text-sm text-red-600">{error || "供应商不存在"}</p>;

  return (
    <div className={embedded ? "w-full" : "mx-auto max-w-2xl"}>
      {!embedded ? (
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-xl font-semibold text-ink">{supplier.name}</h1>
            {supplier.short_name && <p className="text-sm text-ink-muted">{supplier.short_name}</p>}
          </div>
          <span className={`rounded px-2 py-0.5 text-xs ${supplierStatusBadgeClass(supplier.status)}`}>
            {SUPPLIER_STATUS_LABELS[supplier.status] ?? supplier.status}
          </span>
        </div>
      ) : (
        <div className="mb-4 flex justify-end">
          <span className={`rounded px-2 py-0.5 text-xs ${supplierStatusBadgeClass(supplier.status)}`}>
            {SUPPLIER_STATUS_LABELS[supplier.status] ?? supplier.status}
          </span>
        </div>
      )}

      {!embedded && (
        <div className="mt-6 flex gap-1 border-b border-line">
          {(["info", "contacts"] as const).map((t) => (
            <button
              key={t}
              type="button"
              className={`px-4 py-2 text-sm font-medium transition ${tab === t ? "-mb-px border-b-2 border-brand text-brand" : "text-ink-muted hover:text-ink"}`}
              onClick={() => handleTabChange(t)}
            >
              {t === "info" ? "基本信息" : `联系人 (${supplier.contacts.length})`}
            </button>
          ))}
        </div>
      )}

      {(embedded || tab === "info") && (
      <div className={`grid gap-4 sm:grid-cols-2 ${embedded ? "mt-0" : "mt-6"}`}>
        <InfoCard label="类型" value={SUPPLIER_CATEGORY_LABELS[supplier.category] ?? supplier.category} />
        <InfoCard label="合作项目" value={`${supplier.project_count}`} />
        <InfoCard label="主联系人" value={supplier.contact_name || "—"} />
        <InfoCard label="联系电话" value={supplier.contact_phone || "—"} />
        <InfoCard label="邮箱" value={supplier.contact_email || "—"} />
        <InfoCard label="地址" value={supplier.address || "—"} />
        <InfoCard label="开户行" value={supplier.bank_name || "—"} />
        <InfoCard label="银行账号" value={supplier.bank_account || "—"} />
        <InfoCard label="备注" value={supplier.remark || "—"} className="sm:col-span-2" />
      </div>
      )}

      {(embedded || tab === "contacts") && (
      <div className={`${tab === "contacts" && !embedded ? "mt-4" : "mt-8"}`}>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-ink">联系人</h2>
          {editingContactId ? (
            <button type="button" className="text-xs text-ink-muted hover:underline" onClick={resetContactForm}>取消编辑</button>
          ) : null}
        </div>

        <form onSubmit={handleContactSubmit} className="card mb-4 space-y-3 p-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="sm:col-span-2">
              <span className="text-xs text-ink-muted">姓名 <span className="text-red-500">*</span></span>
              <input className="input-field mt-1 w-full text-sm" value={contactForm.name} onChange={(e) => setContactForm({ ...contactForm, name: e.target.value })} required />
            </label>
            <label>
              <span className="text-xs text-ink-muted">职位</span>
              <input className="input-field mt-1 w-full text-sm" value={contactForm.title} onChange={(e) => setContactForm({ ...contactForm, title: e.target.value })} />
            </label>
            <label>
              <span className="text-xs text-ink-muted">手机</span>
              <input className="input-field mt-1 w-full text-sm" value={contactForm.phone} onChange={(e) => setContactForm({ ...contactForm, phone: e.target.value })} />
            </label>
            <label className="sm:col-span-2">
              <span className="text-xs text-ink-muted">邮箱</span>
              <input type="email" className="input-field mt-1 w-full text-sm" value={contactForm.email} onChange={(e) => setContactForm({ ...contactForm, email: e.target.value })} />
            </label>
          </div>
          <label className="flex items-center gap-2 text-sm text-ink">
            <input type="checkbox" checked={contactForm.is_primary} onChange={(e) => setContactForm({ ...contactForm, is_primary: e.target.checked })} />
            设为主联系人
          </label>
          <button type="submit" disabled={savingContact || !contactForm.name.trim()} className="btn-primary text-sm">
            {savingContact ? "保存中…" : editingContactId ? "更新联系人" : "添加联系人"}
          </button>
        </form>

        {supplier.contacts.length === 0 ? (
          <p className="text-sm text-ink-faint">暂无额外联系人</p>
        ) : (
          <ul className="space-y-2">
            {supplier.contacts.map((c) => (
              <li key={c.id} className="card flex items-center justify-between p-3 text-sm">
                <div>
                  <span className="font-medium text-ink">{c.name}</span>
                  {c.is_primary && <span className="ml-2 rounded bg-brand-light px-1.5 py-0.5 text-xs text-brand">主</span>}
                  <p className="text-xs text-ink-muted">{[c.title, c.phone, c.email].filter(Boolean).join(" · ") || "—"}</p>
                </div>
                <div className="flex gap-2">
                  <button type="button" className="text-xs text-brand hover:underline" onClick={() => startEditContact(c)}>编辑</button>
                  <button type="button" className="text-xs text-red-600 hover:underline" onClick={() => void handleDeleteContact(c.id)}>删除</button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
      )}
    </div>
  );
}

function InfoCard({ label, value, className = "" }: { label: string; value: string; className?: string }) {
  return (
    <div className={`card p-4 ${className}`}>
      <p className="text-xs text-ink-faint">{label}</p>
      <p className="mt-1 text-sm text-ink">{value}</p>
    </div>
  );
}
