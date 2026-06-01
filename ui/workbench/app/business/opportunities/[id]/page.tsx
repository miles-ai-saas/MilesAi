"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { BizOpportunity } from "@/lib/types";

const STAGE_LABELS: Record<string, string> = { prospecting: "线索", qualification: "资质确认", proposal: "方案报价", negotiation: "谈判", won: "赢单", lost: "丢单" };

export default function OpportunityDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [opp, setOpp] = useState<BizOpportunity | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api.getOpportunity(id).then(setOpp).catch((e) => setError(e?.message ?? "加载失败")).finally(() => setLoading(false));
  }, [id]);

  if (loading) return <p className="text-sm text-ink-muted">加载中…</p>;
  if (error || !opp) return <p className="text-sm text-red-600">{error || "商机不存在"}</p>;

  const canConvert = opp.stage === "won" && !opp.converted_to_project_id;

  return (
    <div>
      <button type="button" onClick={() => router.back()} className="mb-4 text-xs text-brand hover:underline">← 返回商机列表</button>
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold text-ink">{opp.name}</h1>
          {opp.code && <p className="text-sm text-ink-muted">{opp.code}</p>}
        </div>
        <div className="flex items-center gap-3">
          <span className={`rounded px-2 py-0.5 text-xs ${opp.stage === "won" ? "bg-green-50 text-green-700" : opp.stage === "lost" ? "bg-red-50 text-red-600" : "bg-brand-light text-brand"}`}>
            {STAGE_LABELS[opp.stage] ?? opp.stage}
          </span>
          {canConvert && (
            <Link href={`/business/projects/new?client_id=${opp.client_id}&opportunity_id=${opp.id}`} className="btn-primary text-xs">转为项目</Link>
          )}
        </div>
      </div>

      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        <div className="card p-4"><p className="text-xs text-ink-faint">预估金额</p><p className="mt-1 text-sm font-medium text-ink">{opp.expected_value != null ? `¥${opp.expected_value.toLocaleString()}` : "—"}</p></div>
        <div className="card p-4"><p className="text-xs text-ink-faint">赢单概率</p><p className="mt-1 text-sm font-medium text-ink">{opp.probability != null ? `${opp.probability}%` : "—"}</p></div>
        <div className="card p-4"><p className="text-xs text-ink-faint">预计结单</p><p className="mt-1 text-sm font-medium text-ink">{opp.expected_close_date || "—"}</p></div>
        <div className="card p-4"><p className="text-xs text-ink-faint">描述</p><p className="mt-1 text-sm text-ink">{opp.description || "—"}</p></div>
      </div>
    </div>
  );
}
