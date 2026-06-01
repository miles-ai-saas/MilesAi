"use client";

import Link from "next/link";
import type { ClientDetailPageVm } from "@/features/clients/hooks/use-client-detail-page";
import { PROJECT_STATUS_LABELS } from "@/features/projects/lib/biz-labels";

const INDUSTRY_LABELS: Record<string, string> = {
  government: "政府机关", enterprise: "企业", park: "园区",
  commercial: "商业综合体", tourism: "文旅", other: "其他",
};
const CONF_LABELS: Record<string, string> = {
  normal: "普通", internal: "内部", restricted: "涉密",
};

export function ClientDetailView({ vm }: { vm: ClientDetailPageVm }) {
  const {
    router, client, projects, loading, error, contactForm, setContactForm,
    editingContactId, savingContact, resetContactForm, startEditContact,
    handleContactSubmit, handleDeleteContact,
    editingClient, setEditingClient, clientForm, setClientForm,
    savingClient, handleClientSubmit,
  } = vm;

  if (loading) return <p className="text-sm text-ink-muted">加载中…</p>;
  if (error || !client) return <p className="text-sm text-red-600">{error || "客户不存在"}</p>;

  return (
    <div className="mx-auto max-w-2xl">
      <button type="button" onClick={() => router.back()} className="mb-4 text-xs text-brand hover:underline">← 返回客户列表</button>

      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-ink">{client.name}</h1>
          {client.short_name && <p className="text-sm text-ink-muted">{client.short_name}</p>}
        </div>
        <div className="flex items-center gap-2">
          <span className={`rounded px-2 py-0.5 text-xs ${
            client.confidentiality_level === "restricted" ? "bg-red-50 text-red-600" :
            client.confidentiality_level === "internal" ? "bg-yellow-50 text-yellow-700" :
            "bg-surface-muted text-ink-muted"
          }`}>
            {CONF_LABELS[client.confidentiality_level] ?? client.confidentiality_level}
          </span>
          {!editingClient && (
            <button type="button" className="text-xs text-brand hover:underline" onClick={() => setEditingClient(true)}>编辑</button>
          )}
        </div>
      </div>

      {editingClient ? (
        <form onSubmit={handleClientSubmit} className="card mt-6 space-y-3 p-4">
          <label>
            <span className="text-xs text-ink-muted">名称 <span className="text-red-500">*</span></span>
            <input className="input-field mt-1 w-full text-sm" value={clientForm.name} onChange={(e) => setClientForm({ ...clientForm, name: e.target.value })} required />
          </label>
          <label>
            <span className="text-xs text-ink-muted">简称</span>
            <input className="input-field mt-1 w-full text-sm" value={clientForm.short_name} onChange={(e) => setClientForm({ ...clientForm, short_name: e.target.value })} />
          </label>
          <div className="grid gap-3 sm:grid-cols-2">
            <label>
              <span className="text-xs text-ink-muted">行业</span>
              <select className="input-field mt-1 w-full text-sm" value={clientForm.industry} onChange={(e) => setClientForm({ ...clientForm, industry: e.target.value })}>
                {Object.entries(INDUSTRY_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </label>
            <label>
              <span className="text-xs text-ink-muted">保密级别</span>
              <select className="input-field mt-1 w-full text-sm" value={clientForm.confidentiality_level} onChange={(e) => setClientForm({ ...clientForm, confidentiality_level: e.target.value })}>
                {Object.entries(CONF_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </label>
          </div>
          <label>
            <span className="text-xs text-ink-muted">地址</span>
            <input className="input-field mt-1 w-full text-sm" value={clientForm.address} onChange={(e) => setClientForm({ ...clientForm, address: e.target.value })} />
          </label>
          <label>
            <span className="text-xs text-ink-muted">备注</span>
            <textarea className="input-field mt-1 w-full text-sm" rows={2} value={clientForm.remark} onChange={(e) => setClientForm({ ...clientForm, remark: e.target.value })} />
          </label>
          <div className="flex gap-2">
            <button type="submit" disabled={savingClient || !clientForm.name.trim()} className="btn-primary text-sm">
              {savingClient ? "保存中…" : "保存"}
            </button>
            <button type="button" className="btn-sm-outline text-sm" onClick={() => setEditingClient(false)}>取消</button>
          </div>
        </form>
      ) : (
        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          <InfoCard label="行业" value={INDUSTRY_LABELS[client.industry ?? ""] ?? client.industry ?? "—"} />
          <InfoCard label="项目数" value={`${client.project_count}`} />
          <InfoCard label="地址" value={client.address || "—"} />
          <InfoCard label="备注" value={client.remark || "—"} />
        </div>
      )}

      <div className="mt-8">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-ink">历史项目</h2>
          <Link href={`/business/projects?client_id=${client.id}`} className="text-xs text-brand hover:underline">查看全部</Link>
        </div>
        {projects.length === 0 ? (
          <p className="text-sm text-ink-faint">暂无项目</p>
        ) : (
          <div className="space-y-2">
            {projects.map((p) => (
              <Link key={p.id} href={`/business/projects/${p.id}`} className="card flex items-center justify-between p-3 transition hover:shadow-md">
                <div>
                  <p className="text-sm font-medium text-ink">{p.name}</p>
                  {p.code && <p className="text-xs text-ink-muted">{p.code}</p>}
                </div>
                <span className="rounded bg-surface-muted px-2 py-0.5 text-xs text-ink-muted">
                  {PROJECT_STATUS_LABELS[p.status] ?? p.status}
                </span>
              </Link>
            ))}
          </div>
        )}
      </div>

      <div className="mt-8">
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

        {client.contacts.length === 0 ? (
          <p className="text-sm text-ink-faint">暂无联系人</p>
        ) : (
          <div className="space-y-2">
            {client.contacts.map((c) => (
              <div key={c.id} className="card flex items-start justify-between p-3 text-sm">
                <div>
                  <span className="font-medium text-ink">{c.name}</span>
                  {c.is_primary && <span className="ml-2 rounded bg-brand-light px-1.5 py-0.5 text-xs text-brand">主联系人</span>}
                  {c.title && <span className="ml-2 text-ink-muted">{c.title}</span>}
                  <div className="mt-1 text-xs text-ink-faint">
                    {c.phone && <span className="mr-3">{c.phone}</span>}
                    {c.email && <span>{c.email}</span>}
                  </div>
                </div>
                <div className="flex shrink-0 gap-2">
                  <button type="button" className="text-xs text-brand hover:underline" onClick={() => startEditContact(c)}>编辑</button>
                  <button type="button" className="text-xs text-red-600 hover:underline" onClick={() => void handleDeleteContact(c.id)}>删除</button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function InfoCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="card p-4">
      <p className="text-xs text-ink-faint">{label}</p>
      <p className="mt-1 text-sm text-ink">{value}</p>
    </div>
  );
}
