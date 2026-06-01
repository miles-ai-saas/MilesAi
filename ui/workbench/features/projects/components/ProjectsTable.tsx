"use client";

import Link from "next/link";
import { ResourceListFooter } from "@/components/resource/ResourceListFooter";
import type { ProjectsPageVm } from "@/features/projects/hooks/use-projects-page";
import type { BizProject } from "@/lib/types";

const STATUS_LABELS: Record<string, string> = {
  draft: "草稿", active: "进行中", on_hold: "暂停",
  delivered: "已交付", closed: "已结项", cancelled: "已取消",
};

export function ProjectsTable({ vm }: { vm: ProjectsPageVm }) {
  const { list, onDelete } = vm;

  if (list.loading) return <p className="text-sm text-ink-muted">加载中…</p>;

  return (
    <>
      <div className="card overflow-hidden">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-line bg-surface-muted text-xs text-ink-muted">
            <tr>
              <th className="px-4 py-2">项目名称</th>
              <th className="px-4 py-2">状态</th>
              <th className="px-4 py-2">工作包</th>
              <th className="px-4 py-2 text-right">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line-soft">
            {list.items.length === 0 && (
              <tr><td colSpan={4} className="px-4 py-8 text-center text-ink-faint">暂无项目</td></tr>
            )}
            {list.items.map((p: BizProject) => (
              <tr key={p.id}>
                <td className="px-4 py-3">
                  <Link href={`/business/projects/${p.id}`} className="font-medium text-ink hover:text-brand">
                    {p.name}
                  </Link>
                  {p.code && <span className="ml-2 text-xs text-ink-faint">{p.code}</span>}
                </td>
                <td className="px-4 py-3">
                  <span className={`rounded px-2 py-0.5 text-xs ${
                    p.status === "active" ? "bg-brand-light text-brand" :
                    p.status === "delivered" ? "bg-green-50 text-green-700" :
                    p.status === "cancelled" ? "bg-red-50 text-red-600" :
                    "bg-surface-muted text-ink-muted"
                  }`}>
                    {STATUS_LABELS[p.status] ?? p.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-ink-muted">{p.work_packages?.length ?? 0}</td>
                <td className="px-4 py-3 text-right">
                  <Link href={`/business/projects/${p.id}`} className="mr-3 text-xs text-brand hover:underline">详情</Link>
                  <button type="button" className="text-xs text-red-600 hover:underline" onClick={() => onDelete(p)}>删除</button>
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
