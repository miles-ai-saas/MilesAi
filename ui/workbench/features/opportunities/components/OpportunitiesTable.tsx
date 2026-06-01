"use client";

import Link from "next/link";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import type { OpportunitiesPageVm } from "@/features/opportunities/hooks/use-opportunities-page";
import type { BizOpportunity } from "@/lib/types";

const STAGE_LABELS: Record<string, string> = {
  prospecting: "线索", qualification: "资质确认", proposal: "方案报价",
  negotiation: "谈判", won: "赢单", lost: "丢单",
};

export function OpportunitiesTable({ vm }: { vm: OpportunitiesPageVm }) {
  const { list, onDelete } = vm;
  if (list.loading) return <p className="text-sm text-ink-muted">加载中…</p>;

  return (
    <>
      <div className="card overflow-hidden">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-line bg-surface-muted text-xs text-ink-muted">
            <tr>
              <th className="px-4 py-2">商机名称</th>
              <th className="px-4 py-2">阶段</th>
              <th className="px-4 py-2">金额/概率</th>
              <th className="px-4 py-2 text-right">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line-soft">
            {list.items.length === 0 && <tr><td colSpan={4} className="px-4 py-8 text-center text-ink-faint">暂无商机</td></tr>}
            {list.items.map((o: BizOpportunity) => (
              <tr key={o.id}>
                <td className="px-4 py-3">
                  <Link href={`/business/opportunities/${o.id}`} className="font-medium text-ink hover:text-brand">{o.name}</Link>
                </td>
                <td className="px-4 py-3">
                  <span className={`rounded px-2 py-0.5 text-xs ${
                    o.stage === "won" ? "bg-green-50 text-green-700" :
                    o.stage === "lost" ? "bg-red-50 text-red-600" :
                    o.stage === "negotiation" ? "bg-amber-50 text-amber-700" :
                    "bg-brand-light text-brand"
                  }`}>{STAGE_LABELS[o.stage] ?? o.stage}</span>
                </td>
                <td className="px-4 py-3 text-ink-muted text-xs">
                  {o.expected_value != null ? `¥${o.expected_value.toLocaleString()}` : "—"}
                  {o.probability != null ? ` / ${o.probability}%` : ""}
                </td>
                <td className="px-4 py-3 text-right">
                  <Link href={`/business/opportunities/${o.id}`} className="mr-3 text-xs text-brand hover:underline">详情</Link>
                  <button type="button" className="text-xs text-red-600 hover:underline" onClick={() => onDelete(o)}>删除</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ResourceListFooter className="mt-3" page={list.page} size={list.size} total={list.total} onPageChange={list.setPage} onSizeChange={list.setSize} />
    </>
  );
}
