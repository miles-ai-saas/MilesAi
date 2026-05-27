"use client";

import Link from "next/link";
import { useCallback, useState } from "react";
import {
  STATUS_LABEL,
  statusBadgeClass,
  TYPE_LABEL,
  VENDOR_LABEL,
} from "@/components/model-catalog/form-utils";
import { ListFooter } from "@/components/list/ListFooter";
import { PageHeader } from "@/components/layout/PageHeader";
import { usePagedList } from "@/hooks/use-paged-list";
import { adminApi } from "@/lib/api";
import { useRequireAdmin } from "@/lib/auth-store";

export default function ModelCatalogPage() {
  const ready = useRequireAdmin();
  const [vendor, setVendor] = useState("");

  const list = usePagedList(
    useCallback((p, s) => adminApi.listModelCatalog(p, s, vendor || undefined), [vendor]),
    { enabled: ready, resetKey: vendor },
  );

  return (
    <div>
      <PageHeader
        title="内置模型目录"
        description="维护内置模型元数据，配置平台 API Key 供租户直接使用。"
        action={
          <Link href="/model-catalog/new" className="btn-primary">
            + 新建内置模型
          </Link>
        }
      />

      <div className="mb-4 flex flex-wrap gap-2">
        {["", "deepseek", "doubao", "qwen"].map((v) => (
          <button
            key={v || "all"}
            type="button"
            onClick={() => setVendor(v)}
            className={`rounded-full px-3 py-1 text-xs ${
              vendor === v ? "bg-brand text-white" : "border bg-surface text-ink-muted"
            }`}
          >
            {v ? VENDOR_LABEL[v] ?? v : "全部"}
          </button>
        ))}
      </div>

      {list.loading ? (
        <p className="text-sm text-ink-muted">加载中…</p>
      ) : (
        <>
          <div className="admin-table-wrap">
            <table className="admin-table">
              <thead>
                <tr>
                  <th className="min-w-[10rem]">名称</th>
                  <th className="col-compact">服务商</th>
                  <th className="col-compact">类型</th>
                  <th className="col-center">状态</th>
                  <th className="col-center">平台 Key</th>
                  <th className="col-actions">操作</th>
                </tr>
              </thead>
              <tbody>
                {list.items.length === 0 && (
                  <tr>
                    <td colSpan={6} className="py-10 text-center cell-muted">
                      暂无模型。可{" "}
                      <Link href="/model-catalog/new" className="text-brand hover:underline">
                        新建
                      </Link>{" "}
                      或执行 seed。
                    </td>
                  </tr>
                )}
                {list.items.map((m) => {
                  const modelId = m.model_code ?? m.model_name;
                  return (
                    <tr key={m.id}>
                      <td className="cell-stack">
                        <Link
                          href={`/model-catalog/${m.id}`}
                          className="cell-stack-title hover:text-brand"
                        >
                          {m.name}
                        </Link>
                        {modelId && (
                          <div className="cell-stack-sub" title={modelId}>
                            {modelId}
                          </div>
                        )}
                      </td>
                      <td className="col-compact cell-muted whitespace-nowrap">
                        {VENDOR_LABEL[m.vendor] ?? m.vendor}
                      </td>
                      <td className="col-compact cell-muted whitespace-nowrap">
                        {TYPE_LABEL[m.model_type] ?? m.model_type}
                      </td>
                      <td className="col-center">
                        <span className={`status-badge ${statusBadgeClass(m.publish_status)}`}>
                          {STATUS_LABEL[m.publish_status] ?? m.publish_status}
                        </span>
                      </td>
                      <td className="col-center">
                        <span className={m.has_api_key ? "key-badge-ready" : "key-badge-missing"}>
                          {m.has_api_key ? "已配置" : "未配置"}
                        </span>
                      </td>
                      <td className="col-actions">
                        <Link href={`/model-catalog/${m.id}`} className="text-brand hover:underline">
                          管理
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <ListFooter
            className="mt-3"
            page={list.page}
            size={list.size}
            total={list.total}
            onPageChange={list.setPage}
            onSizeChange={list.setSize}
          />
        </>
      )}
    </div>
  );
}
