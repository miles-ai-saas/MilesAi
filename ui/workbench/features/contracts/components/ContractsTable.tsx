"use client";

import Link from "next/link";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import type { ContractsPageVm } from "@/features/contracts/hooks/use-contracts-page";
import type { BizContract } from "@/lib/types";

const STATUS_LABELS: Record<string, string> = { draft: "草稿", pending_sign: "待签署", signed: "已签署", active: "履约中", completed: "已完结", terminated: "已终止" };
const TYPE_LABELS: Record<string, string> = { service: "服务合同", nda: "保密协议", framework: "框架协议", other: "其他" };

export function ContractsTable({ vm }: { vm: ContractsPageVm }) {
  const { list, onDelete } = vm;
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
                  <Link href={`/business/contracts/${c.id}`} className="font-medium text-ink hover:text-brand">{c.name}</Link>
                  <span className="ml-2 text-xs text-ink-muted">{TYPE_LABELS[c.type] ?? c.type}</span>
                </td>
                <td className="px-4 py-3 text-xs text-ink-faint">{c.contract_no || "—"}</td>
                <td className="px-4 py-3">
                  {c.total_amount != null && <span className="text-xs font-medium text-ink">¥{c.total_amount.toLocaleString()}</span>}
                  <span className={`ml-2 rounded px-2 py-0.5 text-xs ${c.status === "active" ? "bg-brand-light text-brand" : c.status === "signed" ? "bg-green-50 text-green-700" : c.status === "terminated" ? "bg-red-50 text-red-600" : "bg-surface-muted text-ink-muted"}`}>
                    {STATUS_LABELS[c.status] ?? c.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-right">
                  <Link href={`/business/contracts/${c.id}`} className="mr-3 text-xs text-brand hover:underline">详情</Link>
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
