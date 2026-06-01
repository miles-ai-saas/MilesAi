"use client";

import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import type { ClientsPageVm } from "@/features/clients/hooks/use-clients-page";
import type { BizClient } from "@/lib/types";

const INDUSTRY_LABELS: Record<string, string> = {
  government: "政府机关",
  enterprise: "企业",
  park: "园区",
  commercial: "商业综合体",
  tourism: "文旅",
  other: "其他",
};

const CONF_LABELS: Record<string, string> = {
  normal: "普通",
  internal: "内部",
  restricted: "涉密",
};

export function ClientsTable({ vm }: { vm: ClientsPageVm }) {
  const { list, onDelete, openDetail } = vm;

  if (list.loading) {
    return <p className="text-sm text-ink-muted">加载中…</p>;
  }

  return (
    <>
      <div className="card overflow-hidden">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-line bg-surface-muted text-xs text-ink-muted">
            <tr>
              <th className="px-4 py-2">客户名称</th>
              <th className="px-4 py-2">行业</th>
              <th className="px-4 py-2">保密等级</th>
              <th className="px-4 py-2">项目数</th>
              <th className="px-4 py-2 text-right">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line-soft">
            {list.items.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-ink-faint">
                  暂无客户
                </td>
              </tr>
            )}
            {list.items.map((c: BizClient) => (
              <tr key={c.id}>
                <td className="px-4 py-3">
                  <button type="button" onClick={() => openDetail(c.id)} className="font-medium text-ink hover:text-brand text-left">
                    {c.name}
                  </button>
                  {c.short_name && <span className="ml-2 text-xs text-ink-faint">{c.short_name}</span>}
                </td>
                <td className="px-4 py-3 text-ink-muted">{INDUSTRY_LABELS[c.industry ?? ""] ?? c.industry ?? "—"}</td>
                <td className="px-4 py-3">
                  <span className={`rounded px-2 py-0.5 text-xs ${
                    c.confidentiality_level === "restricted" ? "bg-red-50 text-red-600" :
                    c.confidentiality_level === "internal" ? "bg-yellow-50 text-yellow-700" :
                    "bg-surface-muted text-ink-muted"
                  }`}>
                    {CONF_LABELS[c.confidentiality_level] ?? c.confidentiality_level}
                  </span>
                </td>
                <td className="px-4 py-3 text-ink-muted">{c.project_count}</td>
                <td className="px-4 py-3 text-right">
                  <button type="button" className="mr-3 text-xs text-brand hover:underline" onClick={() => openDetail(c.id)}>
                    详情
                  </button>
                  <button type="button" className="text-xs text-red-600 hover:underline" onClick={() => onDelete(c)}>
                    删除
                  </button>
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
