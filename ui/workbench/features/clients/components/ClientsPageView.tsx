"use client";

import Link from "next/link";
import { ClientsTable } from "@/features/clients/components/ClientsTable";
import type { ClientsPageVm } from "@/features/clients/hooks/use-clients-page";

export function ClientsPageView({ vm }: { vm: ClientsPageVm }) {
  const { ready, search, onSearch, confirmDialog } = vm;

  if (!ready) {
    return <p className="text-sm text-ink-muted">加载中…</p>;
  }

  return (
    <div className="w-full">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-ink">客户</h1>
          <p className="mt-1 text-sm text-ink-muted">管理服务的政府机关、企事业单位及其他客户</p>
        </div>
        <Link href="/business/clients/new" className="btn-primary text-sm">
          新建客户
        </Link>
      </div>

      <div className="mb-4">
        <input
          type="search"
          placeholder="搜索客户名称…"
          value={search}
          onChange={(e) => onSearch(e.target.value)}
          className="input-field w-full max-w-xs text-sm"
        />
      </div>

      <ClientsTable vm={vm} />
      {confirmDialog}
    </div>
  );
}
