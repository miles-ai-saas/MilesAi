"use client";

import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import type { ContractsPageVm } from "@/features/contracts/hooks/use-contracts-page";
import {
  CONTRACT_STATUS_LABELS,
  CONTRACT_TYPE_LABELS,
  contractStatusBadgeClass,
} from "@/features/contracts/lib/contract-labels";
import type { BizContract } from "@/lib/types";

export function ContractsTable({ vm }: { vm: ContractsPageVm }) {
  const { list, onDelete, openDetail } = vm;
  if (list.loading) return <p className="text-sm text-ink-muted">加载中…</p>;

  return (
    <>
      <div className="card overflow-hidden">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-line bg-surface-muted text-xs text-ink-muted">
            <tr>
              <th className="px-4 py-2">合同名称</th>
              <th className="px-4 py-2">编号</th>
              <th className="px-4 py-2">金额/状态</th>
              <th className="px-4 py-2 text-right">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line-soft">
            {list.items.length === 0 && <tr><td colSpan={4} className="px-4 py-8 text-center text-ink-faint">暂无合同</td></tr>}
            {list.items.map((c: BizContract) => (
              <tr key={c.id}>
                <td className="px-4 py-3">
                  <button type="button" onClick={() => openDetail(c.id)} className="font-medium text-ink hover:text-brand text-left">
                    {c.name}
                  </button>
                  <span className="ml-2 text-xs text-ink-muted">{CONTRACT_TYPE_LABELS[c.type] ?? c.type}</span>
                </td>
                <td className="px-4 py-3 text-xs text-ink-faint">{c.contract_no || "—"}</td>
                <td className="px-4 py-3">
                  {c.total_amount != null && <span className="text-xs font-medium text-ink">¥{c.total_amount.toLocaleString()}</span>}
                  <span className={`ml-2 rounded px-2 py-0.5 text-xs ${contractStatusBadgeClass(c.status)}`}>
                    {CONTRACT_STATUS_LABELS[c.status] ?? c.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-right">
                  <button type="button" className="mr-3 text-xs text-brand hover:underline" onClick={() => openDetail(c.id)}>详情</button>
                  <button type="button" className="text-xs text-red-600 hover:underline" onClick={() => onDelete(c)}>删除</button>
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
