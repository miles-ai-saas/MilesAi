"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { BizOpportunity, BizQuote } from "@/lib/types";
import { OPPORTUNITY_STAGE_LABELS, QUOTE_STATUS_LABELS, stageBadgeClass } from "@/features/opportunities/lib/opportunity-labels";

export function useOpportunityDetailPage(opportunityId: string) {
  const router = useRouter();
  const [opp, setOpp] = useState<BizOpportunity | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [converting, setConverting] = useState(false);
  const [quotes, setQuotes] = useState<BizQuote[]>([]);
  const [quoteName, setQuoteName] = useState("");
  const [quoteAmount, setQuoteAmount] = useState("");
  const [quoteSaving, setQuoteSaving] = useState(false);

  const loadQuotes = useCallback(async () => {
    const rows = await api.listQuotes(opportunityId);
    setQuotes(rows);
  }, [opportunityId]);

  const load = useCallback(async () => {
    const data = await api.getOpportunity(opportunityId);
    setOpp(data);
    await loadQuotes();
    return data;
  }, [opportunityId, loadQuotes]);

  useEffect(() => {
    load().catch((e) => setError(e?.message ?? "加载失败")).finally(() => setLoading(false));
  }, [load]);

  const handleConvert = async () => {
    setConverting(true);
    try {
      const result = await api.convertOpportunityToProject(opportunityId);
      router.push(`/business/projects/${result.project_id}`);
    } finally {
      setConverting(false);
    }
  };

  const handleAddQuote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!quoteName.trim()) return;
    setQuoteSaving(true);
    try {
      await api.createQuote(opportunityId, {
        name: quoteName.trim(),
        amount: quoteAmount ? Number(quoteAmount) : undefined,
      });
      setQuoteName("");
      setQuoteAmount("");
      await loadQuotes();
    } finally {
      setQuoteSaving(false);
    }
  };

  return { router, opp, loading, error, converting, handleConvert, reload: load, quotes, quoteName, setQuoteName, quoteAmount, setQuoteAmount, quoteSaving, handleAddQuote };
}

export type OpportunityDetailPageVm = ReturnType<typeof useOpportunityDetailPage>;

export function OpportunityDetailView({ vm }: { vm: OpportunityDetailPageVm }) {
  const { router, opp, loading, error, converting, handleConvert, quotes, quoteName, setQuoteName, quoteAmount, setQuoteAmount, quoteSaving, handleAddQuote } = vm;

  if (loading) return <p className="text-sm text-ink-muted">加载中…</p>;
  if (error || !opp) return <p className="text-sm text-red-600">{error || "商机不存在"}</p>;

  const canConvert = opp.stage === "won" && !opp.converted_to_project_id;

  return (
    <div>
      <button type="button" onClick={() => router.back()} className="mb-4 text-xs text-brand hover:underline">← 返回商机列表</button>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-ink">{opp.name}</h1>
          {opp.code && <p className="text-sm text-ink-muted">{opp.code}</p>}
        </div>
        <div className="flex items-center gap-3">
          <span className={`rounded px-2 py-0.5 text-xs ${stageBadgeClass(opp.stage)}`}>
            {OPPORTUNITY_STAGE_LABELS[opp.stage] ?? opp.stage}
          </span>
          {canConvert && (
            <button type="button" className="btn-primary text-xs" disabled={converting} onClick={() => void handleConvert()}>
              {converting ? "转化中…" : "转为项目"}
            </button>
          )}
          {opp.converted_to_project_id && (
            <Link href={`/business/projects/${opp.converted_to_project_id}`} className="btn-sm-outline text-xs">查看项目</Link>
          )}
        </div>
      </div>

      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        <InfoCard label="预估金额" value={opp.expected_value != null ? `¥${opp.expected_value.toLocaleString()}` : "—"} />
        <InfoCard label="赢单概率" value={opp.probability != null ? `${opp.probability}%` : "—"} />
        <InfoCard label="预计结单" value={opp.expected_close_date || "—"} />
        <InfoCard label="描述" value={opp.description || "—"} />
      </div>

      <section className="mt-8">
        <h2 className="text-sm font-semibold text-ink">报价单</h2>
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
                <div className="flex items-center gap-3 text-xs text-ink-muted">
                  {q.amount != null && <span>¥{q.amount.toLocaleString()}</span>}
                  <span className="rounded bg-surface-muted px-2 py-0.5">{QUOTE_STATUS_LABELS[q.status] ?? q.status}</span>
                  {q.valid_until && <span>有效期至 {q.valid_until}</span>}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function InfoCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="card p-4">
      <p className="text-xs text-ink-faint">{label}</p>
      <p className="mt-1 text-sm font-medium text-ink">{value}</p>
    </div>
  );
}
