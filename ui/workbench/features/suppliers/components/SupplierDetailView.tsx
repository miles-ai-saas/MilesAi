"use client";

import type { FormEvent, ReactNode } from "react";
import type { SupplierDetailPageVm } from "@/features/suppliers/hooks/use-supplier-detail-page";
import {
  SUPPLIER_CATEGORY_LABELS,
  SUPPLIER_STATUS_LABELS,
  supplierStatusBadgeClass,
} from "@/features/suppliers/lib/supplier-labels";
import type { BizSupplier, BizSupplierContact } from "@/lib/types";

export function SupplierDetailView({
  vm,
  embedded = false,
}: {
  vm: SupplierDetailPageVm;
  embedded?: boolean;
  onClose?: () => void;
}) {
  const {
    supplier,
    loading,
    error,
    tab,
    handleTabChange,
    contactForm,
    setContactForm,
    editingContactId,
    savingContact,
    resetContactForm,
    startEditContact,
    handleContactSubmit,
    handleDeleteContact,
  } = vm;

  if (loading) return <p className="text-sm text-ink-muted">加载中…</p>;
  if (error || !supplier) return <p className="text-sm text-red-600">{error || "供应商不存在"}</p>;

  const categoryLabel = SUPPLIER_CATEGORY_LABELS[supplier.category] ?? supplier.category;
  const statusLabel = SUPPLIER_STATUS_LABELS[supplier.status] ?? supplier.status;

  return (
    <div className="w-full">
      {!embedded ? (
        <header className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-xl font-semibold tracking-tight text-ink">{supplier.name}</h1>
              <span className={`rounded-md px-2 py-0.5 text-xs font-medium ${supplierStatusBadgeClass(supplier.status)}`}>
                {statusLabel}
              </span>
            </div>
            <p className="mt-1 text-sm text-ink-muted">
              {[supplier.short_name, categoryLabel].filter(Boolean).join(" · ")}
            </p>
          </div>
          <div className="flex shrink-0 gap-2">
            <MetaPill label="合作项目" value={String(supplier.project_count)} />
            <MetaPill label="联系人" value={String(supplier.contacts.length)} />
          </div>
        </header>
      ) : (
        <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
          <span className="text-xs text-ink-muted">{categoryLabel}</span>
          <span className={`rounded-md px-2 py-0.5 text-xs font-medium ${supplierStatusBadgeClass(supplier.status)}`}>
            {statusLabel}
          </span>
        </div>
      )}

      {!embedded ? (
        <nav className="mt-6 flex gap-1 border-b border-line" aria-label="供应商详情分区">
          {(["info", "contacts"] as const).map((t) => (
            <button
              key={t}
              type="button"
              className={`px-4 py-2.5 text-sm font-medium transition ${
                tab === t ? "-mb-px border-b-2 border-brand text-brand" : "text-ink-muted hover:text-ink"
              }`}
              onClick={() => handleTabChange(t)}
            >
              {t === "info" ? "基本信息" : `联系人 (${supplier.contacts.length})`}
            </button>
          ))}
        </nav>
      ) : null}

      {embedded || tab === "info" ? <SupplierInfoPanel supplier={supplier} embedded={embedded} /> : null}

      {embedded || tab === "contacts" ? (
        <div className={embedded ? "mt-6 border-t border-line pt-6" : undefined}>
          {embedded ? (
            <h2 className="mb-4 text-sm font-semibold text-ink">联系人 ({supplier.contacts.length})</h2>
          ) : null}
          <SupplierContactsPanel
            contacts={supplier.contacts}
            embedded={embedded}
            contactForm={contactForm}
            setContactForm={setContactForm}
            editingContactId={editingContactId}
            savingContact={savingContact}
            resetContactForm={resetContactForm}
            startEditContact={startEditContact}
            handleContactSubmit={handleContactSubmit}
            handleDeleteContact={handleDeleteContact}
          />
        </div>
      ) : null}
    </div>
  );
}

function MetaPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-line bg-surface-muted/60 px-3 py-2 text-center min-w-[4.5rem]">
      <p className="text-[11px] text-ink-faint">{label}</p>
      <p className="mt-0.5 text-sm font-semibold tabular-nums text-ink">{value}</p>
    </div>
  );
}

function SupplierInfoPanel({ supplier, embedded }: { supplier: BizSupplier; embedded?: boolean }) {
  return (
    <div className={`space-y-4 ${embedded ? "mt-3" : "mt-6"}`}>
      <section className="card overflow-hidden">
        <SectionTitle>概览</SectionTitle>
        <dl className="grid gap-px bg-line sm:grid-cols-2">
          <Field label="供应商类型" value={SUPPLIER_CATEGORY_LABELS[supplier.category] ?? supplier.category} />
          <Field label="合作状态" value={SUPPLIER_STATUS_LABELS[supplier.status] ?? supplier.status} />
          <Field label="合作项目数" value={`${supplier.project_count}`} />
          <Field label="简称" value={supplier.short_name || "—"} />
        </dl>
      </section>

      <section className="card overflow-hidden">
        <SectionTitle>默认联系方式</SectionTitle>
        <dl className="grid gap-px bg-line sm:grid-cols-2">
          <Field label="主联系人" value={supplier.contact_name || "—"} />
          <Field label="联系电话" value={supplier.contact_phone || "—"} mono />
          <Field label="邮箱" value={supplier.contact_email || "—"} mono />
          <Field label="地址" value={supplier.address || "—"} />
        </dl>
      </section>

      <section className="card overflow-hidden">
        <SectionTitle>结算信息</SectionTitle>
        <dl className="grid gap-px bg-line sm:grid-cols-2">
          <Field label="开户行" value={supplier.bank_name || "—"} />
          <Field label="银行账号" value={supplier.bank_account || "—"} mono />
        </dl>
      </section>

      {supplier.remark ? (
        <section className="card p-4">
          <p className="text-xs font-medium text-ink-faint">备注</p>
          <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-ink">{supplier.remark}</p>
        </section>
      ) : null}
    </div>
  );
}

function SectionTitle({ children }: { children: ReactNode }) {
  return (
    <div className="border-b border-line bg-surface-muted/40 px-4 py-2.5">
      <h2 className="text-xs font-semibold tracking-wide text-ink-muted">{children}</h2>
    </div>
  );
}

function Field({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="bg-surface px-4 py-3">
      <dt className="text-[11px] text-ink-faint">{label}</dt>
      <dd className={`mt-1 text-sm text-ink ${mono ? "font-mono text-[13px] tracking-tight" : ""}`}>{value}</dd>
    </div>
  );
}

function SupplierContactsPanel({
  contacts,
  embedded,
  contactForm,
  setContactForm,
  editingContactId,
  savingContact,
  resetContactForm,
  startEditContact,
  handleContactSubmit,
  handleDeleteContact,
}: {
  contacts: BizSupplierContact[];
  embedded?: boolean;
  contactForm: SupplierDetailPageVm["contactForm"];
  setContactForm: SupplierDetailPageVm["setContactForm"];
  editingContactId: string | null;
  savingContact: boolean;
  resetContactForm: () => void;
  startEditContact: (c: BizSupplierContact) => void;
  handleContactSubmit: (e: FormEvent) => void;
  handleDeleteContact: (id: string) => void;
}) {
  return (
    <div className={`space-y-4 ${embedded ? "mt-0" : "mt-6"}`}>
      <form onSubmit={handleContactSubmit} className="card space-y-4 p-4 sm:p-5">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-sm font-semibold text-ink">{editingContactId ? "编辑联系人" : "添加联系人"}</h2>
          {editingContactId ? (
            <button type="button" className="text-xs text-ink-muted hover:text-ink hover:underline" onClick={resetContactForm}>
              取消编辑
            </button>
          ) : null}
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block sm:col-span-2">
            <span className="text-xs text-ink-muted">
              姓名 <span className="text-red-500">*</span>
            </span>
            <input
              className="input-field mt-1 w-full text-sm"
              value={contactForm.name}
              onChange={(e) => setContactForm({ ...contactForm, name: e.target.value })}
              required
            />
          </label>
          <label className="block">
            <span className="text-xs text-ink-muted">职位</span>
            <input
              className="input-field mt-1 w-full text-sm"
              value={contactForm.title}
              onChange={(e) => setContactForm({ ...contactForm, title: e.target.value })}
            />
          </label>
          <label className="block">
            <span className="text-xs text-ink-muted">手机</span>
            <input
              className="input-field mt-1 w-full text-sm"
              value={contactForm.phone}
              onChange={(e) => setContactForm({ ...contactForm, phone: e.target.value })}
            />
          </label>
          <label className="block sm:col-span-2">
            <span className="text-xs text-ink-muted">邮箱</span>
            <input
              type="email"
              className="input-field mt-1 w-full text-sm"
              value={contactForm.email}
              onChange={(e) => setContactForm({ ...contactForm, email: e.target.value })}
            />
          </label>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <label className="flex items-center gap-2 text-sm text-ink">
            <input
              type="checkbox"
              checked={contactForm.is_primary}
              onChange={(e) => setContactForm({ ...contactForm, is_primary: e.target.checked })}
            />
            设为主联系人
          </label>
          <button type="submit" disabled={savingContact || !contactForm.name.trim()} className="btn-primary text-sm">
            {savingContact ? "保存中…" : editingContactId ? "更新联系人" : "添加联系人"}
          </button>
        </div>
      </form>

      {contacts.length === 0 ? (
        <div className="rounded-xl border border-dashed border-line px-4 py-10 text-center">
          <p className="text-sm text-ink-muted">暂无联系人</p>
          <p className="mt-1 text-xs text-ink-faint">添加后可在此管理多人联系方式</p>
        </div>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2">
          {contacts.map((c) => (
            <li key={c.id} className="card flex gap-3 p-4">
              <div
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand-light text-sm font-semibold text-brand"
                aria-hidden
              >
                {c.name.slice(0, 1)}
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="truncate text-sm font-medium text-ink">{c.name}</p>
                  {c.is_primary ? (
                    <span className="rounded bg-brand-light px-1.5 py-0.5 text-[10px] font-medium text-brand">主联系人</span>
                  ) : null}
                </div>
                <p className="mt-0.5 truncate text-xs text-ink-muted">
                  {[c.title, c.phone, c.email].filter(Boolean).join(" · ") || "暂无联系方式"}
                </p>
                <div className="mt-3 flex gap-3">
                  <button type="button" className="text-xs font-medium text-brand hover:underline" onClick={() => startEditContact(c)}>
                    编辑
                  </button>
                  <button
                    type="button"
                    className="text-xs font-medium text-red-600 hover:underline"
                    onClick={() => void handleDeleteContact(c.id)}
                  >
                    删除
                  </button>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
