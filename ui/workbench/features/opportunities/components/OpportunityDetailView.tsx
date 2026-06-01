"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { useBizPermissions } from "@/features/business/lib/biz-permissions";
import { OPPORTUNITY_STAGES, OPPORTUNITY_STAGE_LABELS, QUOTE_STATUS_LABELS, stageBadgeClass } from "@/features/opportunities/lib/opportunity-labels";
import { api } from "@/lib/api";
import type { BizOpportunity, BizQuote, TenantUser } from "@/lib/types";

export function useOpportunityDetailPage(opportunityId: string | null, options?: { onMutated?: () => void }) {
  const router = useRouter();
  const onMutated = options?.onMutated;
  const [opp, setOpp] = useState<BizOpportunity | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [converting, setConverting] = useState(false);
  const [quotes, setQuotes] = useState<BizQuote[]>([]);
  const [quoteName, setQuoteName] = useState("");
  const [quoteAmount, setQuoteAmount] = useState("");
  const [quoteSaving, setQuoteSaving] = useState(false);
  const [editing, setEditing] = useState(false);
  const [savingEdit, setSavingEdit] = useState(false);
  const [users, setUsers] = useState<TenantUser[]>([]);
  const [editForm, setEditForm] = useState({
    stage: "",
    expected_value: "",
    probability: "",
    expected_close_date: "",
    owner_id: "",
    description: "",
  });

  const resetLocalState = useCallback(() => {
    setOpp(null);
    setError("");
    setQuotes([]);
    setQuoteName("");
    setQuoteAmount("");
    setEditing(false);
  }, []);

  const syncEditForm = useCallback((data: BizOpportunity) => {
    setEditForm({
      stage: data.stage,
      expected_value: data.expected_value != null ? String(data.expected_value) : "",
      probability: data.probability != null ? String(data.probability) : "",
      expected_close_date: data.expected_close_date ?? "",
      owner_id: data.owner_id ?? "",
      description: data.description ?? "",
    });
  }, []);

  const loadQuotes = useCallback(async () => {
    if (!opportunityId) return;
    const rows = await api.listQuotes(opportunityId);
    setQuotes(rows);
  }, [opportunityId]);

  const load = useCallback(async () => {
    if (!opportunityId) return null;
    const data = await api.getOpportunity(opportunityId);
    setOpp(data);
    syncEditForm(data);
    await loadQuotes();
    return data;
  }, [opportunityId, loadQuotes, syncEditForm]);

  useEffect(() => {
    if (!opportunityId) {
      resetLocalState();
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    load().catch((e) => setError(e?.message ?? "加载失败")).finally(() => setLoading(false));
  }, [opportunityId, load, resetLocalState]);

  useEffect(() => {
    if (!editing) return;
    void api.listUsers(1, 100).then((r) => setUsers(r.items));
  }, [editing]);

  const handleConvert = async () => {
    if (!opportunityId) return;
    setConverting(true);
    try {
      const result = await api.convertOpportunityToProject(opportunityId);
      onMutated?.();
      router.push(`/business/projects/${result.project_id}`);
    } finally {
      setConverting(false);
    }
  };

  const handleAddQuote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!opportunityId || !quoteName.trim()) return;
    setQuoteSaving(true);
    try {
      await api.createQuote(opportunityId, {
        name: quoteName.trim(),
        amount: quoteAmount ? Number(quoteAmount) : undefined,
      });
      setQuoteName("");
      setQuoteAmount("");
      await loadQuotes();
      onMutated?.();
    } finally {
      setQuoteSaving(false);
    }
  };

  const handleSaveEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!opportunityId) return;
    setSavingEdit(true);
    try {
      const updated = await api.updateOpportunity(opportunityId, {
        stage: editForm.stage,
        expected_value: editForm.expected_value ? Number(editForm.expected_value) : undefined,
        probability: editForm.probability ? Number(editForm.probability) : undefined,
        expected_close_date: editForm.expected_close_date || undefined,
        owner_id: editForm.owner_id || undefined,
        description: editForm.description.trim() || undefined,
      });
      setOpp(updated);
      syncEditForm(updated);
      setEditing(false);
      onMutated?.();
    } finally {
      setSavingEdit(false);
    }
  };

  const handleQuickStage = async (stage: string) => {
    if (!opportunityId || opp?.stage === stage) return;
    const updated = await api.updateOpportunity(opportunityId, { stage });
    setOpp(updated);
    syncEditForm(updated);
    onMutated?.();
  };

  const handleQuoteStatus = async (quoteId: string, status: string) => {
    if (!opportunityId) return;
    await api.updateQuote(opportunityId, quoteId, { status });
    await loadQuotes();
    onMutated?.();
  };

  const handleDeleteQuote = async (quoteId: string) => {
    if (!opportunityId || !window.confirm("确定删除该报价？")) return;
    await api.deleteQuote(opportunityId, quoteId);
    await loadQuotes();
    onMutated?.();
  };

  return {
    opp,
    loading,
    error,
    converting,
    handleConvert,
    reload: load,
    quotes,
    quoteName,
    setQuoteName,
    quoteAmount,
    setQuoteAmount,
    quoteSaving,
    handleAddQuote,
    editing,
    setEditing,
    editForm,
    setEditForm,
    savingEdit,
    users,
    handleSaveEdit,
    handleQuickStage,
    handleQuoteStatus,
    handleDeleteQuote,
  };
}

export type OpportunityDetailPageVm = ReturnType<typeof useOpportunityDetailPage>;

export function OpportunityDetailView({
  vm,
  embedded = false,
}: {
  vm: OpportunityDetailPageVm;
  embedded?: boolean;
  onClose?: () => void;
}) {
  const perms = useBizPermissions();
  const {
    opp,
    loading,
    error,
    converting,
    handleConvert,
    quotes,
    quoteName,
    setQuoteName,
    quoteAmount,
    setQuoteAmount,
    quoteSaving,
    handleAddQuote,
    editing,
    setEditing,
    editForm,
    setEditForm,
    savingEdit,
    users,
    handleSaveEdit,
    handleQuickStage,
    handleQuoteStatus,
    handleDeleteQuote,
  } = vm;

  if (loading) return <p className="text-sm text-ink-muted">加载中…</p>;
  if (error || !opp) return <p className="text-sm text-red-600">{error || "商机不存在"}</p>;

  const canConvert = opp.stage === "won" && !opp.converted_to_project_id;
  const canEdit = perms.canWriteOpportunity && !opp.converted_to_project_id;
  const closed = opp.stage === "won" || opp.stage === "lost";

  return (
    <div className={embedded ? "w-full" : undefined}>
      {!embedded ? (
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold text-ink">{opp.name}</h1>
            {opp.code && <p className="text-sm text-ink-muted">{opp.code}</p>}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className={`rounded px-2 py-0.5 text-xs ${stageBadgeClass(opp.stage)}`}>
              {OPPORTUNITY_STAGE_LABELS[opp.stage] ?? opp.stage}
            </span>
            {canEdit && canConvert && (
              <button type="button" className="btn-primary text-xs" disabled={converting} onClick={() => void handleConvert()}>
                {converting ? "转化中…" : "转为项目"}
              </button>
            )}
            {opp.converted_to_project_id && (
              <Link href={`/business/projects/${opp.converted_to_project_id}`} className="btn-sm-outline text-xs">查看项目</Link>
            )}
          </div>
        </div>
      ) : (
        <div className="mb-4 flex flex-wrap items-center justify-end gap-2">
          <span className={`rounded px-2 py-0.5 text-xs ${stageBadgeClass(opp.stage)}`}>
            {OPPORTUNITY_STAGE_LABELS[opp.stage] ?? opp.stage}
          </span>
          {canEdit && canConvert && (
            <button type="button" className="btn-primary text-xs" disabled={converting} onClick={() => void handleConvert()}>
              {converting ? "转化中…" : "转为项目"}
            </button>
          )}
          {opp.converted_to_project_id && (
            <Link href={`/business/projects/${opp.converted_to_project_id}`} className="btn-sm-outline text-xs">查看项目</Link>
          )}
        </div>
      )}

      {canEdit && !closed && (
        <div className="mt-4 flex flex-wrap gap-2">
          <button type="button" className="btn-sm-outline text-xs text-green-700" onClick={() => void handleQuickStage("won")}>标记赢单</button>
          <button type="button" className="btn-sm-outline text-xs text-red-600" onClick={() => void handleQuickStage("lost")}>标记丢单</button>
        </div>
      )}

      <section className={`${embedded ? "mt-4" : "mt-6"}`}>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-ink">商机信息</h2>
          {canEdit && !editing && (
            <button type="button" className="text-xs text-brand hover:underline" onClick={() => setEditing(true)}>编辑</button>
          )}
        </div>

        {editing ? (
          <form onSubmit={handleSaveEdit} className="card space-y-3 p-4">
            <label className="block">
              <span className="text-xs text-ink-muted">阶段</span>
              <select className="input-field mt-1 w-full text-sm" value={editForm.stage} onChange={(e) => setEditForm((f) => ({ ...f, stage: e.target.value }))}>
                {OPPORTUNITY_STAGES.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
              </select>
            </label>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="block">
                <span className="text-xs text-ink-muted">预估金额</span>
                <input type="number" className="input-field mt-1 w-full text-sm" value={editForm.expected_value} onChange={(e) => setEditForm((f) => ({ ...f, expected_value: e.target.value }))} />
              </label>
              <label className="block">
                <span className="text-xs text-ink-muted">赢单概率 (%)</span>
                <input type="number" min={0} max={100} className="input-field mt-1 w-full text-sm" value={editForm.probability} onChange={(e) => setEditForm((f) => ({ ...f, probability: e.target.value }))} />
              </label>
            </div>
            <label className="block">
              <span className="text-xs text-ink-muted">预计结单</span>
              <input type="date" className="input-field mt-1 w-full text-sm" value={editForm.expected_close_date} onChange={(e) => setEditForm((f) => ({ ...f, expected_close_date: e.target.value }))} />
            </label>
            <label className="block">
              <span className="text-xs text-ink-muted">负责人</span>
              <select className="input-field mt-1 w-full text-sm" value={editForm.owner_id} onChange={(e) => setEditForm((f) => ({ ...f, owner_id: e.target.value }))}>
                <option value="">— 未指定 —</option>
                {users.map((u) => <option key={u.id} value={u.id}>{u.username}</option>)}
              </select>
            </label>
            <label className="block">
              <span className="text-xs text-ink-muted">描述</span>
              <textarea className="input-field mt-1 w-full text-sm" rows={3} value={editForm.description} onChange={(e) => setEditForm((f) => ({ ...f, description: e.target.value }))} />
            </label>
            <div className="flex gap-2">
              <button type="submit" disabled={savingEdit} className="btn-primary text-sm">{savingEdit ? "保存中…" : "保存"}</button>
              <button type="button" className="btn-ghost text-sm" onClick={() => { setEditing(false); vm.reload(); }}>取消</button>
            </div>
          </form>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            <InfoCard label="预估金额" value={opp.expected_value != null ? `¥${opp.expected_value.toLocaleString()}` : "—"} />
            <InfoCard label="赢单概率" value={opp.probability != null ? `${opp.probability}%` : "—"} />
            <InfoCard label="预计结单" value={opp.expected_close_date || "—"} />
            <InfoCard label="描述" value={opp.description || "—"} className="sm:col-span-2" />
          </div>
        )}
      </section>

      <section className="mt-8">
        <h2 className="text-sm font-semibold text-ink">报价单</h2>
        {canEdit && (
          <form onSubmit={handleAddQuote} className="card mt-3 flex flex-wrap items-end gap-3 p-4">
            <label className="min-w-[10rem] flex-1">
              <span className="text-xs text-ink-muted">名称</span>
              <input className="input-field mt-1 w-full text-sm" value={quoteName} onChange={(e) => setQuoteName(e.target.value)} placeholder="如：V1 方案报价" required />
            </label>
            <label>
              <span className="text-xs text-ink-muted">金额</span>
              <input type="number" className="input-field mt-1 w-32 text-sm" value={quoteAmount} onChange={(e) => setQuoteAmount(e.target.value)} placeholder="可选" />
            </label>
            <button type="submit" disabled={quoteSaving || !quoteName.trim()} className="btn-primary text-sm">{quoteSaving ? "保存中…" : "新增报价"}</button>
          </form>
        )}
        {quotes.length === 0 ? (
          <p className="mt-3 text-sm text-ink-faint">暂无报价</p>
        ) : (
          <ul className="mt-3 space-y-2">
            {quotes.map((q) => (
              <li key={q.id} className="card flex flex-wrap items-center justify-between gap-2 p-3 text-sm">
                <div>
                  <span className="font-medium text-ink">{q.name}</span>
                  {q.version && <span className="ml-2 text-xs text-ink-muted">{q.version}</span>}
                </div>
                <div className="flex flex-wrap items-center gap-2 text-xs text-ink-muted">
                  {q.amount != null && <span>¥{q.amount.toLocaleString()}</span>}
                  <span className="rounded bg-surface-muted px-2 py-0.5">{QUOTE_STATUS_LABELS[q.status] ?? q.status}</span>
                  {q.valid_until && <span>有效期至 {q.valid_until}</span>}
                  {canEdit && q.status === "draft" && (
                    <>
                      <button type="button" className="text-brand hover:underline" onClick={() => void handleQuoteStatus(q.id, "sent")}>发送</button>
                      <button type="button" className="text-red-600 hover:underline" onClick={() => void handleDeleteQuote(q.id)}>删除</button>
                    </>
                  )}
                  {canEdit && q.status === "sent" && (
                    <>
                      <button type="button" className="text-green-700 hover:underline" onClick={() => void handleQuoteStatus(q.id, "accepted")}>采纳</button>
                      <button type="button" className="text-red-600 hover:underline" onClick={() => void handleQuoteStatus(q.id, "rejected")}>拒绝</button>
                    </>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function InfoCard({ label, value, className = "" }: { label: string; value: string; className?: string }) {
  return (
    <div className={`card p-4 ${className}`}>
      <p className="text-xs text-ink-faint">{label}</p>
      <p className="mt-1 text-sm font-medium text-ink">{value}</p>
    </div>
  );
}
