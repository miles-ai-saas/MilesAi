"use client";

import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import type { OpportunitiesPageVm } from "@/features/opportunities/hooks/use-opportunities-page";
import type { BizOpportunity } from "@/lib/types";
import { OPPORTUNITY_STAGE_LABELS, stageBadgeClass } from "@/features/opportunities/lib/opportunity-labels";

export function OpportunitiesTable({ vm }: { vm: OpportunitiesPageVm }) {
  const { list, onDelete, openDetail } = vm;
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
                  <button type="button" onClick={() => openDetail(o.id)} className="font-medium text-ink hover:text-brand text-left">
                    {o.name}
                  </button>
                </td>
                <td className="px-4 py-3">
                  <span className={`rounded px-2 py-0.5 text-xs ${stageBadgeClass(o.stage)}`}>
                    {OPPORTUNITY_STAGE_LABELS[o.stage] ?? o.stage}
                  </span>
                </td>
                <td className="px-4 py-3 text-ink-muted text-xs">
                  {o.expected_value != null ? `¥${o.expected_value.toLocaleString()}` : "—"}
                  {o.probability != null ? ` / ${o.probability}%` : ""}
                </td>
                <td className="px-4 py-3 text-right">
                  <button type="button" className="mr-3 text-xs text-brand hover:underline" onClick={() => openDetail(o.id)}>详情</button>
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
